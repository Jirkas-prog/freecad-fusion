"""Read-only model diagnostics and navigation shared by browser and history."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore as C, QtWidgets as W
import fusionflow_icons as icons

CHECKS = (
    ('ConflictingConstraints', 2, 'Konfliktní vazby', 'Sketcher_SelectConflictingConstraints'),
    ('MalformedConstraints', 2, 'Neplatné vazby', 'Sketcher_SelectMalformedConstraints'),
    ('RedundantConstraints', 1, 'Nadbytečné vazby', 'Sketcher_SelectRedundantConstraints'),
    ('PartiallyRedundantConstraints', 1, 'Částečně nadbytečné vazby', 'Sketcher_SelectPartiallyRedundantConstraints'),
)


def diagnostics(obj):
    """Only cached solver results: inspecting a tree must never solve the sketch."""
    level = 2 if 'Invalid' in obj.State else 0
    notes = []
    if obj.TypeId == 'Sketcher::SketchObject':
        for attr, severity, label, command in CHECKS:
            findings = getattr(obj, attr)
            if findings:
                level = max(level, severity)
                notes.append('%s (%d)' % (label, len(findings)))
        if obj.DoF < 0 and not notes:
            level = 2
            notes.append('Skicu nelze vyřešit')
    if 'Invalid' in obj.State:
        notes.append(obj.getStatusString().strip() or 'Přepočet objektu selhal')
    return level, tuple(dict.fromkeys(notes))


def tooltip(obj, result=None):
    level, notes = diagnostics(obj) if result is None else result
    text = obj.Label + ' · ' + obj.TypeId + '\n' + obj.Document.Name + '#' + obj.Name
    if notes:
        text += '\n' + '\n'.join(notes)
    elif obj.TypeId == 'Sketcher::SketchObject':
        text += '\n' + ('Prázdná skica' if not obj.GeometryCount else
                        'Plně zavazbená skica' if obj.DoF == 0 else 'Stupně volnosti: %d' % obj.DoF)
    return text


def key(obj):
    return obj.Document.Name, obj.Name


def resolve(identity):
    doc = App.listDocuments().get(identity[0])
    return doc.getObject(identity[1]) if doc else None


def relations(obj):
    """Immediate dependencies, excluding ownership and origin scaffolding."""
    excluded = {'PartDesign::Body', 'App::Part', 'App::DocumentObjectGroup',
                'App::Origin', 'App::Line', 'App::Plane', 'App::Point'}
    inputs = [o for o in obj.OutList if o.TypeId not in excluded]
    if obj.TypeId == 'PartDesign::Body':
        inputs = [obj.Tip] if obj.Tip else []
    outputs = [o for o in obj.InList if o.TypeId not in excluded]
    return inputs, outputs


def can_edit(obj):
    active = Gui.activeDocument()
    editing = active.getInEdit() if active else None
    return bool(editing and editing.Object == obj) or not (editing or Gui.Control.activeDialog())


def reveal(identity):
    obj = resolve(identity)
    if not obj:
        return None
    if App.ActiveDocument != obj.Document:
        if Gui.Control.activeDialog() or (Gui.activeDocument() and Gui.activeDocument().getInEdit()):
            return None
        App.setActiveDocument(obj.Document.Name)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(obj)
    import fusionflow_ui as ui
    if ui._timeline:
        ui._timeline.refresh()
        for i in range(ui._timeline.list.count()):
            item = ui._timeline.list.item(i)
            if item.data(C.Qt.UserRole) == obj.Name:
                ui._timeline.list.setCurrentItem(item)
                ui._timeline.list.scrollToItem(item)
                break
    import fusionflow_browser as browser
    if browser._browser:
        b = browser._browser
        b.sync()
        from fusionflow_core import body_of
        owner = body_of(obj)
        item = b.items.get(key(obj)) or (b.items.get(key(owner)) if owner else None)
        if item:
            parent = item.parent()
            while parent:
                parent.setExpanded(True);parent = parent.parent()
            b.tree.scrollToItem(item)
    return obj


def edit_diagnostic(identity, command=None):
    obj = resolve(identity)
    if not obj or not can_edit(obj):
        return
    import fusionflow_ui as ui
    if ui._timeline:
        ui._timeline.end_preview()
    reveal(identity)
    active = Gui.activeDocument()
    if not active.getInEdit():
        from fusionflow_core import body_of
        owner = body_of(obj)
        if owner:
            active.activeView().setActiveObject('pdbody', owner)
        try:
            if ui.edit_feature(obj):
                return
        except Exception as error:
            App.Console.PrintWarning(str(error) + '\n')
    if obj.TypeId == 'Sketcher::SketchObject' and active.getInEdit() and active.getInEdit().Object == obj:
        import fusionflow_sketch as sketch
        if sketch._manager:
            sketch._manager.update()
            sketch._manager.palette.details.setChecked(True)
        if command:
            Gui.runCommand(command)
    else:
        import fusionflow_browser as browser
        if browser._browser:
            browser._browser.props.setChecked(True)


def add_diagnostics(menu, obj):
    level, notes = diagnostics(obj)
    if not level:
        return
    identity = key(obj)
    action = menu.addAction(icons.icon('status_error' if level == 2 else 'status_warning', True),
                            'Otevřít diagnostiku', lambda: edit_diagnostic(identity))
    action.setToolTip('\n'.join(notes));action.setEnabled(can_edit(obj))
    if obj.TypeId == 'Sketcher::SketchObject':
        for attr, severity, label, command in CHECKS:
            if getattr(obj, attr):
                action = menu.addAction('Vybrat: ' + label.lower(),
                                        lambda checked=False, c=command: edit_diagnostic(identity, c))
                action.setEnabled(can_edit(obj))
    menu.addSeparator()


def add_relations(menu, obj):
    inputs, outputs = relations(obj)
    groups = [('Vstupy', inputs), ('Použito v', outputs)]
    if obj.TypeId == 'PartDesign::Body':
        groups[0] = ('Poslední operace', inputs)
        groups.append(('Operace tělesa', [o for o in obj.Group if o.isDerivedFrom('PartDesign::Feature')]))
    for title, objects in groups:
        if not objects:
            continue
        sub = W.QMenu(title, menu)
        menu.addMenu(sub)
        for linked in objects:
            identity = key(linked)
            action = sub.addAction(icons.feature_icon(linked), linked.Label,
                                   lambda checked=False, k=identity: reveal(k))
            action.setToolTip(tooltip(linked));action.setData(identity)
        sub.setToolTipsVisible(True)
