"""Small UI layer; all saved modelling features remain native FreeCAD features."""
from pathlib import Path
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets as W
from fusionflow_core import extrude, cut_all, combine, body_of, suggest_operation, profile_anchor
import fusionflow_icons as icons
import fusionflow_inspect as inspect

ROOT = Path(__file__).parent
PREF = 'User parameter:BaseApp/Preferences/Mod/FusionFlow'
_installed = False
_panel = None
_timeline = None
_bars = []
_shortcuts = []


def selection():
    result = []
    for entry in Gui.Selection.getSelectionEx():
        if not entry.SubElementNames:
            result.append((entry.Object, ''))
        for name in entry.SubElementNames:
            obj = entry.Object
            parts = name.split('.')
            for token in parts[:-1]:
                candidate = obj.Document.getObject(token)
                if candidate:
                    obj = candidate
            result.append((obj, parts[-1]))
    return result


def create_sketch():
    """Let a preselected solid face choose its Body, then use native attachment."""
    picks = selection()
    if len(picks) == 1 and picks[0][1].startswith('Face'):
        owner = body_of(picks[0][0])
        if owner and owner.TypeId == 'PartDesign::Body':
            Gui.activeDocument().activeView().setActiveObject('pdbody', owner)
    Gui.runCommand('PartDesign_NewSketch')


def combo(items):
    c = W.QComboBox()
    for label, data in items:
        c.addItem(label, data)
    return c


def number(value=0, angle=False):
    w = W.QDoubleSpinBox()
    w.setRange(-89 if angle else -1000000, 89 if angle else 1000000)
    w.setDecimals(3)
    w.setValue(value)
    w.setSuffix(' °' if angle else ' mm')
    w.setKeyboardTracking(False)
    w.setButtonSymbols(W.QAbstractSpinBox.NoButtons)
    return w


def selected_name(widget, name):
    index = widget.findData(name)
    if index >= 0:
        widget.setCurrentIndex(index)


def cad_icon(name):
    return icons.icon(name,True)


class PickField(W.QWidget):
    """Compact viewport selection plus an accessible list fallback."""
    def __init__(self, choose, clear, menu=None):
        super().__init__()
        layout = W.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        self.button = W.QToolButton()
        self.button.setObjectName('SelectionChip')
        self.button.setCheckable(True)
        self.button.setIcon(cad_icon('select'))
        self.button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.button.clicked.connect(choose)
        layout.addWidget(self.button)
        self.clear = W.QToolButton()
        self.clear.setText('×')
        self.clear.setToolTip('Clear selection / Vymazat výběr')
        self.clear.clicked.connect(clear)
        layout.addWidget(self.clear)
        if menu:
            from fusionflow_ribbon import MENU_STYLE
            menu.setStyleSheet(MENU_STYLE)
            more = W.QToolButton()
            more.setText('⌄')
            more.setToolTip('Vybrat ze seznamu')
            more.setMenu(menu)
            more.setPopupMode(W.QToolButton.InstantPopup)
            layout.addWidget(more)
        layout.addStretch()
        self.update_count(0)

    def update_count(self, count, names=''):
        self.button.setText('%d selected' % count if count else 'Select')
        self.button.setToolTip(names or 'Vyber kliknutím v modelu')
        self.clear.setVisible(bool(count))


class OperationCard(W.QFrame):
    def __init__(self, title):
        super().__init__(Gui.getMainWindow())
        self.setObjectName('FusionOperationCard')
        self.setWindowTitle(title)
        self.setFixedWidth(292)
        self.setAttribute(QtCore.Qt.WA_StyledBackground)
        self.setStyleSheet('''
        #FusionOperationCard {background:#394352;border:1px solid #596577;}
        #FusionOperationCard QWidget {font:12px "Segoe UI";color:#e7edf5;background:transparent;}
        #FusionOperationCard QLineEdit, #FusionOperationCard QAbstractSpinBox,
        #FusionOperationCard QComboBox {background:#2c3542;border:0;border-radius:0;padding:4px;min-height:18px;}
        #FusionOperationCard QComboBox::drop-down {border:0;width:18px;}
        #FusionOperationCard QComboBox QAbstractItemView {background:#454f60;color:#eff3fa;selection-background-color:#536d88;}
        #FusionOperationCard QToolButton {border:1px solid transparent;padding:3px;background:transparent;}
        #FusionOperationCard QToolButton:hover {background:#50667d;}
        #FusionOperationCard QToolButton:checked {background:#42657c;border:1px solid #6da9cc;}
        #FusionOperationCard QToolButton#SelectionChip {border:1px solid #6b7d91;}
        #FusionOperationCard QPushButton {border:1px solid #728097;padding:4px 12px;min-width:36px;background:#3e4b5d;}
        #FusionOperationCard QPushButton:hover {background:#50667d;}
        #FusionOperationCard QPushButton:disabled {color:#788595;border-color:#536071;}
        #FusionOperationCard QCheckBox::indicator {width:13px;height:13px;}
        #FusionOperationCard QScrollArea {border:0;}
        #FusionOperationCard QScrollBar:vertical {width:5px;background:#303946;}
        #FusionOperationCard QScrollBar::handle:vertical {background:#65758a;min-height:20px;}
        ''')
        self.hide()

    def place(self):
        main = Gui.getMainWindow()
        mdi = main.findChild(W.QMdiArea)
        cube = App.ParamGet('User parameter:BaseApp/Preferences/NaviCube').GetInt('CubeSize', 132)
        top = mdi.mapTo(main, QtCore.QPoint(0, 0)).y() + max(58, cube+12) if mdi else 170
        available = max(180, main.height() - top - 55)
        scroll = self.findChild(W.QScrollArea)
        if scroll:
            scroll.setFixedHeight(min(scroll.widget().layout().sizeHint().height()+10, max(80, available-90)))
        self.layout().activate()
        self.resize(self.width(), min(self.sizeHint().height(), available))
        self.move(max(0, main.width() - self.width() - 14), top)
        self.raise_()

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.Resize:
            self.place()
        return False


class TaskController:
    """FreeCAD retains document locking and Escape/cancel; the card supplies UI."""
    form = []

    def __init__(self, panel):
        self.panel = panel

    def accept(self):
        return self.panel.accept()

    def reject(self):
        return self.panel.reject()

    def getStandardButtons(self):
        return 0

    def isAllowedAlterDocument(self):
        return False

    def isAllowedAlterSelection(self):
        return True

    def isAllowedAlterView(self):
        return True


class Panel:
    def __init__(self, title):
        self.doc = App.ActiveDocument
        self.doc.UndoMode = 1
        self.original = {o.Name: (o.Visibility, getattr(o.ViewObject, 'Transparency', None))
                         for o in self.doc.Objects if hasattr(o, 'Visibility')}
        self.original_internals = {o.Name: o.MakeInternals for o in self.doc.Objects if o.TypeId == 'Sketcher::SketchObject'}
        self.form = OperationCard(title)
        self.layout = W.QVBoxLayout(self.form)
        self.layout.setContentsMargins(10, 6, 10, 8)
        self.layout.setSpacing(7)
        heading = W.QLabel('−  ' + title)
        heading.setStyleSheet('font-size:11px;letter-spacing:1px;padding-bottom:4px;border-bottom:1px solid #485466;')
        self.layout.addWidget(heading)
        self.scroll = W.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.content = W.QWidget()
        content_layout = W.QVBoxLayout(self.content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        self.fields = W.QFormLayout()
        self.fields.setFieldGrowthPolicy(W.QFormLayout.AllNonFixedFieldsGrow)
        self.fields.setHorizontalSpacing(8)
        self.fields.setVerticalSpacing(5)
        self.fields.setLabelAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        content_layout.addLayout(self.fields)
        self.scroll.setWidget(self.content)
        self.layout.addWidget(self.scroll)
        self.message = W.QLabel()
        self.message.setWordWrap(True)
        self.layout.addWidget(self.message)
        self.message.hide()
        footer = W.QHBoxLayout()
        self.info = W.QLabel('ⓘ')
        footer.addWidget(self.info)
        footer.addStretch()
        self.ok = W.QPushButton('OK')
        self.ok.setEnabled(False)
        self.ok.clicked.connect(self.accept)
        cancel = W.QPushButton('Cancel')
        cancel.clicked.connect(self.reject)
        footer.addWidget(self.ok)
        footer.addWidget(cancel)
        self.layout.addLayout(footer)
        self.timer = QtCore.QTimer(self.form)
        self.timer.setSingleShot(True)
        self.timer.setInterval(220)
        self.timer.timeout.connect(self.preview)
        self.transaction = False
        self.transaction_id = None
        self.result = None
        self.closed = False
        self.busy = False
        self.controller = TaskController(self)
        self.escape = QtGui.QShortcut(QtGui.QKeySequence('Esc'), self.form)
        self.escape.setContext(QtCore.Qt.ApplicationShortcut)
        self.escape.activated.connect(self.reject)

    def show(self):
        Gui.Control.showDialog(self.controller)
        tasks = Gui.getMainWindow().findChild(W.QDockWidget, 'Tasks')
        if tasks:
            tasks.hide()
        Gui.getMainWindow().installEventFilter(self.form)
        self.form.show()
        self.update_layout()

    def update_layout(self):
        self.fields.invalidate()
        self.content.layout().activate()
        self.form.layout().activate()
        self.form.place()

    def row(self, label, widget):
        self.fields.addRow(label, widget)
        if isinstance(widget, W.QComboBox):
            widget.currentIndexChanged.connect(self.schedule)
        elif isinstance(widget, W.QAbstractSpinBox):
            widget.valueChanged.connect(self.schedule)
        elif isinstance(widget, W.QCheckBox):
            widget.toggled.connect(self.schedule)
        return widget

    def schedule(self, *_):
        if not self.closed and not self.busy:
            self.timer.start()

    def restore_visibility(self):
        for name, (visible, transparency) in self.original.items():
            obj = self.doc.getObject(name)
            if obj:
                obj.Visibility = visible
                if transparency is not None:
                    obj.ViewObject.Transparency = transparency

    def rollback(self):
        if self.transaction:
            active=App.getActiveTransaction()
            if active and active[1]==self.transaction_id:
                # Document.abortTransaction alone leaves an *empty* application
                # transaction open. Restoring visibility would then create a
                # new undo step after a failed/zero-target preview.
                App.closeActiveTransaction(True)
            else:
                self.doc.abortTransaction()
            self.transaction = False
            self.transaction_id = None
            # Undo restores shapes/properties, but a failed downstream feature
            # can retain its Invalid flag until the restored graph recomputes.
            self.doc.recompute()
        self.result = None
        self.restore_visibility()

    def preview(self):
        if self.closed or App.ActiveDocument != self.doc:
            return
        self.busy = True
        try:
            self.rollback()
            self.doc.openTransaction(self.form.windowTitle())
            self.transaction = True
            self.transaction_id = App.getActiveTransaction()[1]
            self.result = self.build()
            self.message.setText('Náhled je platný. OK uloží operaci, Cancel ji zruší.')
            self.message.hide()
        except Exception as exc:
            self.rollback()
            self.message.setStyleSheet('color:#f2bb82')
            self.message.setText(str(exc))
            self.message.setVisible(not str(exc).startswith(('Vyber', 'Nejprve', 'Vzdálenost musí')))
        finally:
            self.busy = False
            self.ok.setEnabled(self.result is not None)
            self.info.setToolTip(self.message.text())
            self.update_layout()

    def accept(self):
        if self.closed:
            return False
        self.timer.stop()
        self.preview()
        if self.result is None:
            return False
        self.doc.commitTransaction()
        self.transaction = False
        self.transaction_id = None
        owner = body_of(self.result[0] if isinstance(self.result, list) else self.result)
        if owner:
            Gui.activeDocument().activeView().setActiveObject('pdbody', owner)
        Gui.Selection.clearSelection()
        self.finish()
        return True

    def reject(self):
        if self.closed:
            return True
        self.timer.stop()
        self.rollback()
        for name, value in self.original_internals.items():
            obj = self.doc.getObject(name)
            if obj:
                obj.MakeInternals = value
        self.doc.recompute()
        self.finish()
        return True

    def finish(self):
        global _panel
        self.closed = True
        self.escape.setEnabled(False)
        Gui.getMainWindow().removeEventFilter(self.form)
        self.form.hide()
        Gui.Control.closeDialog()
        tasks = Gui.getMainWindow().findChild(W.QDockWidget, 'Tasks')
        if tasks:
            tasks.hide()
        _panel = None
        self.form.deleteLater()
        if _timeline:
            _timeline.refresh(force=True)

    def getStandardButtons(self):
        return (W.QDialogButtonBox.Ok | W.QDialogButtonBox.Cancel).value

    def isAllowedAlterDocument(self):
        return False

    def isAllowedAlterSelection(self):
        return True

    def isAllowedAlterView(self):
        return True


class ExtrudePanel(Panel):
    def __init__(self, edit_feature=None):
        from fusionflow_cut_history import read_group
        self.edit_name = edit_feature.Name if edit_feature else None
        self.edit_data = read_group(edit_feature) if edit_feature else None
        super().__init__('EDIT EXTRUDE · CUT' if edit_feature else 'EXTRUDE')
        self.pick_mode = 'profiles'
        self.face_source = None
        self.face_names = []
        picks = selection()
        sketches = [o for o in self.doc.Objects if o.TypeId == 'Sketcher::SketchObject']
        self.sketch = combo([(o.Label, o.Name) for o in sketches])
        self.sketch.setParent(self.form)
        self.sketch.hide()
        self.regions = W.QListWidget(self.form)
        self.regions.hide()
        kind = W.QWidget()
        self.kind_field = kind
        kinds = W.QHBoxLayout(kind)
        kinds.setContentsMargins(0, 0, 0, 0)
        for name, label in [('extrude', 'Solid'), ('shell', 'Thin Extrude')]:
            button = W.QToolButton()
            button.setIcon(cad_icon(name))
            button.setCheckable(True)
            button.setChecked(label == 'Solid')
            button.setEnabled(label == 'Solid')
            button.setToolTip(label if label == 'Solid' else 'Thin Extrude zatím není implementováno.')
            kinds.addWidget(button)
        kinds.addStretch()
        self.fields.addRow('Type', kind)
        self.profile_menu = W.QMenu()
        self.profile_menu.aboutToShow.connect(self.profiles_menu)
        self.pick = PickField(self.pick_profiles, self.clear_profiles, self.profile_menu)
        self.fields.addRow('Profiles', self.pick)
        self.start = self.row('Start', combo([('Profile Plane', 'plane'), ('Offset', 'offset')]))
        self.offset = self.row('Start offset', number())
        self.direction = self.row('Direction', combo([(label, data) for label, data in [('One Side','One side'), ('Two Sides','Two sides'), ('Symmetric','Symmetric')]]))
        self.reverse = W.QCheckBox(self.form)
        self.reverse.hide()
        self.reverse.toggled.connect(self.schedule)
        self.extent = self.row('Extent Type', combo([('Distance','Distance'), ('To Object','To object'), ('All','All')]))
        self.distance = self.row('Distance', number(0))
        self.distance.setToolTip('Záporná vzdálenost otočí směr vysunutí.')
        self.distance2 = self.row('Distance 2', number(0))
        self.taper = self.row('Taper Angle', number(0, True))
        self.taper2 = self.row('Taper Angle 2', number(0, True))
        for field in (self.taper,self.taper2):
            field.setToolTip('Úkos: kladný úhel rozšiřuje profil, záporný jej zužuje. Pro Distance lze úhel měnit i kruhovým úchopem na oblouku u šipky.')
        self.end = None
        self.end_button = PickField(self.pick_end, self.clear_end)
        self.fields.addRow('To object', self.end_button)
        self.end_offset = self.row('End offset', number())
        self.operation = combo([('New Body','New body'), ('Join','Join'), ('Cut','Cut'), ('Intersect','Intersect')])
        operation_row = W.QWidget()
        operation_layout = W.QHBoxLayout(operation_row)
        operation_layout.setContentsMargins(0,0,0,0)
        operation_layout.setSpacing(5)
        operation_layout.addWidget(self.operation,1)
        self.auto_operation = W.QCheckBox('Auto')
        self.auto_operation.setChecked(True)
        self.auto_operation.setToolTip('Automaticky: průnik → Cut, společná stěna → Join, jinak New Body. Ruční výběr automatiku vypne.')
        self.auto_operation.toggled.connect(self.schedule)
        operation_layout.addWidget(self.auto_operation)
        self.fields.addRow('Operation',operation_row)
        for index, name in enumerate(('box','boolean_join','boolean_cut','boolean_intersect')):
            self.operation.setItemIcon(index, cad_icon(name))
        bodies = [o for o in self.doc.Objects if o.TypeId == 'PartDesign::Body' and o.Tip and o.Shape.Solids]
        self.target = combo([('Select', ''), ('All bodies', '__all__')]+[(o.Label, o.Name) for o in bodies])
        self.target.setParent(self.form)
        self.target.hide()
        self.target.currentIndexChanged.connect(self.target_changed)
        self.target_menu = W.QMenu()
        self.target_menu.aboutToShow.connect(self.targets_menu)
        self.target_pick = PickField(lambda:self.begin_pick('target'), lambda:self.target.setCurrentIndex(0), self.target_menu)
        self.fields.addRow('Target Body', self.target_pick)
        self.cut_affected = None
        self.cut_section = W.QWidget()
        cut_layout = W.QVBoxLayout(self.cut_section)
        cut_layout.setContentsMargins(0,4,0,0);cut_layout.setSpacing(4)
        self.cut_header = W.QToolButton()
        self.cut_header.setObjectName('ObjectsToCut')
        self.cut_header.setText('Objects To Cut')
        self.cut_header.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.cut_header.setArrowType(QtCore.Qt.RightArrow);self.cut_header.setCheckable(True)
        self.cut_header.setStyleSheet('QToolButton {border:0;font-weight:600;} QToolButton:checked {background:transparent;border:0;}')
        self.cut_header.setToolTip('Rozbalit seznam těles. Odškrtni tělesa, která má řez vynechat.')
        cut_layout.addWidget(self.cut_header)
        self.cut_details = W.QWidget()
        details = W.QVBoxLayout(self.cut_details);details.setContentsMargins(0,0,0,0);details.setSpacing(3)
        controls = W.QHBoxLayout()
        for label,checked in [('All',True),('None',False)]:
            button=W.QToolButton();button.setText(label);button.setObjectName('CutSelect'+label)
            button.setToolTip('Zaškrtnout všechna tělesa' if checked else 'Odškrtnout všechna tělesa')
            button.clicked.connect(lambda _,on=checked:self.select_cut_bodies(on));controls.addWidget(button)
        controls.addStretch();details.addLayout(controls)
        self.cut_list = W.QListWidget();self.cut_list.setObjectName('ObjectsToCutList')
        self.cut_list.setSelectionMode(W.QAbstractItemView.NoSelection)
        self.cut_list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.cut_list.setTextElideMode(QtCore.Qt.ElideRight)
        self.cut_list.setIconSize(QtCore.QSize(16,16))
        self.cut_list.setStyleSheet('QListWidget {background:#303a48;border:1px solid #596577;} QListWidget::item {padding:4px;}')
        for body in bodies:
            label=body.Label if sum(o.Label==body.Label for o in bodies)==1 else body.Label+' ['+body.Name+']'
            entry=W.QListWidgetItem(cad_icon('body'),label,self.cut_list)
            entry.setData(QtCore.Qt.UserRole,body.Name)
            entry.setData(QtCore.Qt.UserRole+1,label)
            entry.setFlags(entry.flags() | QtCore.Qt.ItemIsUserCheckable)
            entry.setCheckState(QtCore.Qt.Checked)
        self.cut_list.setFixedHeight(max(32,min(5,len(bodies))*30+4))
        details.addWidget(self.cut_list);cut_layout.addWidget(self.cut_details);self.cut_details.hide()
        self.cut_status = W.QLabel();self.cut_status.setWordWrap(True)
        self.cut_status.setStyleSheet('color:#b9c8d8;font-size:11px;')
        cut_layout.addWidget(self.cut_status)
        self.fields.addRow(self.cut_section)
        self.cut_section.hide()
        self.cut_header.toggled.connect(self.expand_cut_bodies)
        self.cut_list.itemChanged.connect(self.cut_selection_changed)
        self.operation.currentIndexChanged.connect(self.operation_changed)
        self.regions.itemChanged.connect(self.profiles_changed)
        self.sketch.currentIndexChanged.connect(self.load_regions)
        for obj, sub in picks:
            if obj.TypeId == 'Sketcher::SketchObject':
                selected_name(self.sketch, obj.Name)
                owner = body_of(obj)
                if owner and owner in bodies:
                    selected_name(self.target, owner.Name)
                    selected_name(self.operation, 'Join')
                break
        self.load_regions()
        chosen = [int(sub[len('InternalFace'):]) for obj, sub in picks
                  if obj.Name == self.sketch.currentData() and sub.startswith('InternalFace')]
        if chosen:
            for i in range(self.regions.count()):
                self.regions.item(i).setCheckState(QtCore.Qt.Checked if i + 1 in chosen else QtCore.Qt.Unchecked)
        faces = [(obj, sub) for obj, sub in picks if obj.TypeId != 'Sketcher::SketchObject' and sub.startswith('Face')]
        if faces:
            obj = faces[0][0]
            self.set_faces(obj, [sub for source, sub in faces if source == obj])
            owner = body_of(obj)
            if owner and owner in bodies:
                selected_name(self.target, owner.Name)
                selected_name(self.operation, 'Join')
        Gui.Selection.addObserver(self)
        self.operation.currentIndexChanged.connect(self.manual_operation)
        self.target.currentIndexChanged.connect(self.manual_operation)
        from fusionflow_dragger import ExtrudeHandles
        self.handles = ExtrudeHandles(self)
        if self.edit_data:
            self.load_edit()
        self.sync_picks()
        self.schedule()

    def load_edit(self):
        self.busy = True
        self.timer.stop()
        data, options = self.edit_data, self.edit_data['options']
        source = self.doc.getObject(data['source'])
        if source.TypeId == 'Sketcher::SketchObject':
            selected_name(self.sketch, source.Name)
            self.load_regions()
            self.busy = True
            for i in range(self.regions.count()):
                self.regions.item(i).setCheckState(QtCore.Qt.Checked if i+1 in data['regions'] else QtCore.Qt.Unchecked)
        else:
            self.face_source, self.face_names = source.Name, data['regions']
        self.auto_operation.setChecked(False)
        selected_name(self.operation, 'Cut')
        selected_name(self.direction, options['direction'])
        selected_name(self.extent, options['extent'])
        selected_name(self.start, 'offset' if options['start'] else 'plane')
        self.distance.setValue(options['length'] * (-1 if options['reverse'] else 1))
        self.distance2.setValue(options['length2'])
        self.offset.setValue(options['start'])
        self.taper.setValue(options['taper']); self.taper2.setValue(options['taper2'])
        self.end_offset.setValue(options['end_offset'])
        self.end = (options['end_face'][0], options['end_face'][1][0]) if options['end_face'] else None
        # Keep original geometric references. Replacing a historical profile or
        # moving its binder needs a separate reference-remapping workflow.
        for widget in (self.pick, self.start, self.offset, self.end_button, self.operation, self.auto_operation):
            widget.setEnabled(False)
            widget.setToolTip('Společná editace zachovává původní profil, počátek, koncovou stěnu a operaci Cut.')
        if not self.end:
            self.extent.model().item(self.extent.findData('To object')).setEnabled(False)
        with QtCore.QSignalBlocker(self.cut_list):
            self.cut_list.clear()
            bodies = [self.doc.getObject(n) for n in data['bases']]
            bodies = [b for b in bodies if b and b.TypeId == 'PartDesign::Body']
            for body in bodies:
                label = body.Label if sum(b.Label==body.Label for b in bodies)==1 else body.Label+' ['+body.Name+']'
                entry = W.QListWidgetItem(cad_icon('body'), label, self.cut_list)
                entry.setData(QtCore.Qt.UserRole, body.Name)
                entry.setData(QtCore.Qt.UserRole+1, label)
                entry.setFlags(entry.flags() | QtCore.Qt.ItemIsUserCheckable)
                entry.setCheckState(QtCore.Qt.Checked if body.Name in data['selected'] else QtCore.Qt.Unchecked)
        self.cut_list.setFixedHeight(max(32,min(5,len(bodies))*30+4))
        self.cut_header.setChecked(True)
        self.fields.setRowVisible(self.kind_field, False)
        self.fields.setRowVisible(self.operation.parentWidget(), False)
        self.cut_header.setToolTip('Společná editace uloženého řezu. Odškrtnutí potlačí původní krok.\nSeznam obsahuje tělesa z doby vytvoření řezu, včetně původně vynechaných.')
        self.pick_mode = None
        self.busy = False

    def manual_operation(self, *_):
        if not self.busy:
            self.auto_operation.setChecked(False)
        self.schedule()

    def profile(self):
        if self.edit_data:
            return self.doc.getObject(self.edit_data['source']), self.edit_data['regions']
        source = self.doc.getObject(self.face_source or self.sketch.currentData() or '')
        regions = self.face_names if self.face_source else [i+1 for i in range(self.regions.count())
                    if self.regions.item(i).checkState() == QtCore.Qt.Checked]
        return source, regions

    def preview(self):
        super().preview()
        if not self.closed:
            self.cut_affected = {body_of(f).Name for f in self.result} if self.operation.currentData()=='Cut' and isinstance(self.result,list) else None
            self.sync_picks()
            self.update_layout()
            self.handles.sync()

    def expand_cut_bodies(self, expanded):
        self.cut_header.setArrowType(QtCore.Qt.DownArrow if expanded else QtCore.Qt.RightArrow)
        self.cut_details.setVisible(expanded)
        self.update_layout()

    def selected_cut_names(self):
        return [self.cut_list.item(i).data(QtCore.Qt.UserRole) for i in range(self.cut_list.count())
                if self.cut_list.item(i).checkState()==QtCore.Qt.Checked]

    def select_cut_bodies(self, checked):
        with QtCore.QSignalBlocker(self.cut_list):
            for i in range(self.cut_list.count()):
                self.cut_list.item(i).setCheckState(QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
        self.cut_selection_changed()

    def cut_selection_changed(self, *_):
        self.cut_affected=None
        self.manual_operation()
        self.sync_picks()

    def target_changed(self, *_):
        # Retain the single-target selection route for viewport picks and older
        # integrations; Auto changes this combo with signals blocked.
        if self.operation.currentData()=='Cut':
            target=self.target.currentData()
            with QtCore.QSignalBlocker(self.cut_list):
                for i in range(self.cut_list.count()):
                    entry=self.cut_list.item(i)
                    entry.setCheckState(QtCore.Qt.Checked if target=='__all__' or target==entry.data(QtCore.Qt.UserRole) else QtCore.Qt.Unchecked)
            self.cut_affected=None
        self.sync_picks()
        self.schedule()

    def profiles_menu(self):
        self.profile_menu.clear()
        for index in range(self.sketch.count()):
            sk = self.doc.getObject(self.sketch.itemData(index))
            menu = self.profile_menu.addMenu(sk.Label)
            action = menu.addAction('Use this sketch')
            action.triggered.connect(lambda checked=False, i=index:self.use_sketch(i))
            for face in range(len(sk.InternalShape.Faces)):
                action = menu.addAction('Profile %d' % (face+1))
                action.setCheckable(True)
                current = index == self.sketch.currentIndex()
                action.setChecked(current and self.regions.item(face).checkState() == QtCore.Qt.Checked)
                action.triggered.connect(lambda checked, si=index, fi=face:self.choose_profile(si, fi, checked))

    def use_sketch(self, index):
        if self.sketch.currentIndex() == index:
            self.load_regions()
        else:
            self.sketch.setCurrentIndex(index)
        self.sync_picks()

    def choose_profile(self, sketch_index, face_index, checked):
        self.face_source = None
        self.face_names = []
        self.sketch.setCurrentIndex(sketch_index)
        self.regions.item(face_index).setCheckState(QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
        self.profiles_changed()

    def set_faces(self, obj, names):
        self.timer.stop()
        self.busy = True
        self.rollback()
        source = obj.Tip if obj.TypeId == 'PartDesign::Body' else obj
        self.face_source = source.Name if source else None
        self.face_names = list(dict.fromkeys(names))
        self.busy = False
        self.sync_picks()
        self.schedule()

    def operation_changed(self, *_):
        if self.operation.currentData() == 'Cut':
            # Returning to Cut keeps deliberate exclusions from this dialog.
            with QtCore.QSignalBlocker(self.target):selected_name(self.target, '__all__')
        elif self.target.currentData() == '__all__':
            source = self.doc.getObject(self.face_source or self.sketch.currentData() or '')
            owner = body_of(source)
            self.target.setCurrentIndex(0)
            if owner:
                selected_name(self.target, owner.Name)
        self.sync_picks()
        self.schedule()

    def targets_menu(self):
        self.target_menu.clear()
        for i in range(1, self.target.count()):
            if self.target.itemData(i) == '__all__' and self.operation.currentData() != 'Cut':
                continue
            action = self.target_menu.addAction(self.target.itemText(i))
            action.triggered.connect(lambda checked=False, index=i:self.target.setCurrentIndex(index))

    def profiles_changed(self, *_):
        self.sync_picks()
        self.schedule()

    def sync_picks(self):
        count = len(self.face_names) if self.face_source else sum(self.regions.item(i).checkState() == QtCore.Qt.Checked for i in range(self.regions.count()))
        source = self.doc.getObject(self.face_source) if self.face_source else None
        self.pick.update_count(count, source.Label+' · '+', '.join(self.face_names) if source else self.sketch.currentText())
        self.pick.button.setChecked(self.pick_mode == 'profiles')
        self.target_pick.update_count(bool(self.target.currentData()), self.target.currentText())
        if self.target.currentData() == '__all__':
            self.target_pick.button.setText('All bodies')
            self.target_pick.button.setToolTip('Odebere ze všech protínaných Part Design těles v dokumentu, včetně skrytých.')
        self.target_pick.button.setChecked(self.pick_mode == 'target')
        self.end_button.update_count(bool(self.end), ' · '.join(self.end) if self.end else '')
        self.end_button.button.setChecked(self.pick_mode == 'end')
        cut=self.operation.currentData()=='Cut'
        self.fields.setRowVisible(self.target_pick,self.operation.currentData() in ('Join','Intersect'))
        self.cut_section.setVisible(cut)
        names=self.selected_cut_names()
        self.cut_header.setText('Objects To Cut · %d / %d'%(len(names),self.cut_list.count()))
        self.cut_status.setText(('Zasaženo %d z %d vybraných těles.'%(len(self.cut_affected),len(names)))
            if self.cut_affected is not None else 'Žádné těleso není vybrané.' if not names else 'Vybraná tělesa zahrnují i skrytá. Řez se provede jen při průniku.')
        with QtCore.QSignalBlocker(self.cut_list):
            for i in range(self.cut_list.count()):
                entry=self.cut_list.item(i);name=entry.data(QtCore.Qt.UserRole)
                label=entry.data(QtCore.Qt.UserRole+1)
                status='vynecháno' if name not in names else 'mimo řez' if self.cut_affected is not None and name not in self.cut_affected else ''
                entry.setText(label+(' · '+status if status else ''))
                entry.setForeground(QtGui.QColor('#9fadbd' if name not in names else '#e7edf5'))
                entry.setToolTip(label+'\n'+name+(' · původně skryté těleso' if not self.original.get(name,(True,))[0] else '')+'\n'+(status or 'Vybráno k odebrání'))

    def clear_profiles(self):
        self.face_source = None
        self.face_names = []
        for i in range(self.regions.count()):
            self.regions.item(i).setCheckState(QtCore.Qt.Unchecked)
        self.pick_profiles()
        self.schedule()

    def clear_end(self):
        self.end = None
        self.sync_picks()
        self.schedule()

    def begin_pick(self, mode):
        self.timer.stop()
        self.busy = True
        self.rollback()
        Gui.Selection.clearSelection()
        self.busy = False
        self.pick_mode = mode
        self.ok.setEnabled(False)
        self.sync_picks()

    def load_regions(self, *_):
        self.timer.stop()
        self.busy = True
        self.rollback()
        self.face_source = None
        self.face_names = []
        self.regions.clear()
        obj = self.doc.getObject(self.sketch.currentData() or '')
        if obj:
            # Enabling generated regions is a deliberate persistent sketch setting.
            obj.MakeInternals = True
            self.doc.recompute()
            count = len(obj.InternalShape.Faces)
            for i, face in enumerate(obj.InternalShape.Faces, 1):
                item = W.QListWidgetItem('Oblast %d   ·   %.1f mm²' % (i, face.Area), self.regions)
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.Checked if count == 1 else QtCore.Qt.Unchecked)
            self.message.setText('Klikni na uzavřenou oblast skici nebo ji zaškrtni v seznamu. Ctrl přidává oblasti.')
        self.busy = False
        self.schedule()

    def pick_profiles(self):
        self.begin_pick('profiles')
        obj = self.doc.getObject(self.face_source or self.sketch.currentData() or '')
        if not obj:
            return
        owner = body_of(obj)
        if owner:
            owner.Visibility = True
        obj.Visibility = True
        self.message.setText('Klikni na rovinnou stěnu nebo dovnitř oblasti skici. Ctrl přidává další výběr.')

    def addSelection(self, *_):
        if self.closed or self.busy or self.edit_name:
            return
        picks = selection()
        if not picks:
            return
        obj, sub = picks[-1]
        if obj.Document != self.doc or obj.Name not in self.original:
            return
        if self.pick_mode == 'profiles' and obj.TypeId == 'Sketcher::SketchObject' and sub.startswith('InternalFace'):
                self.face_source = None
                self.face_names = []
                selected_name(self.sketch, obj.Name)
                i = int(sub[len('InternalFace'):]) - 1
                if 0 <= i < self.regions.count():
                    self.regions.item(i).setCheckState(QtCore.Qt.Checked)
                self.profiles_changed()
        elif self.pick_mode == 'profiles' and sub.startswith('Face'):
            self.set_faces(obj, [name for selected, name in picks if selected == obj and name.startswith('Face')])
        elif self.pick_mode == 'target':
            owner = body_of(obj)
            if owner:
                selected_name(self.target, owner.Name)
                self.sync_picks()
        elif self.pick_mode == 'end' and sub.startswith('Face') and obj.TypeId != 'Sketcher::SketchObject':
            self.end = (obj.Name, sub)
            self.sync_picks()
            self.schedule()

    def pick_end(self):
        self.begin_pick('end')

    def build(self):
        two = self.direction.currentData() == 'Two sides'
        self.fields.setRowVisible(self.distance2, two)
        self.fields.setRowVisible(self.taper2, two)
        self.fields.setRowVisible(self.offset, self.start.currentData() == 'offset')
        to_face = self.extent.currentData() == 'To object'
        self.fields.setRowVisible(self.end_button, to_face)
        self.fields.setRowVisible(self.end_offset, to_face)
        self.fields.setRowVisible(self.distance, self.extent.currentData() == 'Distance')
        self.sync_picks()
        sk, regions = self.profile()
        if not sk:
            raise ValueError('Vyber rovinnou stěnu nebo uzavřenou oblast skici.')
        options = dict(length=abs(self.distance.value()), length2=self.distance2.value(), direction=self.direction.currentData(),
                       reverse=self.reverse.isChecked() != (self.distance.value() < 0),
                       start=self.offset.value() if self.start.currentData() == 'offset' else 0,
                       taper=self.taper.value(), taper2=self.taper2.value(), extent=self.extent.currentData(),
                       end_face=(self.doc.getObject(self.end[0]), [self.end[1]]) if self.end else None,
                       end_offset=self.end_offset.value())
        if self.edit_name:
            from fusionflow_cut_history import edit_cut
            return edit_cut(self.doc.getObject(self.edit_name), self.selected_cut_names(), **options)
        if self.auto_operation.isChecked() and (options['length']>0 or options['extent']!='Distance'):
            operation, target = suggest_operation(sk, regions, **options)
            self.operation.blockSignals(True)
            self.target.blockSignals(True)
            try:
                selected_name(self.operation, operation)
                selected_name(self.target, '__all__' if operation=='Cut' else target.Name if target else '')
            finally:
                self.operation.blockSignals(False)
                self.target.blockSignals(False)
        self.sync_picks()
        if self.operation.currentData() == 'Cut':
            targets=[self.doc.getObject(name) for name in self.selected_cut_names()]
            return cut_all(sk, regions, targets=targets, **options)
        return extrude(sk, regions, self.operation.currentData(), self.doc.getObject(self.target.currentData() or ''), **options)

    def finish(self):
        self.handles.close()
        Gui.Selection.removeObserver(self)
        super().finish()


class CombinePanel(Panel):
    def __init__(self):
        super().__init__('COMBINE')
        self.pick_mode = 'target'
        bodies = [o for o in self.doc.Objects if o.TypeId == 'PartDesign::Body' and o.Tip and not o.Shape.isNull()]
        self.target = combo([('Select','')]+[(o.Label, o.Name) for o in bodies])
        self.target.setParent(self.form)
        self.target.hide()
        self.tools = W.QListWidget(self.form)
        self.tools.hide()
        for body in bodies:
            item = W.QListWidgetItem(body.Label, self.tools)
            item.setData(QtCore.Qt.UserRole, body.Name)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Unchecked)
        self.target_menu = W.QMenu()
        self.target_menu.aboutToShow.connect(lambda:self.selection_menu('target'))
        self.tools_menu = W.QMenu()
        self.tools_menu.aboutToShow.connect(lambda:self.selection_menu('tools'))
        self.target_pick = PickField(lambda:self.begin_pick('target'), self.clear_target, self.target_menu)
        self.tools_pick = PickField(lambda:self.begin_pick('tools'), self.clear_tools, self.tools_menu)
        self.fields.addRow('Target Body', self.target_pick)
        self.fields.addRow('Tool Bodies', self.tools_pick)
        self.operation = combo([(v, v) for v in ('Join', 'Cut', 'Intersect')])
        self.operation.setParent(self.form)
        self.operation.hide()
        operations = W.QWidget()
        buttons = W.QHBoxLayout(operations)
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(2)
        self.operation_buttons = []
        for index, (label, picture) in enumerate([('Join','boolean_join'),('Cut','boolean_cut'),('Intersect','boolean_intersect')]):
            button = W.QToolButton()
            button.setIcon(cad_icon(picture))
            button.setToolTip(label)
            button.setAccessibleName(label)
            button.setCheckable(True)
            button.setChecked(index == 0)
            button.clicked.connect(lambda checked=False, i=index:self.operation.setCurrentIndex(i))
            buttons.addWidget(button)
            self.operation_buttons.append(button)
        buttons.addStretch()
        self.fields.addRow('Operation', operations)
        self.keep = self.row('Keep Tools', W.QCheckBox())
        picked = []
        for obj, _ in selection():
            body = body_of(obj)
            if body and body.TypeId == 'PartDesign::Body' and body not in picked:
                picked.append(body)
        if picked:
            selected_name(self.target, picked[0].Name)
            self.pick_mode = 'tools'
            for i in range(self.tools.count()):
                if self.tools.item(i).data(QtCore.Qt.UserRole) in [o.Name for o in picked[1:]]:
                    self.tools.item(i).setCheckState(QtCore.Qt.Checked)
        self.tools.itemChanged.connect(self.selection_changed)
        self.target.currentIndexChanged.connect(self.target_changed)
        self.operation.currentIndexChanged.connect(self.selection_changed)
        Gui.Selection.addObserver(self)
        self.sync_picks()
        self.schedule()

    def selection_menu(self, role):
        menu = self.target_menu if role == 'target' else self.tools_menu
        menu.clear()
        for index in range(self.tools.count()):
            item = self.tools.item(index)
            name = item.data(QtCore.Qt.UserRole)
            action = menu.addAction(item.text())
            action.setCheckable(True)
            action.setChecked(name == self.target.currentData() if role == 'target' else item.checkState() == QtCore.Qt.Checked)
            action.setEnabled(role == 'target' or name != self.target.currentData())
            if role == 'target':
                action.triggered.connect(lambda checked=False, n=name:selected_name(self.target, n))
            else:
                action.triggered.connect(lambda checked, i=index:self.tools.item(i).setCheckState(QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked))

    def sync_picks(self):
        names = [self.tools.item(i).text() for i in range(self.tools.count()) if self.tools.item(i).checkState() == QtCore.Qt.Checked]
        self.target_pick.update_count(bool(self.target.currentData()), self.target.currentText())
        self.tools_pick.update_count(len(names), ', '.join(names))
        self.target_pick.button.setChecked(self.pick_mode == 'target')
        self.tools_pick.button.setChecked(self.pick_mode == 'tools')
        for index, button in enumerate(self.operation_buttons):
            button.setChecked(index == self.operation.currentIndex())

    def selection_changed(self, *_):
        self.sync_picks()
        self.schedule()

    def target_changed(self, *_):
        for i in range(self.tools.count()):
            item = self.tools.item(i)
            if item.data(QtCore.Qt.UserRole) == self.target.currentData():
                item.setCheckState(QtCore.Qt.Unchecked)
        if self.target.currentData():
            self.pick_mode = 'tools'
        self.selection_changed()

    def begin_pick(self, role):
        self.timer.stop()
        self.busy = True
        self.rollback()
        Gui.Selection.clearSelection()
        self.busy = False
        self.pick_mode = role
        self.ok.setEnabled(False)
        self.sync_picks()

    def clear_target(self):
        self.target.setCurrentIndex(0)
        self.begin_pick('target')
        self.schedule()

    def clear_tools(self):
        for i in range(self.tools.count()):
            self.tools.item(i).setCheckState(QtCore.Qt.Unchecked)
        self.begin_pick('tools')
        self.schedule()

    def addSelection(self, *_):
        if self.closed or self.busy:
            return
        picks = selection()
        if not picks:
            return
        obj, sub = picks[-1]
        owner = body_of(obj)
        if not owner or owner.Document != self.doc or self.target.findData(owner.Name) < 1:
            return
        if self.pick_mode == 'target':
            selected_name(self.target, owner.Name)
        elif owner.Name != self.target.currentData():
            for i in range(self.tools.count()):
                if self.tools.item(i).data(QtCore.Qt.UserRole) == owner.Name:
                    self.tools.item(i).setCheckState(QtCore.Qt.Checked)
                    break

    def build(self):
        target = self.doc.getObject(self.target.currentData() or '')
        tools = [self.doc.getObject(self.tools.item(i).data(QtCore.Qt.UserRole))
                 for i in range(self.tools.count()) if self.tools.item(i).checkState() == QtCore.Qt.Checked]
        return combine(target, tools, self.operation.currentData(), self.keep.isChecked())

    def finish(self):
        Gui.Selection.removeObserver(self)
        super().finish()


def open_panel(kind):
    global _panel
    if not App.ActiveDocument:
        return
    if _panel:
        _panel.reject()
    if Gui.activeDocument().getInEdit() or Gui.Control.activeDialog():
        W.QMessageBox.information(Gui.getMainWindow(), 'FusionFlow', 'Nejprve dokonči nebo zruš právě otevřenou operaci.')
        return
    if _timeline:
        _timeline.end_preview()
    _panel = kind()
    _panel.show()


def edit_feature(obj, native=False):
    """Shared entry point for timeline, grouped browser and diagnostics."""
    if getattr(obj,'ConstructionMode','') and not native:
        from fusionflow_construct_ui import open_construct
        open_construct(obj.ConstructionMode,obj)
        return True
    if not obj or _panel or Gui.Control.activeDialog() or Gui.activeDocument().getInEdit():
        return False
    if _timeline:
        _timeline.end_preview()
    if getattr(obj, 'AnalysisType', ''):
        from fusionflow_analysis_ui import open_analysis
        open_analysis(obj.AnalysisType,obj)
        return True
    if not native and getattr(obj, 'FusionFlowCut', ''):
        try:
            open_panel(lambda: ExtrudePanel(obj))
        except ValueError as error:
            W.QMessageBox.warning(Gui.getMainWindow(), 'Extrude · společná editace', str(error))
        return True
    owner = body_of(obj)
    if owner:
        Gui.activeDocument().activeView().setActiveObject('pdbody', owner)
    Gui.activeDocument().setEdit(obj.Name)
    return False


def history_objects(doc):
    """Reconstruct surviving parametric steps; dependencies precede consumers."""
    objects = [o for o in doc.Objects if o.TypeId == 'Sketcher::SketchObject' or getattr(o,'ConstructionMode','') or
               (o.isDerivedFrom('PartDesign::Feature') and o.TypeId not in ('PartDesign::Body', 'PartDesign::SubShapeBinder'))] if doc else []
    names = {o.Name for o in objects}
    ordered, visited = [], set()
    def visit(obj):
        if obj.Name in visited:
            return
        visited.add(obj.Name)
        for dependency in obj.OutList:
            if dependency.Name in names:
                visit(dependency)
        ordered.append(obj)
    for obj in objects:
        visit(obj)
    return ordered


class HistoryList(W.QListWidget):
    positionRequested = QtCore.Signal(int)

    def __init__(self):
        super().__init__()
        self.history_position = 0
        self.dragging_marker = False
        self.setMouseTracking(True)
        self.setToolTip('Přetáhni svislou značku pro náhled mezistavu modelu. Dvojklik na ikonu upraví operaci.')

    def marker_x(self, position=None):
        position = self.history_position if position is None else position
        return self.visualItemRect(self.item(position-1)).right()+2 if position else 2-self.horizontalScrollBar().value()

    def set_marker(self, position):
        self.history_position = max(0,min(self.count(),position))
        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self.viewport())
        x = self.marker_x()
        painter.setPen(QtGui.QPen(QtGui.QColor('#d8e2ef'),2))
        painter.drawLine(x,7,x,self.viewport().height()-2)
        painter.setBrush(QtGui.QColor('#d8e2ef'))
        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x-4,1),QtCore.QPoint(x+4,1),QtCore.QPoint(x,7)]))

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and abs(event.position().x()-self.marker_x()) <= 6:
            self.dragging_marker = True
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging_marker:
            x = event.position().x()
            position = min(range(self.count()+1),key=lambda p:abs(self.marker_x(p)-x))
            if position != self.history_position:
                self.positionRequested.emit(position)
            event.accept()
        else:
            self.viewport().setCursor(QtCore.Qt.SizeHorCursor if abs(event.position().x()-self.marker_x()) <= 6 else QtCore.Qt.ArrowCursor)
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.dragging_marker:
            self.dragging_marker = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class Timeline(W.QDockWidget):
    def __init__(self):
        super().__init__('History / Historie', Gui.getMainWindow())
        self.setObjectName('FusionFlowHistory')
        self.setMaximumHeight(120)
        self.setAllowedAreas(QtCore.Qt.BottomDockWidgetArea)
        box = W.QWidget()
        layout = W.QHBoxLayout(box)
        layout.setContentsMargins(8, 2, 8, 2)
        self.list = HistoryList()
        self.list.setFlow(W.QListView.LeftToRight)
        self.list.setWrapping(False)
        self.list.setIconSize(QtCore.QSize(28, 28))
        self.list.setMaximumHeight(74)
        self.list.setMinimumHeight(64)
        self.list.setSpacing(3)
        layout.addWidget(self.list, 1)
        buttons = W.QVBoxLayout()
        self.ghost = W.QCheckBox('Náhled kroku')
        self.ghost.setToolTip('Zobrazí tvar po vybraném kroku. Nemění Tip ani pořadí operací.')
        self.ghost.toggled.connect(self.preview_selected)
        buttons.addWidget(self.ghost)
        end = W.QPushButton('Konec historie')
        end.clicked.connect(self.end_preview)
        buttons.addWidget(end)
        layout.addLayout(buttons)
        self.setWidget(box)
        self.signature = None
        self.saved = None
        self.list.itemClicked.connect(self.select)
        self.list.itemDoubleClicked.connect(self.edit)
        self.list.positionRequested.connect(self.go_to)
        self.list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self.context_menu)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(900)
        App.addDocumentObserver(self)
        Gui.getMainWindow().addDockWidget(QtCore.Qt.BottomDockWidgetArea, self)

    def slotStartSaveDocument(self, doc, filename):
        if self.saved and self.saved[0] == doc.Name:
            self.end_preview()

    def slotDeletedObject(self, obj):
        if not _panel and hasattr(obj,'Profile'):
            # Wait until native Delete has finished restoring input visibility.
            QtCore.QTimer.singleShot(0,self.hide_unused_profiles)

    def hide_unused_profiles(self):
        if not _panel:
            from fusionflow_core import hide_unused_profiles
            hide_unused_profiles(App.ActiveDocument)

    def refresh(self, force=False):
        if _panel:
            return
        self.hide_unused_profiles()
        doc = App.ActiveDocument
        if self.saved and (not doc or doc.Name != self.saved[0] or Gui.activeDocument().getInEdit()):
            self.end_preview()
        objects = history_objects(doc)
        findings = {o.Name:inspect.diagnostics(o) for o in objects}
        sig = (doc.Name if doc else '', tuple((o.Name, o.Label, tuple(o.State), getattr(o, 'Suppressed', False), findings[o.Name]) for o in objects))
        if sig == self.signature and not force:
            return
        old_names = tuple(self.list.item(i).data(QtCore.Qt.UserRole) for i in range(self.list.count()))
        same_steps = self.signature and self.signature[0] == sig[0] and old_names == tuple(o.Name for o in objects)
        old_position = self.list.history_position
        selected = self.list.currentItem().data(QtCore.Qt.UserRole) if self.list.currentItem() else None
        if not same_steps:
            self.end_preview()
        self.signature = sig
        self.list.clear()
        for i, obj in enumerate(objects, 1):
            icon = icons.status_badge(icons.feature_icon(obj), findings[obj.Name][0])
            if getattr(obj, 'Suppressed', False):
                icon = QtGui.QIcon(icon.pixmap(28, 28, QtGui.QIcon.Disabled))
            item = W.QListWidgetItem(icon, '%d  %s' % (i, obj.Label), self.list)
            item.setData(QtCore.Qt.UserRole, obj.Name)
            item.setToolTip(inspect.tooltip(obj,findings[obj.Name])+'\nDvojklik: upravit parametrickou operaci\nPravé tlačítko: diagnostika, vstupy a navazující operace')
            if getattr(obj, 'FusionFlowCut', ''):
                item.setToolTip(item.toolTip()+'\nSpolečný Extrude Cut: dvojklik upraví všechna tělesa této operace.'+('\nPotlačeno: těleso je z řezu vynechané.' if obj.Suppressed else ''))
            if 'Invalid' in obj.State:
                item.setForeground(QtGui.QColor('#c43b32'))
            if obj.Name == selected:
                self.list.setCurrentItem(item)
        self.list.set_marker(old_position if same_steps else self.list.count())

    def obj(self, item):
        return App.ActiveDocument.getObject(item.data(QtCore.Qt.UserRole)) if item and App.ActiveDocument else None

    def select(self, item):
        obj = self.obj(item)
        if obj and not _panel and not Gui.activeDocument().getInEdit():
            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(obj)
            self.preview_selected()

    def edit(self, item):
        obj = self.obj(item)
        if obj and not _panel and not Gui.activeDocument().getInEdit():
            edit_feature(obj)

    def preview_selected(self, *_):
        if not self.ghost.isChecked():
            self.end_preview()
            return
        if _panel or not App.ActiveDocument or Gui.activeDocument().getInEdit():
            return
        self.go_to(self.list.currentRow()+1)

    def go_to(self, position):
        if _panel or not App.ActiveDocument or Gui.Control.activeDialog() or Gui.activeDocument().getInEdit():
            return
        position = max(0,min(self.list.count(),position))
        if position == self.list.count():
            self.end_preview()
            return
        if not self.saved:
            self.saved = (App.ActiveDocument.Name, {o.Name: o.Visibility for o in App.ActiveDocument.Objects if hasattr(o, 'Visibility')})
        self.ghost.blockSignals(True)
        self.ghost.setChecked(True)
        self.ghost.blockSignals(False)
        self.list.set_marker(position)
        self.list.setCurrentRow(position-1)
        if position:
            self.list.scrollToItem(self.list.item(position-1))
        heads, consumed = {}, set()
        for i in range(position):
            obj = self.obj(self.list.item(i))
            if obj.TypeId != 'Sketcher::SketchObject':
                owner = body_of(obj)
                heads[owner.Name if owner else obj.Name] = obj
                if obj.TypeId == 'PartDesign::Boolean':
                    consumed.update(tool.Name for tool in obj.Group)
        for o in App.ActiveDocument.Objects:
            if hasattr(o, 'Shape'):
                o.Visibility = False
        for name, obj in heads.items():
            if name not in consumed:
                owner = body_of(obj)
                if owner:
                    owner.Visibility = True
                obj.Visibility = True
        current = self.obj(self.list.currentItem())
        if current and current.TypeId == 'Sketcher::SketchObject':
            owner = body_of(current)
            if owner:
                owner.Visibility = True
            current.Visibility = True

    def context_menu(self, point):
        item = self.list.itemAt(point)
        if not item or Gui.Control.activeDialog() or (Gui.activeDocument() and Gui.activeDocument().getInEdit()):
            return
        menu = W.QMenu(self.list)
        from fusionflow_ribbon import MENU_STYLE
        menu.setStyleSheet(MENU_STYLE)
        menu.setToolTipsVisible(True)
        inspect.add_diagnostics(menu,self.obj(item))
        menu.addAction('Edit / Upravit operaci',lambda:self.edit(item))
        if getattr(self.obj(item), 'FusionFlowCut', ''):
            menu.addAction('Upravit nativní Pocket', lambda:edit_feature(self.obj(item), native=True))
        menu.addAction('Náhled po tomto kroku',lambda:self.go_to(self.list.row(item)+1))
        menu.addAction('Konec historie',self.end_preview)
        menu.addSeparator();inspect.add_relations(menu,self.obj(item))
        menu.exec(self.list.mapToGlobal(point))
        menu.deleteLater()

    def restore(self):
        if self.saved:
            name, visibility = self.saved
            doc = App.listDocuments().get(name)
            if doc:
                for key, val in visibility.items():
                    obj = doc.getObject(key)
                    if obj:
                        obj.Visibility = val
            self.saved = None

    def end_preview(self, *_):
        self.ghost.blockSignals(True)
        self.ghost.setChecked(False)
        self.ghost.blockSignals(False)
        self.restore()
        self.list.set_marker(self.list.count())


class Command:
    def __init__(self, text, callback, icon, tip='', always=False):
        self.text, self.callback, self.icon, self.tip, self.always = text, callback, icon, tip, always

    def GetResources(self):
        return {'MenuText': self.text, 'ToolTip': self.tip or self.text, 'Pixmap': icons.icon_path(self.icon)}

    def Activated(self):
        self.callback()

    def IsActive(self):
        return self.always or bool(App.ActiveDocument)


def show_sketches():
    if _timeline:
        _timeline.end_preview()
    doc = App.ActiveDocument
    if not doc:
        return
    selected = [o for o, _ in selection() if o.TypeId == 'Sketcher::SketchObject']
    sketches = selected or [o for o in doc.Objects if o.TypeId == 'Sketcher::SketchObject']
    show = not all(o.Visibility for o in sketches)
    for obj in sketches:
        obj.MakeInternals = True
        obj.Visibility = show
    doc.recompute()


def search_entries():
    from fusionflow_sketch import active_sketch
    from fusionflow_ribbon import SKETCH_CREATE, SKETCH_MODIFY, CONSTRAINTS, FINISH
    if active_sketch():
        def flatten(entries):
            for entry in entries:
                if entry is None:
                    continue
                if len(entry) == 2:
                    yield from flatten(entry[1])
                elif entry[1] and entry[1] in Gui.listCommands():
                    yield entry[1], entry[0] + ('  ·  '+entry[3] if entry[3] else '')
        return list(dict(flatten(SKETCH_CREATE + SKETCH_MODIFY + CONSTRAINTS + [FINISH])).items())
    return [('FusionFlow_CreateSketch', 'Create Sketch / Nová skica'), ('FusionFlow_Extrude', 'Extrude / Vysunutí'), ('FusionFlow_Combine', 'Combine / Spojit, odebrat, průnik'), ('PartDesign_Fillet', 'Fillet / Zaoblení'), ('PartDesign_Chamfer', 'Chamfer / Zkosení'), ('PartDesign_Hole', 'Hole / Díra'), ('PartDesign_Thickness', 'Shell / Skořepina'), ('PartDesign_Revolution', 'Revolve / Orotování'), ('PartDesign_AdditivePipe', 'Sweep / Tažení'), ('PartDesign_AdditiveLoft', 'Loft'), ('PartDesign_LinearPattern', 'Rectangular pattern'), ('PartDesign_PolarPattern', 'Circular pattern'), ('PartDesign_Draft', 'Draft / Úkos'), ('Std_Measure', 'Measure / Měření')]


def search_commands():
    from fusionflow_sketch import active_sketch
    from fusionflow_ribbon import native_action
    dialog = W.QDialog(Gui.getMainWindow())
    dialog.setObjectName('FusionCommandSearch')
    dialog.setWindowTitle('Search / Příkazy')
    dialog.resize(440, 390)
    layout = W.QVBoxLayout(dialog)
    field = W.QLineEdit()
    field.setPlaceholderText('Line, Rectangle, Dimension, Trim…' if active_sketch() else 'Extrude, Combine, Fillet…')
    layout.addWidget(field)
    entries = W.QListWidget()
    layout.addWidget(entries)
    for name, label in search_entries():
        item = W.QListWidgetItem(label, entries)
        item.setData(QtCore.Qt.UserRole, name)
        item.setIcon(icons.command_icon(name,small=True))
        action = native_action(name)
        if action and not action.isEnabled():
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEnabled)
    def filter_items(text):
        for i in range(entries.count()):
            entries.item(i).setHidden(text.casefold() not in entries.item(i).text().casefold())
        entries.setCurrentItem(next((entries.item(i) for i in range(entries.count())
                                    if not entries.item(i).isHidden() and entries.item(i).flags() & QtCore.Qt.ItemIsEnabled),None))
    field.textChanged.connect(filter_items)
    def run(item):
        if item is None or item.isHidden() or not item.flags() & QtCore.Qt.ItemIsEnabled:
            return
        dialog.accept()
        command = item.data(QtCore.Qt.UserRole)
        QtCore.QTimer.singleShot(0,lambda: Gui.runCommand(command))
    entries.itemActivated.connect(run)
    field.returnPressed.connect(lambda: run(entries.currentItem()))
    filter_items('')
    field.setFocus()
    dialog.exec()
    dialog.deleteLater()


def move_context():
    from fusionflow_sketch import active_sketch
    Gui.runCommand('Sketcher_Move' if active_sketch() else 'Std_TransformManip')


def toolbar(name, commands):
    bar = W.QToolBar(name, Gui.getMainWindow())
    bar.setObjectName(name)
    bar.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
    bar.setIconSize(QtCore.QSize(30, 30))
    for name, label, icon in commands:
        command = Gui.Command.get(name)
        if command is None:
            continue
        actions = command.getAction()
        if isinstance(actions, (list, tuple)):
            action = actions[0] if actions else None
        else:
            action = actions
        if action is None:
            action = QtGui.QAction(label, bar)
            action.setObjectName(name)
            action.triggered.connect(lambda checked=False, cmd=name: Gui.runCommand(cmd))
            Gui.getMainWindow().addAction(action)
        if action:
            action.setText(label)
            if icon:
                action.setIcon(QtGui.QIcon(str(ROOT / 'icons' / (icon + '.svg'))))
            button = W.QToolButton(bar)
            button.setDefaultAction(action)
            button.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
            button.setText(label)
            bar.addWidget(button)
    Gui.getMainWindow().addToolBar(bar)
    return bar


def install():
    global _installed, _timeline, _bars
    if _installed or not App.ParamGet(PREF).GetBool('Enabled', True):
        return
    _installed = True
    import PartDesignGui, SketcherGui
    import fusionflow_analysis_ui
    fusionflow_analysis_ui.install()
    import fusionflow_construct_ui, fusionflow_navigator
    fusionflow_construct_ui.install();fusionflow_navigator.install()
    for name, command in {
        'FusionFlow_CreateSketch': Command('Create Sketch', create_sketch, 'sketch', 'Skica na vybrané rovinné stěně; její těleso se aktivuje automaticky'),
        'FusionFlow_Extrude': Command('Extrude', lambda: open_panel(ExtrudePanel), 'extrude', 'E · Vysunutí vybrané stěny nebo oblasti skici; Join, Cut, Intersect nebo New body'),
        'FusionFlow_Combine': Command('Combine', lambda: open_panel(CombinePanel), 'combine', 'Cílové těleso + nástrojová tělesa; Join / Cut / Intersect'),
        'FusionFlow_Sketches': Command('Sketches', show_sketches, 'sketch', 'Zobrazit / skrýt skici pro další použití'),
        'FusionFlow_Search': Command('Search', search_commands, 'search', 'S · Vyhledání příkazu'),
        'FusionFlow_Move': Command('Move / Copy', move_context, 'move', 'M · Přesun geometrie skici nebo tělesa'),
    }.items():
        Gui.addCommand(name, command)
    from freecad_fusion import presets
    presets.SHORTCUTS['E'] = 'FusionFlow_Extrude'
    presets.SHORTCUTS['L'] = 'Sketcher_CreatePolyline'
    presets.SHORTCUTS['M'] = 'FusionFlow_Move'
    presets.SHORTCUTS['I'] = 'FusionFlow_Measure'
    presets.apply_preset()
    for key, command in [('S', 'FusionFlow_Search')]:
        for old in Gui.Command.listByShortcut(key):
            if old != command:
                presets._backup_shortcut(presets.params.backup_group(), 'displaced', old)
                Gui.Command.get(old).setShortcut('')
        Gui.Command.get(command).setShortcut('')
    bind_shortcuts()
    # No workbench replacement: all commands stay in Part Design and Sketcher.
    model = [('FusionFlow_CreateSketch', 'Create Sketch', 'sketch'), ('FusionFlow_Extrude', 'Extrude  E', 'extrude'),
             ('PartDesign_Revolution', 'Revolve', None), ('PartDesign_AdditiveLoft', 'Loft', None),
             ('FusionFlow_Combine', 'Combine', 'combine'), ('PartDesign_Fillet', 'Fillet  F', 'fillet'),
             ('PartDesign_Chamfer', 'Chamfer', None), ('PartDesign_Hole', 'Hole  H', None),
             ('PartDesign_Thickness', 'Shell', None), ('FusionFlow_Sketches', 'Sketches', 'sketch'),
             ('FusionFlow_Search', 'Search  S', 'search')]
    sketch = [('Sketcher_CreateLine', 'Line  L', None), ('Sketcher_CreateRectangle', 'Rectangle  R', None),
              ('Sketcher_CreateCircle', 'Circle  C', None), ('Sketcher_CreatePolyline', 'Polyline', None),
              ('Sketcher_Dimension', 'Dimension  D', None), ('Sketcher_Trimming', 'Trim  T', None),
              ('Sketcher_Offset', 'Offset  O', None), ('Sketcher_Projection', 'Project  P', None),
              ('Sketcher_ToggleConstruction', 'Construction  X', None), ('Sketcher_LeaveSketch', 'Finish Sketch', 'finish')]
    _bars = [] if App.ParamGet(PREF).GetBool('RibbonEnabled', True) else [toolbar('FusionFlow · Solid', model), toolbar('FusionFlow · Sketch', sketch)]
    _timeline = Timeline()
    def arrange(*_):
        wb = Gui.activeWorkbench().name()
        for bar in Gui.getMainWindow().findChildren(W.QToolBar):
            if bar in _bars:
                continue
            names = [a.objectName() for a in bar.actions() if not a.isSeparator()]
            if names and all(n.startswith(('PartDesign_', 'Sketcher_')) for n in names):
                bar.hide()
        if _bars:
            _bars[0].setVisible(wb == 'PartDesignWorkbench')
            _bars[1].setVisible(wb == 'SketcherWorkbench')
        _timeline.show()
    Gui.getMainWindow().workbenchActivated.connect(lambda *_: QtCore.QTimer.singleShot(0, arrange))
    arrange()
    import fusionflow_ribbon
    fusionflow_ribbon.install()
    import fusionflow_view
    fusionflow_view.install()
    import fusionflow_sketch
    fusionflow_sketch.install()
    import fusionflow_browser
    fusionflow_browser.install()
    App.ParamGet('User parameter:BaseApp/Preferences/Mod/Sketcher').SetBool('MakeInternals', True)
    App.ParamGet('User parameter:BaseApp/Preferences/General').SetString('AutoloadModule', 'PartDesignWorkbench')
    App.Console.PrintMessage('FusionFlow připraven: E Extrude, S Search, Combine, History.\n')


def bind_shortcuts():
    """Use one Qt shortcut per custom command, without a second native action."""
    global _shortcuts
    for shortcut in _shortcuts:
        shortcut.setEnabled(False)
        shortcut.deleteLater()
    _shortcuts = []
    for key, name in [('E', 'FusionFlow_Extrude'), ('S', 'FusionFlow_Search'), ('M', 'FusionFlow_Move')]:
        Gui.Command.get(name).setShortcut('')
        for action in Gui.getMainWindow().findChildren(QtGui.QAction):
            if action.objectName() == name:
                action.setShortcut(QtGui.QKeySequence())
        shortcut = QtGui.QShortcut(QtGui.QKeySequence(key), Gui.getMainWindow())
        shortcut.setContext(QtCore.Qt.ApplicationShortcut)
        shortcut.activated.connect(lambda cmd=name: Gui.runCommand(cmd))
        _shortcuts.append(shortcut)
    reconcile_shortcuts()


def reconcile_shortcuts():
    """Clearing a Command shortcut can restore its default; clear Qt actions too."""
    from freecad_fusion import presets
    custom = {'FusionFlow_Extrude','FusionFlow_Search','FusionFlow_Move'}
    for key, target in dict(presets.SHORTCUTS, S='FusionFlow_Search').items():
        for name in set(Gui.Command.listByShortcut(key)) | {target}:
            command = Gui.Command.get(name)
            if command is None:
                continue
            actions = command.getAction()
            for action in actions if isinstance(actions,(tuple,list)) else [actions]:
                if action:
                    action.setShortcut(QtGui.QKeySequence(key if name==target and name not in custom else ''))
