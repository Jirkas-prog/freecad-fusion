"""Non-destructive saved analyses; model solids remain native and untouched."""
import json
import math
import FreeCAD as App
import Part
from fusionflow_core import global_shape

SECTION_DEFAULTS = dict(plane='XY', offset=0, angle_x=0, angle_y=0,
                        flip=False, caps=True, hatch=True, reference_axes=True)


def is_datum_plane(obj):
    kind=getattr(obj,'ConstructionMode','')
    return obj.TypeId in ('PartDesign::Plane','App::Plane') or kind.endswith('Plane') or kind=='Midplane'


def is_visible(obj):
    """Effective visibility includes every containing Body/Part/LinkGroup."""
    return bool(obj and getattr(obj,'Visibility',False) and all(
        is_visible(parent) for parent in obj.InList
        if parent.TypeId in ('PartDesign::Body','App::Part','App::LinkGroup')))


def displayed_object(obj):
    if not is_visible(obj):return None
    if obj.TypeId=='PartDesign::Body':obj=getattr(obj,'VisibleFeature',obj.Tip)
    return obj if is_visible(obj) else None


def visible_shapes(doc, displayed=False):
    """Top-level visible representations, excluding duplicate Body children."""
    result = []
    for obj in doc.Objects:
        if not hasattr(obj, 'Shape') or not getattr(obj, 'Visibility', False) or getattr(obj,'ConstructionMode',''):
            continue
        if obj.TypeId in ('Sketcher::SketchObject','App::Part','App::LinkGroup') or obj.isDerivedFrom('PartDesign::Feature') and obj.TypeId != 'PartDesign::Body':
            continue
        if displayed:obj=displayed_object(obj)
        if not is_visible(obj):continue
        if obj.Shape.isNull() or not obj.Shape.Faces:
            continue
        result.append(obj)
    return result


def plane_frame(settings, references=()):
    plane = settings.get('plane', 'XY')
    position = App.Vector()
    rotation = None
    normal = {'XY':App.Vector(0,0,1), 'XZ':App.Vector(0,-1,0), 'YZ':App.Vector(1,0,0)}.get(plane)
    if plane == 'Selection':
        if not references:
            raise ValueError('Vyber rovinnou stěnu nebo konstrukční rovinu.')
        obj, subs = references[0]
        if is_datum_plane(obj):
            placement = obj.getGlobalPlacement()
            position, normal = placement.Base, placement.Rotation.multVec(App.Vector(0,0,1))
            if settings.get('reference_axes',False):rotation=placement.Rotation
        else:
            if not subs or not subs[0].startswith('Face'):
                raise ValueError('Reference řezu musí být rovinná stěna nebo konstrukční rovina.')
            face = global_shape(obj).getElement(subs[0])
            if not isinstance(face.Surface, Part.Plane):
                raise ValueError('Zakřivená stěna neurčuje jedinou rovinu. Vyber rovinnou stěnu.')
            position, normal = face.CenterOfMass, face.normalAt(0,0)
            if settings.get('reference_axes',False):
                x=face.Surface.tangent(0,0)[0]
                rotation=App.Rotation(x,normal.cross(x),normal,'ZXY')
    if normal is None:
        raise ValueError('Neznámá rovina řezu.')
    # Older saved sections contain no reference_axes key. Keep their exact
    # orientation until the user opts into the reference plane's local axes.
    if rotation is None:rotation = App.Rotation(App.Vector(0,0,1), normal)
    rotation = rotation * App.Rotation(App.Vector(1,0,0), settings.get('angle_x',0)) * App.Rotation(App.Vector(0,1,0), settings.get('angle_y',0))
    normal = rotation.multVec(App.Vector(0,0,1))
    return App.Placement(position + normal*settings.get('offset',0), rotation)


def section_caps(shape, frame):
    normal = frame.Rotation.multVec(App.Vector(0,0,1))
    wires = shape.slice(normal, normal.dot(frame.Base))
    return Part.makeFace(wires, 'Part::FaceMakerBullseye') if wires else Part.Shape()


def changed():
    if App.GuiUp:
        import fusionflow_analysis_view as view
        if view.manager:
            view.manager.dirty = True


class Analysis:
    def __init__(self, obj, kind, settings, references=()):
        obj.addProperty('App::PropertyString','AnalysisType','Analysis').AnalysisType = kind
        obj.setEditorMode('AnalysisType',1)
        obj.addProperty('App::PropertyString','Settings','Analysis').Settings = json.dumps(settings)
        obj.setEditorMode('Settings',2)
        # Analyses live outside Bodies and may reference their internal features.
        obj.addProperty('App::PropertyLinkSubListGlobal','References','Analysis').References = references
        obj.addProperty('App::PropertyString','Result','Analysis')
        obj.setEditorMode('Result',1)
        obj.Proxy = self

    def execute(self, obj):
        if obj.AnalysisType == 'Section':
            plane_frame(json.loads(obj.Settings), obj.References)
        changed()

    def onDocumentRestored(self, obj):
        changed()

    def dumps(self):
        return None

    def loads(self, state):
        pass


def create_analysis(doc, kind, settings, references=()):
    obj = doc.addObject('App::FeaturePython', kind+'Analysis')
    obj.Label = kind+' Analysis'
    Analysis(obj, kind, settings, references)
    if App.GuiUp:
        import fusionflow_analysis_view as view
        view.AnalysisView(obj.ViewObject)
        obj.ViewObject.Visibility=False
    return obj
