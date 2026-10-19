"""Saved membership and in-place editing of native multi-body Pockets.

Metadata is deliberately not a document link: mutual links between Pockets in
different Bodies would introduce recompute cycles. Native features own all
geometry dependencies; the JSON only identifies the shared editing operation.
"""
import json
import uuid

from fusionflow_core import body_of, extrude


DEFAULTS = dict(length=10, length2=10, direction='One side', reverse=False,
                start=0, taper=0, taper2=0, extent='Distance', end_face=None, end_offset=0)


def link_value(value):
    return [value[0].Name, list(value[1])] if value and value[0] else None


def native_state(feature):
    """Detect native edits rather than silently replacing expressions/settings."""
    profile = feature.Profile[0]
    state = {name:str(getattr(feature, name)) for name in (
        'Length', 'Length2', 'SideType', 'Reversed', 'TaperAngle', 'TaperAngle2',
        'Type', 'Type2', 'Offset', 'Offset2', 'Suppressed', 'AlongSketchNormal',
        'UseCustomVector', 'ReferenceAxis', 'Refine', 'AllowMultiFace',
        'ExpressionEngine')}
    state.update(base=feature.BaseFeature.Name, profile=link_value(feature.Profile),
                 end=link_value(feature.UpToFace), end2=link_value(feature.UpToFace2))
    if feature.UseCustomVector:
        state['Direction'] = str(feature.Direction)
    if profile.TypeId == 'PartDesign::SubShapeBinder':
        # Placement may be driven by upstream geometry; compare its expression
        # and offset, not the resulting transform which is meant to follow it.
        state['binder'] = dict(support=[link_value(s) for s in profile.Support],
                              offset=profile.StartOffset.Value,
                              expressions=str(profile.ExpressionEngine))
    return state


def save_group(doc, data):
    members = [doc.getObject(name) for name in data['members'].values()]
    data['states'] = {f.Name:native_state(f) for f in members}
    value = json.dumps(data, ensure_ascii=False, sort_keys=True)
    for feature in members:
        if 'FusionFlowCut' not in feature.PropertiesList:
            feature.addProperty('App::PropertyString', 'FusionFlowCut', 'FusionFlow',
                                'Shared Extrude Cut editor data; native Pocket owns the geometry.')
            feature.setEditorMode('FusionFlowCut', 2)
        feature.FusionFlowCut = value


def remember_cut(source, regions, bases, targets, results, options):
    settings = dict(DEFAULTS, **options)
    settings['end_face'] = link_value(settings['end_face'])
    data = dict(version=1, id=uuid.uuid4().hex, source=source.Name, regions=list(regions),
                bases=bases, selected=[o.Name for o in targets], options=settings,
                members={body_of(f).Name:f.Name for f in results})
    save_group(source.Document, data)


def read_group(feature):
    value = getattr(feature, 'FusionFlowCut', '')
    if not value:
        return None
    try:
        data = json.loads(value)
        if data['version'] != 1 or feature.Name not in data['members'].values():
            raise ValueError()
        doc = feature.Document
        if not doc.getObject(data['source']):
            raise ValueError()
        for body_name, name in data['members'].items():
            member = doc.getObject(name)
            if (not member or member.TypeId != 'PartDesign::Pocket' or
                    body_of(member).Name != body_name or member.FusionFlowCut != value):
                raise ValueError()
            if native_state(member) != data['states'][name]:
                raise ValueError('Operace byla změněna mimo společný editor. Použij Upravit nativní Pocket; společná editace by přepsala ruční změny.')
        return data
    except (KeyError, TypeError, AttributeError, ValueError) as error:
        raise ValueError(str(error) or 'Chybí část společného řezu nebo jeho uložené údaje. Použij Upravit nativní Pocket.') from error


def edit_cut(feature, selected, **options):
    """Caller owns the transaction and must abort on failure, as for creation."""
    data = read_group(feature)
    if not data:
        raise ValueError('Tento řez nemá uloženou společnou historii.')
    doc = feature.Document
    selected = list(dict.fromkeys(selected))
    if not selected:
        raise ValueError('Nejsou vybraná žádná tělesa k odebrání. Zaškrtni je v Objects To Cut.')
    settings = dict(data['options'], **options)
    settings['end_face'] = link_value(options['end_face']) if 'end_face' in options else settings['end_face']
    if any(settings[k] != data['options'][k] for k in ('start', 'end_face')):
        raise ValueError('Společná editace zachovává původní profil, počátek a koncovou stěnu.')
    if settings['extent'] == 'Distance' and (settings['length'] <= 0 or
            (settings['direction'] == 'Two sides' and settings['length2'] <= 0)):
        raise ValueError('Vzdálenost musí být kladná.')
    if settings['extent'] != 'Distance' and settings['direction'] != 'One side':
        raise ValueError('Pro To object / All zvol One side.')
    if settings['extent'] == 'To object' and not settings['end_face']:
        raise ValueError('Řez nemá původní koncovou stěnu pro To Object.')
    for name in selected:
        body = doc.getObject(name)
        base = doc.getObject(data['bases'].get(name, ''))
        if not body or not base or body.TypeId != 'PartDesign::Body' or base not in body.Group:
            raise ValueError('Původní těleso nebo jeho výchozí krok už neexistuje: ' + name)
    source = doc.getObject(data['source'])
    native_options = dict(settings)
    end = settings['end_face']
    native_options['end_face'] = (doc.getObject(end[0]), end[1]) if end else None
    visibility = {o.Name:o.Visibility for o in doc.Objects if hasattr(o, 'Visibility')}
    invalid_before = {o.Name for o in doc.Objects if 'Invalid' in o.State}
    results = []
    for body_name, name in data['members'].items():
        member = doc.getObject(name)
        member.Length = settings['length']
        member.Length2 = settings['length2']
        member.SideType = settings['direction']
        member.Reversed = not settings['reverse']
        member.TaperAngle = settings['taper']
        member.TaperAngle2 = settings['taper2']
        member.Type = {'Distance':'Length', 'All':'ThroughAll', 'To object':'UpToFace'}[settings['extent']]
        if settings['extent'] == 'To object':
            member.UpToFace = native_options['end_face']
        member.Offset = settings['end_offset']
        member.Suppressed = body_name not in selected
    doc.recompute()
    for body_name in selected:
        body = doc.getObject(body_name)
        if body_name in data['members']:
            member = doc.getObject(data['members'][body_name])
        else:
            base = doc.getObject(data['bases'][body_name])
            old_tip, old_compound = body.Tip, body.AllowCompound
            before = {o.Name for o in doc.Objects}
            # newObject inserts after Tip and rewires the next native feature.
            # Do not call insertObject on an object already in the Body.
            body.Tip = base
            member = extrude(source, data['regions'], 'Cut', body, **native_options)
            if base.Shape.Volume-member.Shape.Volume <= max(1e-7, base.Shape.Volume*1e-10):
                body.Tip = old_tip
                for obj in reversed(doc.Objects):
                    if obj.Name not in before:
                        doc.removeObject(obj.Name)
                body.AllowCompound = old_compound
                doc.recompute()
                continue
            data['members'][body_name] = member.Name
            if old_tip != base:
                body.Tip = old_tip
                member.Visibility = False
            else:
                visible = visibility.get(base.Name, True)
                visibility[base.Name] = False
                member.Visibility = visible
        base = member.BaseFeature
        if base.Shape.Volume-member.Shape.Volume > max(1e-7, base.Shape.Volume*1e-10):
            results.append(member)
    doc.recompute()
    invalid = [o.Label for o in doc.Objects if 'Invalid' in o.State and o.Name not in invalid_before]
    if invalid:
        raise ValueError('Změna by poškodila navazující operace: ' + ', '.join(invalid) + '. Uprav rozměr nebo výběr těles.')
    if not results:
        raise ValueError('Vysunutí neprotíná žádné vybrané těleso. Změň výběr, vzdálenost nebo směr.')
    data['selected'], data['options'] = selected, settings
    save_group(doc, data)
    for name, visible in visibility.items():
        obj = doc.getObject(name)
        if obj:
            obj.Visibility = visible
    return results
