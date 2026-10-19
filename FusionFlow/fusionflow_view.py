"""Viewport grid and a compact view bar. No objects are added to the model."""
import math
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore as C, QtGui as G, QtWidgets as W
from pivy import coin
from shiboken6 import isValid
import fusionflow_icons as icons

PREF = 'User parameter:BaseApp/Preferences/Mod/FusionFlow'
_manager = None
BACKGROUND = (.188, .212, .255)
AXES = ((.65,.24,.26), (.28,.54,.33), (.29,.44,.73))


def nice_spacing(value):
    power = 10 ** math.floor(math.log10(max(value, 1e-9)))
    return next(n*power for n in (1,2,5,10) if n*power >= value)


def grid_geometry(camera, size, plane='Auto', adaptive=True, major=10, divisions=5, axes=True):
    """Project the visible area onto an origin plane; bound work at the horizon."""
    width,height = max(1,size[0]),max(1,size[1])
    aspect = width/height
    volume = camera.getViewVolume(aspect)
    if aspect < 1:
        volume.scale(1/aspect)
    direction = camera.orientation.getValue().multVec(coin.SbVec3f(0,0,-1))
    perpendicular = max(range(3),key=lambda i:abs(direction[i]))
    # In oblique views the floor is XY; principal views use their facing plane.
    normal = perpendicular if plane=='Auto' and abs(direction[perpendicular])>.97 else {'XY':2,'XZ':1,'YZ':0}.get(plane,2)
    u,v = [i for i in range(3) if i!=normal]
    span = camera.height.getValue() if hasattr(camera,'height') else 2*camera.focalDistance.getValue()*math.tan(camera.heightAngle.getValue()/2)
    unit = span/min(width,height)
    major = nice_spacing(unit*90) if adaptive else max(major,1e-6)
    step = major/divisions
    if abs(direction[normal]) < .025:
        return [],[],major,normal
    focal = camera.position.getValue()+direction*camera.focalDistance.getValue()
    centre = [focal[u],focal[v]]
    intersections = []
    for x,y in ((0,0),(0,1),(1,0),(1,1),(.5,.5)):
        near,far = volume.projectPointToLine(coin.SbVec2f(x,y))
        ray = far-near
        if abs(ray[normal]) < 1e-10:
            continue
        distance = -near[normal]/ray[normal]
        if not hasattr(camera,'height') and distance < 0:
            continue
        hit = near+ray*distance
        intersections.append((hit[u],hit[v]))
        if (x,y)==(.5,.5):
            centre = [hit[u],hit[v]]
    limit = span*12
    bounds = []
    for axis in range(2):
        values = [p[axis] for p in intersections] or [centre[axis]-span,centre[axis]+span]
        low = max(centre[axis]-limit,min(values)-major)
        high = min(centre[axis]+limit,max(values)+major)
        bounds.append((math.floor(low/major)*major,math.ceil(high/major)*major))
    points,colors = [],[]
    for axis in range(2):
        low,high = bounds[axis]
        begin,end = bounds[1-axis]
        first,last = math.floor(low/step),math.ceil(high/step)
        # Hide subpixel lines at fixed spacing instead of changing its units.
        stride = 1 if step/unit>=5 else divisions
        stride *= max(1,math.ceil((last-first)/stride/500))
        indices = range(math.ceil(first/stride)*stride,last+1,stride)
        indices = sorted(set(indices)|({0} if axes and first<=0<=last else set()))
        for index in indices:
            if index==0 and axes:
                color = AXES[[u,v][1-axis]]
            else:
                color = (.34,.39,.46) if index%divisions==0 else (.255,.295,.35)
            coordinate = index*step
            edge = min(1,(coordinate-low)/max(major,(high-low)*.12),(high-coordinate)/max(major,(high-low)*.12))
            fade = min(major*3,(end-begin)*.12)
            for along,opacity in ((begin,0),(begin+fade,edge),(end-fade,edge),(end,0)):
                point = [0.,0.,0.]
                point[[u,v][axis]]=coordinate
                point[[u,v][1-axis]]=along
                points.append(point)
                colors.append(tuple(b+(c-b)*max(0,opacity) for b,c in zip(BACKGROUND,color)))
    return points,colors,major,normal


class ViewGrid:
    def __init__(self, view):
        self.view = view
        self.widget = view.graphicsView()
        self.selection_root = view.getSceneGraph()
        self.selection_root.ref()
        self.native_colors = {name:tuple(self.selection_root.getField(name).getValue())
                              for name in ('colorSelection','colorHighlight')}
        self.sketch_colors = None
        self.closed = False
        self.signature = None
        self.normal = 2
        self.root = coin.SoSwitch()
        self.root.ref()
        self.root.setName('FusionFlowLayoutGrid')
        # Exclude decorations from all bounds queries, including view rotation.
        skip = coin.SoType.fromName('SoSkipBoundingGroup').createInstance()
        skip.getField('mode').setValue('EXCLUDE_BBOX')
        self.root.addChild(skip)
        self.group = coin.SoSeparator()
        skip.addChild(self.group)
        self.camera=None
        self.source_camera=None
        self.camera_fields=[]
        pick = coin.SoPickStyle();pick.style=coin.SoPickStyle.UNPICKABLE
        light = coin.SoLightModel();light.model=coin.SoLightModel.BASE_COLOR
        bind = coin.SoMaterialBinding();bind.value=coin.SoMaterialBinding.PER_VERTEX
        self.coords = coin.SoCoordinate3()
        self.color = coin.SoBaseColor()
        self.lines = coin.SoLineSet()
        for node in (pick,light,bind,self.color,self.coords,self.lines):
            self.group.addChild(node)
        # Coin's native background pass isolates the grid's camera/depth state.
        # A SoDepthBuffer in FreeCAD's model graph suppresses native face
        # selection highlighting (1.1.3), even inside a SoSeparator.
        self.render_manager = view.getViewer().getSoRenderManager()
        # SoRenderManager::Superimposition: AUTOREDRAW=0x4, BACKGROUND=0x8.
        self.background = self.render_manager.addSuperimposition(self.root, 0x4 | 0x8)
        self.bar = ViewBar(self)
        self.widget.destroyed.connect(lambda *_:self.close(view_destroyed=True))

    def update(self):
        if self.closed:
            return
        pref = App.ParamGet(PREF)
        edit = Gui.activeDocument().getInEdit()
        sketch = edit if edit and edit.Object.TypeId=='Sketcher::SketchObject' else None
        if bool(sketch) != self.sketch_colors:
            self.sketch_colors = bool(sketch)
            # Native solid selection adds emissive colour to the shaded face.
            # Use a restrained blue; Sketcher's own colour scheme stays intact.
            colors = self.native_colors if sketch else {'colorSelection':(.04,.16,.32), 'colorHighlight':(.09,.21,.37)}
            for name,color in colors.items():
                self.selection_root.getField(name).setValue(*color)
        self.bar.sketch = sketch
        self.bar.place()
        visible = pref.GetBool('LayoutGrid',True) and not sketch
        self.root.whichChild=coin.SO_SWITCH_ALL if visible else coin.SO_SWITCH_NONE
        if not visible:
            self.signature=None
            self.bar.scale.setText(App.Units.Quantity(1,App.Units.Length).getUserPreferred()[2] if sketch else '')
            if sketch:self.bar.scale.setToolTip('Jednotky souřadnic skici')
            return
        camera = self.view.getCameraNode()
        size = self.view.getSize()
        settings = (pref.GetString('GridPlane','Auto'),pref.GetBool('GridAdaptive',True),pref.GetFloat('GridMajor',10),max(2,min(20,pref.GetInt('GridDivisions',5))),pref.GetBool('GridAxes',True))
        signature=(self.view.getCamera(),size,settings)
        if signature==self.signature:
            return
        self.signature=signature
        points,colors,major,self.normal=grid_geometry(camera,size,*settings)
        if camera!=self.source_camera:
            for field in self.camera_fields:field.disconnect()
            if self.camera:self.group.removeChild(self.camera)
            self.source_camera=camera
            self.camera=camera.copy()
            self.camera_fields=[]
            # Share the exact live camera transform, but give the background its
            # own clipping range so the grid extends past the model's bounds.
            for name in ('position','orientation','height','heightAngle','focalDistance','aspectRatio','viewportMapping'):
                if hasattr(camera,name):
                    field=getattr(self.camera,name);field.connectFrom(getattr(camera,name));self.camera_fields.append(field)
            self.camera.nearDistance=.001
            self.camera.farDistance=1e12
            self.group.insertChild(self.camera,0)
        self.lines.numVertices.setNum(0)
        self.coords.point.setNum(0);self.color.rgb.setNum(0)
        if points:
            self.coords.point.setValues(points)
            self.color.rgb.setValues(colors)
            self.lines.numVertices.setValues([4]*(len(points)//4))
        self.bar.scale.setText(App.Units.Quantity(major,App.Units.Length).UserString)
        self.bar.scale.setToolTip('Rozteč hlavních čar · '+('YZ','XZ','XY')[self.normal])

    def close(self,view_destroyed=False):
        if self.closed:
            return
        self.closed=True
        for field in self.camera_fields:field.disconnect()
        if not view_destroyed:
            self.render_manager.removeSuperimposition(self.background)
            for name,color in self.native_colors.items():
                self.selection_root.getField(name).setValue(*color)
        self.selection_root.unref()
        self.root.unref()
        if isValid(self.bar):
            self.bar.hide();self.bar.deleteLater()


class ViewBar(W.QFrame):
    def __init__(self, grid):
        super().__init__(grid.widget)
        self.grid=grid
        self.sketch=None
        self.setObjectName('FusionViewBar')
        self.setStyleSheet('''#FusionViewBar {background:#394352;border:1px solid #4b5869;border-radius:3px;}
          #FusionViewBar QToolButton {background:transparent;border:0;padding:4px;color:#dce6f1;}
          #FusionViewBar QToolButton:hover {background:#52677e;}
          #FusionViewBar QLabel {background:transparent;color:#bac7d7;font:10px "Segoe UI";padding:0 5px;}''')
        layout=W.QHBoxLayout(self);layout.setContentsMargins(3,1,3,1);layout.setSpacing(2)
        for picture,tip,callback in [('view_home','Home / Izometrický pohled',self.home),('view_fit','Fit / Celý model',lambda:Gui.runCommand('Std_ViewFitAll'))]:
            button=self.button(picture,tip);button.clicked.connect(callback);layout.addWidget(button)
        self.display_button=self.button('view_display','Display Settings / Nastavení pohledu')
        self.display_menu=W.QMenu(self);self.display_menu.aboutToShow.connect(self.display_menu_items)
        self.display_button.setMenu(self.display_menu);self.display_button.setPopupMode(W.QToolButton.InstantPopup)
        layout.addWidget(self.display_button)
        self.grid_button=self.button('view_grid','Grid / Mřížka a její nastavení')
        self.grid_menu=W.QMenu(self);self.grid_menu.aboutToShow.connect(self.grid_menu_items)
        self.grid_button.setMenu(self.grid_menu);self.grid_button.setPopupMode(W.QToolButton.InstantPopup)
        layout.addWidget(self.grid_button)
        self.scale=W.QLabel();layout.addWidget(self.scale)
        from fusionflow_ribbon import MENU_STYLE
        for menu in (self.display_menu,self.grid_menu):menu.setStyleSheet(MENU_STYLE)
        self.setFixedHeight(30)
        self.show()

    def button(self,picture,tip):
        button=W.QToolButton(self);button.setIcon(icons.icon(picture,True));button.setIconSize(C.QSize(16,16));button.setToolTip(tip)
        return button

    def place(self):
        self.adjustSize()
        self.move(max(4,(self.parentWidget().width()-self.width())//2),max(0,self.parentWidget().height()-self.height()-8))
        self.raise_()

    def home(self):
        self.grid.view.viewAxonometric();self.grid.view.fitAll()

    def checked_action(self,menu,text,checked,callback):
        action=menu.addAction(text);action.setCheckable(True);action.setChecked(checked);action.triggered.connect(callback)
        return action

    def set_preference(self,key,value):
        pref=App.ParamGet(PREF)
        if isinstance(value,bool):pref.SetBool(key,value)
        else:pref.SetString(key,value)
        self.grid.signature=None;self.grid.update()

    def grid_menu_items(self):
        menu=self.grid_menu;menu.clear();pref=App.ParamGet(PREF)
        if self.sketch:
            sketch=self.sketch
            self.checked_action(menu,'Sketch Grid',sketch.ShowGrid,lambda on:setattr(sketch,'ShowGrid',on))
            self.checked_action(menu,'Adaptive',sketch.GridAuto,lambda on:setattr(sketch,'GridAuto',on))
            menu.addSeparator()
            info=menu.addAction('Další volby: Sketcher → Preferences');info.setEnabled(False)
            return
        self.checked_action(menu,'Layout Grid',pref.GetBool('LayoutGrid',True),lambda on:self.set_preference('LayoutGrid',on))
        self.checked_action(menu,'Layout Grid Lock',pref.GetString('GridPlane','Auto')!='Auto',lambda on:self.set_preference('GridPlane',('YZ','XZ','XY')[self.grid.normal] if on else 'Auto'))
        self.checked_action(menu,'Origin Axes',pref.GetBool('GridAxes',True),lambda on:self.set_preference('GridAxes',on))
        menu.addSeparator();menu.addAction('Grid Settings…',self.settings)

    def display_menu_items(self):
        menu=self.display_menu;menu.clear()
        perspective=self.grid.view.getCameraType()=='Perspective'
        for label,camera in [('Orthographic','Orthographic'),('Perspective','Perspective')]:
            self.checked_action(menu,label,perspective==(camera=='Perspective'),lambda _,c=camera:self.grid.view.setCameraType(c))
        menu.addSeparator()
        for name in ('FlatLines','Shaded','Wireframe','AsIs'):
            action=Gui.getMainWindow().findChild(G.QAction,'Std_DrawStyle'+name)
            if action:menu.addAction(action)
        menu.addSeparator()
        for label,command in [('Top','Std_ViewTop'),('Front','Std_ViewFront'),('Right','Std_ViewRight')]:
            menu.addAction(label,lambda cmd=command:Gui.runCommand(cmd))

    def settings(self):
        pref=App.ParamGet(PREF)
        dialog=W.QDialog(self);dialog.setWindowTitle('GRID SETTINGS');dialog.setMinimumWidth(310)
        layout=W.QFormLayout(dialog)
        adaptive=W.QCheckBox('Adaptive');adaptive.setChecked(pref.GetBool('GridAdaptive',True));layout.addRow(adaptive)
        spacing=W.QDoubleSpinBox();spacing.setDecimals(6);spacing.setRange(.000001,1e9);spacing.setSuffix(' mm');spacing.setValue(pref.GetFloat('GridMajor',10));layout.addRow('Major grid spacing',spacing)
        spacing.setEnabled(not adaptive.isChecked());adaptive.toggled.connect(lambda on:spacing.setEnabled(not on))
        divisions=W.QSpinBox();divisions.setRange(2,20);divisions.setValue(pref.GetInt('GridDivisions',5));layout.addRow('Subdivisions',divisions)
        plane=W.QComboBox();plane.addItems(['Auto','XY','XZ','YZ']);plane.setCurrentText(pref.GetString('GridPlane','Auto'));layout.addRow('Plane',plane)
        buttons=W.QDialogButtonBox(W.QDialogButtonBox.Ok|W.QDialogButtonBox.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addRow(buttons)
        if dialog.exec()==W.QDialog.Accepted:
            pref.SetBool('GridAdaptive',adaptive.isChecked());pref.SetFloat('GridMajor',spacing.value());pref.SetInt('GridDivisions',divisions.value());pref.SetString('GridPlane',plane.currentText())
            self.grid.signature=None;self.grid.update()
        dialog.deleteLater()


class ViewManager:
    def __init__(self):
        self.grid=None
        self.timer=C.QTimer(Gui.getMainWindow());self.timer.timeout.connect(self.update);self.timer.start(100)

    def update(self):
        view=Gui.activeDocument().activeView() if Gui.activeDocument() else None
        if view and not hasattr(view,'getSceneGraph'):view=None
        if self.grid and (self.grid.closed or view!=self.grid.view):
            self.grid.close();self.grid=None
        if view and not self.grid:self.grid=ViewGrid(view)
        if self.grid:self.grid.update()

    def close(self):
        self.timer.stop();self.timer.deleteLater()
        if self.grid:self.grid.close()


def install():
    global _manager
    pref=App.ParamGet(PREF)
    if not pref.GetBool('GridConfigured',False):
        sketch=App.ParamGet('User parameter:BaseApp/Preferences/Mod/Sketcher/General')
        sketch.SetBool('ShowGrid',True)
        sketch.SetBool('GridAuto',True)
        pref.SetBool('GridConfigured',True)
    if _manager is None:_manager=ViewManager()


def uninstall():
    global _manager
    if _manager:_manager.close();_manager=None
