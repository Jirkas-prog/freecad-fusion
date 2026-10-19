"""Compact sketch controls using the native Sketcher, solver and edit session."""
import re
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore as C, QtGui as G, QtWidgets as W
from shiboken6 import isValid
import fusionflow_icons as icons
from fusionflow_ui import OperationCard

PREF = 'User parameter:BaseApp/Preferences/Mod/FusionFlow'
SNAP = 'User parameter:BaseApp/Preferences/Mod/Sketcher/Snap'
DIMENSIONS = {'Distance', 'DistanceX', 'DistanceY', 'Angle', 'Radius', 'Diameter',
              'Weight', 'SnellsLaw'}
TOOL_FAMILIES={'Circle':'Circle','Arc':'Arc','Rectangle':'Rectangle','ArcSlot':'Arc Slot',
               'BSpline':'B-Spline','Polyline':'Polyline','Line':'Line','Ellipse':'Ellipse','Polygon':'Polygon'}
_manager = None


def active_sketch():
    edit = Gui.activeDocument().getInEdit() if Gui.activeDocument() else None
    return edit.Object if edit and edit.Object.TypeId == 'Sketcher::SketchObject' else None


def constraint_ids(sketch, dimensions):
    return [i for i, c in enumerate(sketch.Constraints) if (c.Type in DIMENSIONS) == dimensions]


def set_constraint_visibility(sketch, dimensions, visible):
    """Same saved visibility metadata as the native constraint-list checkboxes."""
    ids = constraint_ids(sketch, dimensions)
    if not ids:
        return
    doc = sketch.Document
    doc.openTransaction('Show / hide sketch dimensions' if dimensions else 'Show / hide sketch constraints')
    try:
        sketch.setVirtualSpace(ids, not visible)
        sketch.setVisibility(ids, visible)
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise


class FeatureOptions(W.QWidget):
    """Mirror native mode controls; never replace the running drawing handler."""
    def __init__(self, palette):
        super().__init__(palette)
        self.palette=palette;self.source=None;self.signature=None;self.controls=[];self.family=''
        layout=W.QVBoxLayout(self);layout.setContentsMargins(0,0,0,4);layout.setSpacing(3)
        self.body=W.QWidget();body_layout=W.QVBoxLayout(self.body);body_layout.setContentsMargins(0,0,0,0);body_layout.setSpacing(3)
        layout.addWidget(palette.section('Feature Options',self.body))
        layout.addWidget(self.body)
        self.content=W.QWidget();body_layout.addWidget(self.content)
        self.rows=W.QVBoxLayout(self.content);self.rows.setContentsMargins(0,0,0,0);self.rows.setSpacing(3)
        self.hints=W.QLabel();self.hints.setObjectName('FusionToolHints');self.hints.setWordWrap(True)
        self.hints.setTextFormat(C.Qt.RichText);self.hints.setStyleSheet('color:#c6d5e1;font-size:11px;padding:3px 0;')
        body_layout.addWidget(self.hints)
        self.actions=W.QWidget();buttons=W.QHBoxLayout(self.actions);buttons.setContentsMargins(0,0,0,0)
        self.cycle=W.QPushButton('Další režim · M');self.cycle.setObjectName('FusionToolCycle')
        self.cycle.setToolTip('Nativní přepnutí režimu. U Polyline je dostupné po první úsečce.')
        self.cycle.clicked.connect(lambda:self.send_key(C.Qt.Key_M,'m',0x4d));buttons.addWidget(self.cycle)
        self.cancel=W.QPushButton('Přerušit · Esc');self.cancel.setObjectName('FusionToolEscape')
        self.cancel.setToolTip('Stejné jako Escape v kreslicí ploše; dokončená geometrie zůstane zachovaná.')
        self.cancel.clicked.connect(lambda:self.send_key(C.Qt.Key_Escape,'',0x1b));buttons.addWidget(self.cancel)
        body_layout.addWidget(self.actions)
        self.hide()

    def sync(self):
        native_hint=Gui.getMainWindow().findChild(W.QLabel,'hintLabel')
        html=native_hint.text() if native_hint else ''
        document=G.QTextDocument();document.setHtml(html);plain=document.toPlainText()
        def hint_matches(family,message):
            text=C.QCoreApplication.translate('SketcherGui::DrawSketchHandler'+family,message)
            return text.replace('%1','').strip() in plain
        slot=any(hint_matches('Slot','%1 '+message) for message in ('pick slot start point','pick slot end point','pick slot width'))
        sources=[w for w in self.palette.tasks.findChildren(W.QWidget)
                 if w.metaObject().className()=='SketcherGui::SketcherToolDefaultWidget' and w.isVisibleTo(self.palette.tasks)] if self.palette.tasks else []
        source=sources[-1] if sources else None
        combos=[c for c in source.findChildren(W.QComboBox) if not c.isHidden() and c.count()>0] if source else []
        checks=[c for c in source.findChildren(W.QCheckBox) if not c.isHidden()] if source else []
        fields=[c for c in source.findChildren(W.QAbstractSpinBox) if c.isVisibleTo(source)] if source else []
        signature=(source,tuple((c,tuple(c.itemText(i) for i in range(c.count()))) for c in combos),tuple(checks),tuple(fields),slot)
        if signature!=self.signature:
            self.signature=signature;self.source=source;self.controls=[]
            while self.rows.count():
                entry=self.rows.takeAt(0)
                if entry.widget():entry.widget().deleteLater()
            heading=next((w.text() for w in source.parentWidget().parentWidget().findChildren(W.QWidget)
                          if w.metaObject().className()=='QSint::ActionLabel'),'') if source else ''
            family=next((name for name,title in TOOL_FAMILIES.items() if heading in (title+' Parameters',
                        C.QCoreApplication.translate('SketcherGui::DrawSketchHandler'+name,title+' Parameters'))),'Slot' if slot else '')
            self.family=family
            if family in ('Slot','ArcSlot'):
                row=W.QWidget();buttons=W.QHBoxLayout(row);buttons.setContentsMargins(0,0,0,0)
                buttons.addWidget(W.QLabel('Slot'),1)
                for command,picture,label in [('Sketcher_CreateSlot','slot','Rovná drážka'),('Sketcher_CreateArcSlot','arc_slot','Oblouková drážka')]:
                    button=W.QToolButton();button.setObjectName('Variant_'+command);button.setIcon(icons.icon(picture,True))
                    button.setIconSize(C.QSize(21,21));button.setFixedSize(28,26);button.setCheckable(True)
                    button.setChecked((family=='Slot')==(command=='Sketcher_CreateSlot'));button.setToolTip(label+' — začne nový tvar')
                    button.clicked.connect(lambda checked=False,cmd=command:self.start_tool(cmd));buttons.addWidget(button)
                self.rows.addWidget(row)
            for combo_index,combo in enumerate(combos):
                container=W.QWidget();row=W.QHBoxLayout(container);row.setContentsMargins(0,0,0,0);row.setSpacing(3)
                label=source.findChild(W.QLabel,combo.objectName().replace('comboBox','comboLabel'))
                caption=('Ends' if family=='ArcSlot' else family) if family and combo_index==0 else label.text().replace(' (M)','') if label else 'Mode'
                row.addWidget(W.QLabel(caption),1)
                buttons=[]
                for i in range(combo.count()):
                    button=W.QToolButton();button.setCheckable(True);button.setFixedSize(25,25);button.setIconSize(C.QSize(19,19))
                    icon=combo.itemIcon(i)
                    entry=family.lower()
                    pictures={'circle':['circle','circle3'],'rectangle':['rectangle','center_rectangle','rectangle3','center_rectangle'],
                              'arc':['arc_center','arc3'],'arcslot':['arc_slot','arc_slot_flat'],
                              'line':['line_angle','line_xy','line_points'],'bspline':['spline','spline']}
                    if entry in pictures:icon=icons.icon(pictures[entry][min(i,len(pictures[entry])-1)],True)
                    if icon.isNull():button.setText(str(i+1))
                    else:button.setIcon(icon)
                    button.setToolTip(combo.itemText(i))
                    button.clicked.connect(lambda _,c=combo,n=i:self.set_mode(c,n))
                    row.addWidget(button);buttons.append(button)
                self.rows.addWidget(container);self.controls.append((combo,buttons))
            for source_check in checks:
                check=W.QCheckBox(source_check.text());check.setToolTip(source_check.toolTip())
                check.clicked.connect(lambda on,c=source_check:c.setChecked(on) if isValid(c) else None)
                self.rows.addWidget(check);self.controls.append((source_check,check))
            for native in fields:
                row=W.QWidget();layout=W.QHBoxLayout(row);layout.setContentsMargins(0,0,0,0)
                names=['One','Two','Three','Four','Five','Six','Seven','Eight','Nine','Ten']
                index=next((i for i,n in enumerate(names) if native.objectName()=='parameter'+n),0)
                label=source.findChild(W.QLabel,'label'+(str(index+1) if index else ''))
                layout.addWidget(W.QLabel(label.text() if label else 'Value'))
                field=W.QLineEdit();field.setMaximumWidth(105)
                field.editingFinished.connect(lambda n=native,f=field:self.set_value(n,f))
                layout.addWidget(field);self.rows.addWidget(row);self.controls.append((native,field))
            if source and family not in ('ArcSlot',):
                hint=W.QLabel('Tab: hodnoty   ·   Esc: ukončit')
                hint.setStyleSheet('color:#aebbc9;font-size:10px;padding:2px 0;')
                self.rows.addWidget(hint)
        for native,control in self.controls:
            if not isValid(native):continue
            if isinstance(control,list):
                for i,button in enumerate(control):button.setChecked(i==native.currentIndex());button.setEnabled(native.isEnabled())
            elif isinstance(control,W.QLineEdit):
                if not control.hasFocus():control.setText(native.text())
            else:control.setChecked(native.isChecked());control.setEnabled(native.isEnabled())
        # The status bar is hidden by our ribbon. Keep the native, state-specific
        # mouse/key hints available here, including tools without a task widget.
        cells=re.findall(r'<td valign=bottom>(.*?)</td>',html,re.S)
        self.hints.setText('<br/>'.join(cells).replace('height=22','height=16'))
        self.hints.setVisible(bool(cells))
        self.actions.setVisible(bool(cells))
        self.cycle.setVisible(bool(cells) and not combos and any(hint_matches(f,'%1 switch mode') for f in ('LineSet',*TOOL_FAMILIES)))
        self.setVisible(bool(source or cells))
        # Native drawing tools use M to switch construction method. Do not let the
        # global Move shortcut steal it while a tool is collecting points.
        import fusionflow_ui as ui
        view=Gui.activeDocument().activeView()
        drawing=source is not None or view.graphicsView().cursor().shape()==C.Qt.BitmapCursor
        for shortcut in ui._shortcuts:
            if shortcut.key().toString()=='M':shortcut.setEnabled(not drawing)

    def set_mode(self, combo, index):
        if isValid(combo):combo.setCurrentIndex(index)
        Gui.activeDocument().activeView().graphicsView().setFocus()
        self.sync()

    def start_tool(self,command):
        Gui.runCommand(command)
        Gui.activeDocument().activeView().graphicsView().setFocus()
        self.sync()

    def send_key(self,key,text,virtual_key):
        if active_sketch()!=self.palette.sketch or not self.hints.isVisible():return
        view=Gui.activeDocument().activeView().graphicsView();view.setFocus()
        for event_type in (C.QEvent.KeyPress,C.QEvent.KeyRelease):
            W.QApplication.sendEvent(view.viewport(),G.QKeyEvent(event_type,key,C.Qt.NoModifier,0,virtual_key,0,text))
        self.sync()

    def set_value(self, native, field):
        if not isValid(native):return
        try:
            quantity=App.Units.Quantity(field.text())
            current=native.property('value')
            if isinstance(native,(W.QSpinBox,W.QDoubleSpinBox)):
                if quantity.Unit!=App.Units.Unit():raise ValueError('Zadejte počet bez jednotky.')
                if isinstance(native,W.QSpinBox) and not quantity.Value.is_integer():raise ValueError('Zadejte celé číslo.')
                native.setValue(int(quantity.Value) if isinstance(native,W.QSpinBox) else quantity.Value)
            else:
                if hasattr(current,'Unit') and quantity.Unit not in (App.Units.Unit(),current.Unit):
                    raise ValueError('Nesprávná jednotka pro tento parametr.')
                if not native.setProperty('rawValue',quantity.Value):raise ValueError('Pole není editovatelné.')
            native.editingFinished.emit()
            field.setStyleSheet('')
        except Exception as exc:
            field.setToolTip(str(exc));field.setStyleSheet('border:1px solid #ed7770;')

    def dispose(self):
        import fusionflow_ui as ui
        for shortcut in ui._shortcuts:
            if shortcut.key().toString()=='M':shortcut.setEnabled(True)


class SketchPalette(OperationCard):
    def __init__(self, sketch):
        super().__init__('SKETCH PALETTE')
        self.sketch = sketch
        from fusionflow_profiles import SketchProfiles
        self.profiles = SketchProfiles(sketch)
        from fusionflow_sketch_view import SketchPresentation
        self.presentation = SketchPresentation(sketch)
        self.setFixedWidth(252)
        self.setObjectName('FusionOperationCard')
        self.setProperty('FusionSketchPalette', True)
        self.setStyleSheet(self.styleSheet()+'''
          #FusionOperationCard QCheckBox::indicator {width:12px;height:12px;border:1px solid #a5afbc;border-radius:0;background:#394352;}
          #FusionOperationCard QCheckBox::indicator:checked {background:#e0e5eb;image:url("'''+str(icons.ROOT/'sketch_check.svg').replace('\\','/')+'''");}
          #FusionOperationCard QToolButton:checked {background:#425e73;border:1px solid #6192af;}
          #FusionOperationCard QToolButton[section="true"] {border:0;background:transparent;padding:4px 0;text-align:left;font-weight:600;}
        ''')
        self.tasks = Gui.getMainWindow().findChild(W.QDockWidget, 'Tasks')
        self.tasks_visible = self.tasks.isVisible() if self.tasks else False
        if self.tasks:
            self.tasks.hide()
        self.widgets = {}
        outer = W.QVBoxLayout(self)
        outer.setContentsMargins(10, 5, 8, 7)
        outer.setSpacing(3)
        title = W.QLabel('SKETCH PALETTE')
        title.setStyleSheet('font-size:11px;letter-spacing:1px;')
        outer.addWidget(title)
        self.scroll = W.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(C.Qt.ScrollBarAlwaysOff)
        content = W.QWidget()
        content_layout = W.QVBoxLayout(content)
        content_layout.setContentsMargins(0,0,2,0);content_layout.setSpacing(3)
        self.feature_options = FeatureOptions(self)
        content_layout.addWidget(self.feature_options)
        self.options = W.QWidget()
        options_header = self.section('Options',self.options)
        content_layout.addWidget(options_header)
        content_layout.addWidget(self.options)
        self.rows = W.QGridLayout(self.options)
        self.rows.setContentsMargins(0, 3, 2, 3)
        self.rows.setHorizontalSpacing(10)
        self.rows.setVerticalSpacing(2)
        self.scroll.setWidget(content)
        outer.addWidget(self.scroll)
        self.row('Linetype', self.command_button('Sketcher_ToggleConstruction', 'construction',
                 'Construction · X — přepnout vybrané čáry nebo režim nového kreslení'))
        self.row('Look At', self.command_button('Sketcher_ViewSketch', 'view_look_at',
                 'Pohled kolmo na rovinu aktivní skici'))
        self.check('grid', 'Sketch Grid', lambda on: self.set_view('ShowGrid', on), 'Mřížka aktivní skici')
        self.check('snap', 'Snap', self.set_snap,
                   'Přichycení k mřížce; geometrické vazby se nastavují samostatně')
        self.check('slice', 'Slice', self.slice, 'Dočasný řez v rovině skici: vyplněný materiál a obrysy; otvory zůstávají prázdné')
        self.check('profiles', 'Profile', lambda on: App.ParamGet(PREF).SetBool('SketchProfiles',on),
                   'Modré vybarvení uzavřených oblastí skici — stejné oblasti jako pro Extrude')
        self.check('points','Points',lambda on: App.ParamGet(PREF).SetBool('SketchPoints',on),'Zobrazit body skici')
        self.check('dimensions', 'Dimensions', lambda on: set_constraint_visibility(self.sketch, True, on),
                   'Zobrazit / skrýt kóty; hodnoty kót i jejich vazby zůstávají zachované')
        self.check('constraints', 'Constraints', lambda on: set_constraint_visibility(self.sketch, False, on),
                   'Zobrazit / skrýt symboly geometrických vazeb')
        self.check('projected','Projected Geometries',lambda on: App.ParamGet(PREF).SetBool('SketchProjected',on),'Zobrazit promítnuté referenční a profilové čáry')
        self.check('construction_geometry','Construction Geometries',lambda on: App.ParamGet(PREF).SetBool('SketchConstruction',on),'Zobrazit konstrukční čáry; jejich vazby se nemění')
        advanced = W.QWidget()
        advanced_header = self.section('Sketcher options',advanced,False)
        content_layout.addWidget(advanced_header);content_layout.addWidget(advanced)
        option_rows = self.rows
        self.rows = W.QGridLayout(advanced);self.rows.setContentsMargins(0,2,2,2);self.rows.setVerticalSpacing(2)
        self.check('adaptive', 'Adaptive Grid', lambda on: self.set_view('GridAuto', on), 'Automatická rozteč podle přiblížení')
        self.check('auto', 'Auto Constraints', lambda on: self.set_view('Autoconstraints', on), 'Automatické vazby při kreslení')
        self.status = W.QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(C.Qt.PlainText)
        self.rows.addWidget(self.status, self.rows.rowCount(), 0, 1, 2)
        self.profile_status = W.QLabel()
        self.profile_status.setWordWrap(True)
        self.profile_status.setTextFormat(C.Qt.PlainText)
        self.rows.addWidget(self.profile_status,self.rows.rowCount(),0,1,2)
        find = W.QPushButton('Find Under-Constrained')
        find.setToolTip('Vybrat geometrii, která se stále může pohybovat')
        find.clicked.connect(lambda: Gui.runCommand('Sketcher_SelectElementsWithDoFs'))
        self.widgets['find'] = find
        self.rows.addWidget(find, self.rows.rowCount(), 0, 1, 2)
        self.details = W.QCheckBox('Sketcher details')
        self.details.setToolTip('Nativní volby nástroje, seznam kót, vazeb a diagnostika řešiče')
        self.details.toggled.connect(self.show_details)
        self.rows.addWidget(self.details,self.rows.rowCount(),0,1,2)
        self.rows = option_rows
        self.problem=W.QPushButton('Vazby vyžadují opravu — otevřít diagnostiku')
        self.problem.setStyleSheet('color:#ffb06a;font-size:10px;')
        self.problem.clicked.connect(lambda:self.details.setChecked(True))
        outer.addWidget(self.problem);self.problem.hide()
        finish = W.QPushButton('Finish Sketch')
        finish.setObjectName('FusionSketchFinish')
        finish.clicked.connect(lambda: Gui.runCommand('Sketcher_LeaveSketch'))
        outer.addWidget(finish, 0, C.Qt.AlignRight)
        self.sync()
        self.show()

    def section(self, text, content, expanded=True):
        button=W.QToolButton();button.setProperty('section',True)
        button.setToolButtonStyle(C.Qt.ToolButtonTextBesideIcon)
        button.setText(text);button.setCheckable(True);button.setChecked(expanded)
        def toggle(on):
            content.setVisible(on);button.setArrowType(C.Qt.DownArrow if on else C.Qt.RightArrow)
            self.place()
        button.toggled.connect(toggle)
        content.setVisible(expanded);button.setArrowType(C.Qt.DownArrow if expanded else C.Qt.RightArrow)
        return button

    def row(self, label, widget):
        index = self.rows.rowCount()
        self.rows.addWidget(W.QLabel(label), index, 0)
        self.rows.addWidget(widget, index, 1, C.Qt.AlignRight)
        self.rows.setRowMinimumHeight(index,25)

    def check(self, key, label, callback, tip):
        widget = W.QCheckBox()
        widget.setObjectName('SketchOption_'+key)
        widget.setToolTip(tip)
        # clicked rather than stateChanged lets sync display a partial state safely.
        widget.clicked.connect(lambda on: self.change(callback, on))
        self.widgets[key] = widget
        self.row(label, widget)

    def change(self, callback, value):
        if active_sketch() != self.sketch:
            return
        try:
            callback(value)
        except Exception as exc:
            App.Console.PrintError('Sketch Palette: %s\n' % exc)
        self.sync()

    def command_button(self, command, picture, tip):
        button = W.QToolButton()
        button.setObjectName('Palette_'+command)
        button.setIcon(icons.command_icon(command, picture, True))
        button.setIconSize(C.QSize(18, 18));button.setFixedSize(28, 26)
        button.setToolTip(tip)
        button.clicked.connect(lambda: Gui.runCommand(command))
        self.widgets[command] = button
        return button

    def set_view(self, name, value):
        setattr(self.sketch.ViewObject, name, value)
        key={'ShowGrid':'SketchGrid','GridAuto':'SketchAdaptive'}.get(name)
        if key:App.ParamGet(PREF).SetBool(key,value)

    def set_snap(self,on):
        pref=App.ParamGet(SNAP);pref.SetBool('SnapToGrid',on)
        if on:pref.SetBool('Snap',True)

    def slice(self, value):
        self.sketch.ViewObject.TempoVis.sketchClipPlane(self.sketch, value)

    def show_details(self, visible):
        if self.tasks and isValid(self.tasks):
            self.tasks.setVisible(visible)
            if visible:
                self.tasks.raise_()
        self.place()

    def place(self):
        main = Gui.getMainWindow()
        view = Gui.activeDocument().activeView() if Gui.activeDocument() else None
        if not view or not hasattr(view, 'graphicsView'):
            return
        widget = view.graphicsView()
        origin = widget.mapTo(main, C.QPoint(0, 0))
        cube = App.ParamGet('User parameter:BaseApp/Preferences/NaviCube').GetInt('CubeSize', 132)
        top = origin.y() + cube + 8
        available = max(160, widget.height() - cube - 16)
        self.scroll.setFixedHeight(min(self.scroll.widget().sizeHint().height()+4, max(60, available-64)))
        self.layout().activate()
        self.resize(self.width(), self.sizeHint().height())
        self.move(max(origin.x(), origin.x()+widget.width()-self.width()-10), top)
        self.raise_()

    def sync(self):
        self.feature_options.sync()
        # FreeCAD restores task-dock visibility after entering the workbench.
        if self.tasks and isValid(self.tasks) and self.tasks.isHidden() == self.details.isChecked():
            self.tasks.setVisible(self.details.isChecked())
        view = self.sketch.ViewObject
        for key, value in [('grid',view.ShowGrid), ('adaptive',view.GridAuto),
                           ('snap',App.ParamGet(SNAP).GetBool('Snap',True) and App.ParamGet(SNAP).GetBool('SnapToGrid',False)),
                           ('profiles',App.ParamGet(PREF).GetBool('SketchProfiles',True)),
                           ('points',App.ParamGet(PREF).GetBool('SketchPoints',True)),
                           ('projected',App.ParamGet(PREF).GetBool('SketchProjected',True)),
                           ('construction_geometry',App.ParamGet(PREF).GetBool('SketchConstruction',True)),
                           ('slice',view.SectionView), ('auto',view.Autoconstraints)]:
            self.widgets[key].setChecked(value)
        for key, dimensions in [('dimensions',True), ('constraints',False)]:
            values = [not self.sketch.Constraints[i].InVirtualSpace for i in constraint_ids(self.sketch,dimensions)]
            state = C.Qt.PartiallyChecked if values and any(values) and not all(values) else C.Qt.Checked if all(values) else C.Qt.Unchecked
            self.widgets[key].setCheckState(state)
            self.widgets[key].setEnabled(bool(values))
        from fusionflow_ribbon import native_action
        for name, button in self.widgets.items():
            if not name.startswith('Sketcher_'):
                continue
            action = native_action(name)
            button.setEnabled(bool(action and action.isEnabled()))
            if action and action.isCheckable():
                button.setCheckable(True);button.setChecked(action.isChecked())
        errors = self.sketch.ConflictingConstraints or self.sketch.RedundantConstraints or self.sketch.MalformedConstraints or self.sketch.PartiallyRedundantConstraints or self.sketch.DoF < 0
        self.problem.setVisible(bool(errors))
        if errors:
            text = 'Konfliktní nebo nadbytečné vazby — otevřít Sketcher details'
            color = '#ffb06a'
        else:
            text = 'Empty Sketch' if not self.sketch.GeometryCount else 'Fully Constrained' if self.sketch.DoF == 0 else '%s degrees of freedom' % self.sketch.DoF
            color = '#77d49b' if self.sketch.DoF == 0 else '#c2cede'
        self.status.setText(text);self.status.setStyleSheet('color:%s;padding:5px 0;' % color)
        self.widgets['find'].setEnabled(self.sketch.DoF > 0 and not errors)
        show_profiles = App.ParamGet(PREF).GetBool('SketchProfiles',True)
        self.profiles.update(show_profiles)
        self.presentation.update()
        self.profile_status.setVisible(show_profiles)
        self.profile_status.setText('Profiles unavailable — '+self.profiles.error if self.profiles.error else
                                   '%s closed profiles' % self.profiles.count)
        self.profile_status.setStyleSheet('color:#9bbbd5;padding-bottom:4px;')
        self.place()

    def dispose(self):
        self.presentation.close()
        self.feature_options.dispose()
        self.profiles.close()
        if self.tasks and isValid(self.tasks):
            self.tasks.setVisible(self.tasks_visible)
        self.hide();self.deleteLater()


class SketchManager:
    def __init__(self):
        self.palette = None
        from fusionflow_sketch_edit import DimensionEditor
        self.dimension_editor=DimensionEditor()
        self.timer = C.QTimer(Gui.getMainWindow())
        self.timer.timeout.connect(self.update);self.timer.start(250)

    def update(self):
        sketch = active_sketch()
        if self.palette and (not isValid(self.palette) or self.palette.sketch != sketch):
            if isValid(self.palette):
                self.palette.dispose()
            self.palette = None
        if sketch and self.palette is None:
            self.palette = SketchPalette(sketch)
        if self.palette:
            self.palette.sync()

    def close(self):
        self.dimension_editor.close()
        self.timer.stop();self.timer.deleteLater()
        if self.palette and isValid(self.palette):
            self.palette.dispose()


def install():
    global _manager
    from fusionflow_sketch_view import configure
    configure()
    pref = App.ParamGet(PREF)
    if not pref.GetBool('SketchPaletteConfigured',False):
        App.ParamGet('User parameter:BaseApp/Preferences/Mod/Sketcher').SetBool('LeaveSketchWithEscape',False)
        pref.SetBool('SketchPaletteConfigured',True)
    if _manager is None:
        _manager = SketchManager()


def uninstall():
    global _manager
    if _manager:
        _manager.close();_manager = None
