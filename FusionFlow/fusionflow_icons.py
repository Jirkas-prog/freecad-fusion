"""One icon vocabulary for the ribbon, native browser and feature history."""
from pathlib import Path
from functools import lru_cache
import json
import FreeCAD as App
from PySide import QtCore as C, QtGui as G, QtWidgets as W

ROOT=Path(__file__).parent/'icons'
PACK=ROOT/'public'
MANIFEST=json.loads((PACK/'manifest.json').read_text(encoding='utf-8'))['icons']
_browsers={}
_actions={}

@lru_cache(maxsize=256)
def icon(name, small=False):
    return G.QIcon(icon_path(name,small))

def icon_path(name,small=False):
    if name in MANIFEST:
        return str(PACK/MANIFEST[name]['16' if small else '32']['file'])
    local=ROOT/(name+'.svg')
    return str(local if local.exists() else ROOT/'ribbon'/(name+'.svg'))

ANALYSIS_ICONS={'Section':'section','Measure':'inspect','Interference':'combine','CenterOfMass':'point',
                'CurvatureComb':'spline','Isocurve':'surface','CurvatureMap':'appearance','Draft':'draft',
                'Accessibility':'select','MinimumRadius':'arc','Zebra':'surface','Environment':'appearance',
                'ComponentColors':'appearance','MeshGroups':'mesh'}

FEATURES={
    'Sketcher::SketchObject':'sketch_feature','PartDesign::Body':'body',
    'PartDesign::Pad':'extrude','PartDesign::Pocket':'boolean_cut',
    'PartDesign::Fillet':'fillet','PartDesign::Chamfer':'chamfer',
    'PartDesign::Revolution':'revolve','PartDesign::Groove':'revolve',
    'PartDesign::Hole':'hole','PartDesign::Thickness':'shell','PartDesign::Draft':'draft',
    'PartDesign::AdditivePipe':'sweep','PartDesign::SubtractivePipe':'sweep',
    'PartDesign::AdditiveLoft':'loft','PartDesign::SubtractiveLoft':'loft',
    'PartDesign::AdditiveHelix':'helix','PartDesign::SubtractiveHelix':'helix',
    'PartDesign::LinearPattern':'pattern','PartDesign::PolarPattern':'circular_pattern',
    'PartDesign::Mirrored':'mirror','PartDesign::MultiTransform':'pattern',
    'PartDesign::SubShapeBinder':'project','PartDesign::ShapeBinder':'project',
    'PartDesign::Plane':'construct','PartDesign::Line':'axis','PartDesign::Point':'point',
    'PartDesign::CoordinateSystem':'coordinates','App::Origin':'origin',
    'App::Plane':'construct','App::Line':'axis','App::Part':'component',
    'App::DocumentObjectGroup':'folder','Part::Feature':'body',
}

def feature_name(obj):
    if getattr(obj,'ConstructionMode',''):
        kind=obj.ConstructionMode
        return 'axis' if kind.endswith('Axis') else 'point' if kind.endswith('Point') else 'coordinates' if kind=='UCS' else 'construct'
    if getattr(obj,'AnalysisType',''):
        return ANALYSIS_ICONS.get(obj.AnalysisType,'inspect')
    if obj.TypeId=='PartDesign::Boolean':
        return {'Fuse':'boolean_join','Cut':'boolean_cut','Common':'boolean_intersect'}.get(str(obj.Type),'combine')
    return FEATURES.get(obj.TypeId)

def feature_icon(obj):
    name=feature_name(obj)
    return icon(name,True) if name else obj.ViewObject.Icon


@lru_cache(maxsize=256)
def status_badge(art, severity):
    if not severity:return art
    pix=G.QPixmap(20,20);pix.fill(C.Qt.transparent)
    painter=G.QPainter(pix);art.paint(painter,0,0,18,18)
    icon('status_error' if severity==2 else 'status_warning',True).paint(painter,9,9,11,11)
    painter.end();return G.QIcon(pix)

COMMANDS={
    'PartDesign_'+name.split('::')[-1]:picture for name,picture in FEATURES.items()
    if name.startswith('PartDesign::')}
COMMANDS.update({
    'PartDesign_NewSketch':'sketch','FusionFlow_CreateSketch':'sketch','PartDesign_Body':'new_body',
    'PartDesign_CompPrimitiveAdditive':'box','FusionFlow_Extrude':'extrude',
    'FusionFlow_Combine':'combine','FusionFlow_Sketches':'sketch_feature','FusionFlow_Search':'search',
    'FusionFlow_Move':'move', 'Sketcher_CreateArcSlot':'arc_slot',
    'Sketcher_ViewSketch':'view_look_at',
    'Sketcher_CreatePeriodicBSpline':'spline','Sketcher_CreatePeriodicBSplineByInterpolation':'spline',
    'Sketcher_ConstrainHorVer':'constraints','Sketcher_ToggleDrivingConstraint':'dimension',
    'Sketcher_CreateLine':'line','Sketcher_CreatePolyline':'polyline',
    'Sketcher_CreateRectangle':'rectangle','Sketcher_CreateRectangle_Center':'center_rectangle',
    'Sketcher_CreateCircle':'circle','Sketcher_Create3PointCircle':'circle3',
    'Sketcher_CreateArc':'arc_center','Sketcher_Create3PointArc':'arc3',
    'Sketcher_CreateEllipseByCenter':'ellipse','Sketcher_CreateRegularPolygon':'polygon',
    'Sketcher_CreateHexagon':'polygon','Sketcher_CreateSlot':'slot',
    'Sketcher_CreateBSpline':'spline','Sketcher_CreateBSplineByInterpolation':'spline',
    'Sketcher_CreatePoint':'point','Sketcher_CreateFillet':'arc',
    'Sketcher_Trimming':'trim','Sketcher_Extend':'extend','Sketcher_Split':'split',
    'Sketcher_Offset':'offset','Sketcher_Dimension':'dimension','Sketcher_Projection':'project',
    'Sketcher_ToggleConstruction':'construction','Sketcher_Symmetry':'mirror',
    'Sketcher_RectangularArray':'pattern','Sketcher_Move':'sketch_move','Sketcher_Scale':'scale',
    'Sketcher_LeaveSketch':'finish','Std_Import':'insert','Std_ViewLoadImage':'image',
    'Std_Measure':'inspect','Std_SetAppearance':'appearance','Std_TransformManip':'move',
    'Std_New':'component','Std_Open':'open','Std_Save':'save','Std_Undo':'undo','Std_Redo':'redo',
    '@AssemblyWorkbench':'assemble',
})
for suffix,name in [('Coincident','coincident'),('Parallel','parallel'),('Perpendicular','perpendicular'),
                    ('Tangent','tangent'),('Equal','equal'),('Symmetric','symmetry'),('Block','fix')]:
    COMMANDS['Sketcher_Constrain'+suffix]='constraint_'+name

def command_icon(command, fallback='box', small=False):
    return icon(COMMANDS.get(command,fallback),small)

def install_commands():
    import FreeCADGui as Gui
    available=set(Gui.listCommands())
    for name,picture in COMMANDS.items():
        if name not in available:
            continue
        actions=Gui.Command.get(name).getAction()
        for action in actions if isinstance(actions,(list,tuple)) else [actions]:
            if action and action not in _actions:
                _actions[action]=action.icon()
                action.setIcon(icon(picture,name.startswith('Std_') and name[4:] in ('New','Open','Save','Undo','Redo')))

def uninstall_commands():
    from shiboken6 import isValid
    for action,old in _actions.items():
        if isValid(action):
            action.setIcon(old)
    _actions.clear()

def tree_object(index):
    """FreeCAD 1.1 exposes the stable internal name in hidden column 2."""
    name=index.siblingAtColumn(2).data()
    root=index
    while root.parent().isValid():
        root=root.parent()
    docs=[d for d in App.listDocuments().values() if d.Label==root.data()]
    objects=[d.getObject(name) for d in docs if name and d.getObject(name)]
    # Labels are not identities: two same-label documents may have different diagnostics.
    if len(objects)==1:
        return objects[0]

def replace_artwork(native, obj, picture):
    """Keep native visibility and status overlays; replace only the base artwork."""
    result=G.QIcon()
    for state in (G.QIcon.Off,G.QIcon.On):
        original=native.pixmap(C.QSize(65535,65535),G.QIcon.Normal,state).toImage()
        h=original.height()
        if not h:
            return native
        x=original.width()-h
        body=original.copy(x,0,h,h)
        # h is already a physical pixel size. Passing it as a logical size
        # applies Windows scaling twice, so every base pixel looks like a badge.
        candidates=[obj.ViewObject.Icon.pixmap(C.QSize(h,h),1.0,mode,state).toImage()
                    for mode in (G.QIcon.Normal,G.QIcon.Disabled)]
        differences=[sum(body.pixel(i,j)!=base.pixel(i,j) for i in range(h) for j in range(h))
                     for base in candidates]
        hidden=differences[1]<differences[0]
        base=candidates[int(hidden)]
        replacement=G.QImage(h,h,G.QImage.Format_ARGB32_Premultiplied)
        replacement.fill(C.Qt.transparent)
        painter=G.QPainter(replacement)
        painter.setOpacity(0.52 if hidden else 1)
        picture.paint(painter,0,0,h,h)
        painter.end()
        # Native badges are the exact pixels added after the view provider icon.
        for i in range(h):
            for j in range(h):
                if body.pixel(i,j)!=base.pixel(i,j):
                    replacement.setPixelColor(i,j,body.pixelColor(i,j))
        painter=G.QPainter(original)
        painter.setCompositionMode(G.QPainter.CompositionMode_Source)
        painter.drawImage(x,0,replacement)
        painter.end()
        result.addPixmap(G.QPixmap.fromImage(original),G.QIcon.Normal,state)
    return result

class BrowserIcons(W.QStyledItemDelegate):
    """Retain FreeCAD's native selection, visibility clicks and label editor."""
    def __init__(self, tree):
        super().__init__(tree)
        self.native=tree.itemDelegate()
        self.cache={}

    def initStyleOption(self, option, index):
        self.native.initStyleOption(option,index)
        if index.column()!=0:
            return
        size=option.icon.actualSize(C.QSize(65535,65535))
        height=App.ParamGet('User parameter:BaseApp/Preferences/TreeView').GetInt('IconSize',16)
        if height<=0:
            height=self.parent().style().pixelMetric(W.QStyle.PM_SmallIconSize)
        if size.height()>0:
            option.decorationSize=C.QSize(round(size.width()*height/size.height()),height)
        option.textElideMode=C.Qt.ElideMiddle
        if not index.parent().isValid():
            option.icon=icon('component',True)
            return
        obj=tree_object(index)
        name=feature_name(obj) if obj else None
        if name:
            import fusionflow_inspect as inspect
            # Native invalid-object overlays are already retained below.
            severity=inspect.diagnostics(obj)[0] if obj.TypeId=='Sketcher::SketchObject' and 'Invalid' not in obj.State else 0
            key=(option.icon.cacheKey(),name,severity)
            if key not in self.cache:
                if len(self.cache)>512:
                    self.cache.clear()
                self.cache[key]=replace_artwork(option.icon,obj,status_badge(icon(name,True),severity))
            option.icon=self.cache[key]

    def paint(self,painter,option,index):
        opt=W.QStyleOptionViewItem(option)
        self.initStyleOption(opt,index)
        tree=self.parent()
        if tree.property('FusionOverlayBrowser'):
            painter.save()
            width=min(opt.rect.width(),opt.fontMetrics.horizontalAdvance(opt.text)+opt.decorationSize.width()+14)
            painter.fillRect(C.QRect(opt.rect.x(),opt.rect.y()+1,width,opt.rect.height()-2),G.QColor(57,67,82,175))
            painter.restore()
        artificial=tree.findChild(W.QTreeView,'DocumentTreeItems')
        tree.style().drawControl(W.QStyle.CE_ItemViewItem,opt,painter,artificial or tree)

    def sizeHint(self,option,index):
        return self.native.sizeHint(option,index)

    def createEditor(self,parent,option,index):
        return self.native.createEditor(parent,option,index)

    def setEditorData(self,editor,index):
        self.native.setEditorData(editor,index)

    def setModelData(self,editor,model,index):
        self.native.setModelData(editor,model,index)

def install_browser():
    import FreeCADGui as Gui
    for tree in Gui.getMainWindow().findChildren(W.QTreeWidget):
        if tree.metaObject().className()=='Gui::TreeWidget' and tree not in _browsers:
            delegate=BrowserIcons(tree)
            _browsers[tree]=delegate
            tree.setItemDelegate(delegate)

def uninstall_browser():
    from shiboken6 import isValid
    for tree,delegate in _browsers.items():
        if isValid(tree):
            tree.setItemDelegate(delegate.native)
            delegate.deleteLater()
    _browsers.clear()
