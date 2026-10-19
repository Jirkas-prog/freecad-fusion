"""Fusion-like commands producing only native FreeCAD Part Design objects."""
import FreeCAD as App
import Part


def body_of(obj):
    if obj and obj.TypeId == 'PartDesign::Body':
        return obj
    return obj.getParentGeoFeatureGroup() if obj else None


def hide_unused_profiles(doc):
    """Native Delete shows an operation's input. Internal binders are not models.

    Keep the objects and their links for Undo/Redo; only hide unconsumed helpers
    created by FusionFlow. Ordinary user-created binders are left alone.
    """
    if not doc or not App.GuiUp:return []
    hidden=[]
    for obj in doc.Objects:
        if obj.TypeId!='PartDesign::SubShapeBinder' or not obj.Visibility:continue
        generated=getattr(obj,'FusionFlowProfile',False) or (
            obj.Name.startswith('ExtrudeProfile') and 'StartOffset' in obj.PropertiesList
            and obj.getGroupOfProperty('StartOffset')=='Extrude')
        if not generated:continue
        consumers=[parent for parent in obj.InList
                   if parent.TypeId not in ('PartDesign::Body','App::Part','App::DocumentObjectGroup')]
        if not consumers:
            obj.Visibility=False;hidden.append(obj.Name)
    return hidden


def check(feature, allow_empty=False):
    feature.Document.recompute()
    if 'Invalid' in feature.State or feature.Shape.isNull():
        raise ValueError(feature.getStatusString())
    if not feature.Shape.isValid() or (not feature.Shape.Solids and not allow_empty):
        raise ValueError('Výsledek není platné objemové těleso. Zkontroluj profil, směr a rozměry.')
    return feature


def resolve_profile(source, regions):
    """Resolve Body faces to the current feature, never to a changing Body Tip."""
    if source.TypeId == 'PartDesign::Body':
        source = source.Tip
    if not source:
        raise ValueError('Vyber oblast skici nebo rovinnou stěnu.')
    if source.TypeId == 'Sketcher::SketchObject':
        source.MakeInternals = True
        source.Document.recompute()
        if not regions or any(not isinstance(i, int) or i < 1 or i > len(source.InternalShape.Faces) for i in regions):
            raise ValueError('Vyber alespoň jednu uzavřenou oblast skici.')
        return source, ['InternalFace%d' % i for i in regions], source.getGlobalPlacement().Rotation.multVec(App.Vector(0, 0, 1))
    if not regions or any(not isinstance(n, str) or not n.startswith('Face') or not n[4:].isdigit() for n in regions):
        raise ValueError('Vyber rovinnou stěnu tělesa.')
    faces = [source.Shape.getElement(n) for n in regions]
    if any(not isinstance(f.Surface, Part.Plane) for f in faces):
        raise ValueError('Extrude vyžaduje rovinnou stěnu. Zakřivenou stěnu nelze vysunout jako rovinný profil.')
    normal = faces[0].normalAt(0, 0)
    origin = faces[0].CenterOfMass
    if any(normal.dot(f.normalAt(0, 0)) < 1-1e-7 or abs(normal.dot(f.CenterOfMass-origin)) > 1e-7 for f in faces[1:]):
        raise ValueError('Vybrané stěny musí ležet ve stejné rovině a mít stejný směr.')
    # Shape already includes the feature Placement; add only its parent transform.
    parent_rotation = source.getGlobalPlacement().Rotation * source.Placement.Rotation.inverted()
    return source, list(regions), parent_rotation.multVec(normal)


def global_shape(obj):
    shape = obj.Shape.copy()
    shape.Placement = obj.getGlobalPlacement() * obj.Placement.inverse() * shape.Placement
    return shape


def profile_anchor(source, regions, on_face=False):
    """World-space centre and normal shared by the preview and its handle."""
    source, names, normal = resolve_profile(source, regions)
    if source.TypeId == 'Sketcher::SketchObject':
        faces = [source.InternalShape.Faces[i-1] for i in regions]
        transform = source.getGlobalPlacement()
    else:
        faces = [source.Shape.getElement(n) for n in names]
        transform = source.getGlobalPlacement() * source.Placement.inverse()
    area = sum(f.Area for f in faces)
    centre = sum((f.CenterOfMass*f.Area for f in faces), App.Vector()) / area
    if on_face and not any(f.isInside(centre, 1e-7, True) for f in faces):
        # A ring's centre lies in its hole. Use an interior triangle of the
        # largest selected region instead of placing the controls in empty air.
        face = max(faces, key=lambda f: f.Area)
        vertices, triangles = face.tessellate(max(face.BoundBox.DiagonalLength/100, .001))
        triangle = max(triangles, key=lambda t: (vertices[t[1]]-vertices[t[0]]).cross(vertices[t[2]]-vertices[t[0]]).Length)
        centre = sum((vertices[i] for i in triangle), App.Vector()) / 3
    return transform.multVec(centre), normal


def suggest_operation(source, regions, **options):
    """Use the native tapered/offset sweep; never leave a probe in the document."""
    if options.get('extent') == 'All':
        return 'Cut', None
    doc = source.Document
    bodies = [(o, global_shape(o)) for o in doc.Objects
              if o.TypeId == 'PartDesign::Body' and o.Tip and o.Shape.Solids]
    if not bodies:
        return 'New body', None
    before = {o.Name for o in doc.Objects}
    visibility = {o.Name:o.Visibility for o in doc.Objects if hasattr(o, 'Visibility')}
    try:
        probe = doc.addObject('PartDesign::Body', 'ExtrudeProbe')
        # Explicit Join into an empty probe prevents reusing an existing empty Body.
        feature = extrude(source, regions, 'Join', probe, **options)
        sweep = global_shape(feature)
        joined = []
        for body, shape in bodies:
            bounds = shape.BoundBox
            bounds.enlarge(1e-7)
            if not bounds.intersect(sweep.BoundBox):
                continue
            common = shape.common(sweep)
            if common.Volume > max(1e-7, min(shape.Volume, sweep.Volume)*1e-10):
                return 'Cut', None
            if shape.distToShape(sweep)[0] <= 1e-7:
                # Edge/point contact is not a volume union. A shared face is.
                if len(shape.fuse(sweep).Solids) < len(shape.Solids)+len(sweep.Solids):
                    joined.append(body)
        if joined:
            owner = body_of(source)
            return 'Join', owner if owner in joined else joined[0] if len(joined)==1 else None
        return 'New body', None
    finally:
        for obj in reversed(doc.Objects):
            if obj.Name not in before:
                doc.removeObject(obj.Name)
        for name, visible in visibility.items():
            doc.getObject(name).Visibility = visible
        doc.recompute()


def extrude(sketch, regions, operation='New body', target=None, length=10,
            length2=10, direction='One side', reverse=False, start=0,
            taper=0, taper2=0, extent='Distance', end_face=None, end_offset=0):
    """Caller owns the transaction. A failed preview must be aborted by caller."""
    sketch, names, normal = resolve_profile(sketch, regions)
    doc = sketch.Document
    is_sketch = sketch.TypeId == 'Sketcher::SketchObject'
    if operation not in ('New body', 'Join', 'Cut', 'Intersect'):
        raise ValueError('Neznámá operace.')
    if operation != 'New body' and (not target or target.TypeId != 'PartDesign::Body'):
        raise ValueError('Vyber cílové těleso.')
    if target and target.Document != doc:
        raise ValueError('Těleso a profil musí být ve stejném dokumentu.')
    if extent == 'Distance' and (length <= 0 or (direction == 'Two sides' and length2 <= 0)):
        raise ValueError('Vzdálenost musí být kladná. Směr otoč volbou Reverse.')
    if extent == 'To object' and not end_face:
        raise ValueError('Vyber koncovou plochu a stiskni Použít vybranou plochu.')
    if extent == 'All' and operation != 'Cut':
        raise ValueError('All / Skrz vše je k dispozici pro odebrání Cut.')
    if extent != 'Distance' and direction != 'One side':
        raise ValueError('Pro To object / All zvol One side.')
    if operation == 'New body':
        owner = body_of(sketch)
        target = owner if owner and owner.TypeId == 'PartDesign::Body' and not owner.Tip else doc.addObject('PartDesign::Body', 'Body')
        target.Label = 'Body'
    if operation == 'Intersect':
        tool = extrude(sketch, regions, 'New body', length=length, length2=length2,
                       direction=direction, reverse=reverse, start=start, taper=taper,
                       taper2=taper2, extent=extent, end_face=end_face, end_offset=end_offset)
        return combine(target, [body_of(tool)], 'Intersect')
    old_tip = target.Tip
    target.AllowCompound = True
    profile, subs = sketch, names
    if start or body_of(sketch) != target or not is_sketch:
        binder = target.newObject('PartDesign::SubShapeBinder', 'ExtrudeProfile')
        binder.Label = 'Profile / Start offset'
        binder.addProperty('App::PropertyBool','FusionFlowProfile','FusionFlow').FusionFlowProfile=True
        binder.setEditorMode('FusionFlowProfile',2)
        owner = body_of(sketch)
        if owner and owner.TypeId == 'PartDesign::Body' and owner != target:
            binder.Support = [(owner, [sketch.Name+'.'+name for name in names])]
        else:
            binder.Support = [(sketch, names)]
        binder.Relative = True
        binder.Fuse = True
        doc.recompute()
        # Relative binding follows the source placement as well as its curves.
        binder.Placement.Base = target.getGlobalPlacement().Rotation.inverted().multVec(normal * start)
        binder.addProperty('App::PropertyDistance', 'StartOffset', 'Extrude').StartOffset = start
        if is_sketch and (body_of(sketch) == target or (not body_of(sketch) and target.Placement.Rotation.isIdentity())):
            binder.setExpression('Placement.Base', '%s.Placement.Rotation * vector(0; 0; StartOffset)' % sketch.Name)
        # ponytail: for differently placed bodies the initial normal is fixed;
        # re-create the offset profile after reorienting those bodies.
        profile, subs = binder, ['']
        binder.Visibility = False
    kind = 'Pocket' if operation == 'Cut' else 'Pad'
    feature = target.newObject('PartDesign::' + kind, 'Extrude')
    feature.Label = 'Extrude · ' + operation
    feature.Profile = (profile, subs)
    feature.Length = length
    feature.Length2 = length2
    feature.SideType = direction
    # Pocket's native positive direction is opposite to Pad. The common dialog
    # always uses the sketch normal, independently of Join/Cut.
    feature.Reversed = (not reverse) if kind == 'Pocket' else reverse
    feature.TaperAngle = taper
    feature.TaperAngle2 = taper2
    feature.AllowMultiFace = True
    feature.Refine = True
    if extent == 'All':
        feature.Type = 'ThroughAll'
    elif extent == 'To object':
        feature.Type = 'UpToFace'
        feature.UpToFace = end_face
        feature.Offset = end_offset
    else:
        feature.Type = 'Length'
    check(feature, allow_empty=operation == 'Cut')
    target.Tip = feature
    if old_tip:
        old_tip.Visibility = False
    sketch.Visibility = False
    feature.Visibility = True
    target.Visibility = True
    if profile != sketch:
        profile.Visibility = False
    return feature


def cut_all(source, regions, targets=None, **options):
    """Cut intersected targets in one caller-owned transaction; None means all.

    An explicit empty selection is never interpreted as all bodies. Excluded
    bodies are not probed or modified, even temporarily.
    """
    source, names, _ = resolve_profile(source, regions)
    doc = source.Document
    profiles = regions if source.TypeId == 'Sketcher::SketchObject' else names
    bases = {o.Name:o.Tip.Name for o in doc.Objects
             if o.TypeId == 'PartDesign::Body' and o.Tip and o.Shape.Solids}
    if targets is None:
        targets = [o for o in doc.Objects if o.TypeId == 'PartDesign::Body' and o.Tip and o.Shape.Solids]
    else:
        targets = list(dict.fromkeys(targets))
        if not targets:
            raise ValueError('Nejsou vybraná žádná tělesa k odebrání. Zaškrtni je v Objects To Cut.')
        if any(not o or o.Document != doc or o.TypeId != 'PartDesign::Body' or not o.Tip or not o.Shape.Solids for o in targets):
            raise ValueError('Cíle řezu musí být objemová Part Design tělesa ve stejném dokumentu.')
    results = []
    for target in targets:
        old_tip = target.Tip
        old_compound = target.AllowCompound
        volume = target.Shape.Volume
        before = {o.Name for o in doc.Objects}
        visibility = {o.Name:o.Visibility for o in doc.Objects if hasattr(o, 'Visibility')}
        feature = extrude(source, profiles, 'Cut', target, **options)
        if volume-feature.Shape.Volume > max(1e-7, volume*1e-10):
            results.append(feature)
            continue
        # Native Pocket returns an unchanged solid when the sweep misses it.
        # Remove that unused history step and its binder, keeping all other cuts.
        target.Tip = old_tip
        target.AllowCompound = old_compound
        for obj in reversed(doc.Objects):
            if obj.Name not in before:
                doc.removeObject(obj.Name)
        for name, visible in visibility.items():
            doc.getObject(name).Visibility = visible
        doc.recompute()
    if not results:
        raise ValueError('Vysunutí neprotíná žádné vybrané těleso. Změň výběr, vzdálenost nebo směr.')
    from fusionflow_cut_history import remember_cut
    remember_cut(source, profiles, bases, targets, results, options)
    return results


def combine(target, tools, operation='Join', keep=False):
    if not target or target.TypeId != 'PartDesign::Body' or not target.Tip:
        raise ValueError('Vyber cílové Part Design těleso s objemem.')
    if not tools or target in tools:
        raise ValueError('Vyber jiné nástrojové těleso.')
    if operation not in ('Join', 'Cut', 'Intersect'):
        raise ValueError('Neznámá booleovská operace.')
    for tool in tools:
        if tool.TypeId != 'PartDesign::Body' or tool.Document != target.Document or tool.Shape.isNull():
            raise ValueError('Nástroj musí být objemové Part Design těleso ve stejném dokumentu.')
        if target in tool.OutListRecursive:
            raise ValueError('Nástroj už závisí na cíli. Operace by vytvořila kruhovou závislost.')
    old_tip = target.Tip
    feature = target.newObject('PartDesign::Boolean', 'Combine')
    feature.Label = 'Combine · ' + operation
    feature.Type = {'Join': 'Fuse', 'Cut': 'Cut', 'Intersect': 'Common'}[operation]
    feature.addObjects(tools)
    feature.Refine = True
    check(feature)
    target.Tip = feature
    old_tip.Visibility = False
    feature.Visibility = True
    for tool in tools:
        tool.Visibility = keep
    return feature
