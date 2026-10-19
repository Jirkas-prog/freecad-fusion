"""Fusion-style command ribbon, backed by real FreeCAD commands and menus."""
from pathlib import Path
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore as C, QtGui as G, QtWidgets as W
import fusionflow_icons as icons

ROOT = Path(__file__).parent
PREF = 'User parameter:BaseApp/Preferences/Mod/FusionFlow'
_ribbon = None


def item(label, command='', icon='box', shortcut=''):
    return (label, command, icon, shortcut)


SKETCH = item('Create Sketch', 'FusionFlow_CreateSketch', 'sketch')
EXTRUDE = item('Extrude', 'FusionFlow_Extrude', 'extrude', 'E')
REVOLVE = item('Revolve', 'PartDesign_Revolution', 'revolve')
HOLE = item('Hole', 'PartDesign_Hole', 'hole', 'H')
FILLET = item('Fillet', 'PartDesign_Fillet', 'fillet', 'F')
CHAMFER = item('Chamfer', 'PartDesign_Chamfer', 'chamfer')
SHELL = item('Shell', 'PartDesign_Thickness', 'shell')
COMBINE = item('Combine', 'FusionFlow_Combine', 'combine')
MEASURE = item('Measure', 'FusionFlow_Measure', 'inspect', 'I')
IMPORT = item('Insert CAD', 'Std_Import', 'insert')
SELECT = item('Box Selection', 'Std_BoxSelection', 'select')
LINE = item('Line', 'Sketcher_CreatePolyline', 'line', 'L')
RECT = item('Rectangle', 'Sketcher_CreateRectangle', 'rectangle', 'R')
CIRCLE = item('Circle', 'Sketcher_CreateCircle', 'circle', 'C')
SFILLET = item('Fillet', 'Sketcher_CreateFillet', 'arc')
TRIM = item('Trim', 'Sketcher_Trimming', 'trim', 'T')
OFFSET = item('Offset', 'Sketcher_Offset', 'offset', 'O')
DIM = item('Sketch Dimension', 'Sketcher_Dimension', 'dimension', 'D')
FINISH = item('Finish Sketch', 'Sketcher_LeaveSketch', 'finish')

SOLID_CREATE = [SKETCH, item('Create Form'), item('Derive'), None, EXTRUDE, REVOLVE,
    item('Sweep', 'PartDesign_AdditivePipe', 'surface'), item('Loft', 'PartDesign_AdditiveLoft', 'surface'),
    item('Rib'), item('Web'), item('Emboss'), None, HOLE, item('Thread'), None,
    item('Primitives…', 'PartDesign_CompPrimitiveAdditive', 'box'),
    item('Coil', 'PartDesign_AdditiveHelix', 'revolve'), None,
    ('Pattern', [item('Rectangular Pattern', 'PartDesign_LinearPattern', 'pattern'),
                 item('Circular Pattern', 'PartDesign_PolarPattern', 'pattern')]),
    item('Mirror', 'PartDesign_Mirrored', 'pattern'),
    item('New Body', 'PartDesign_Body', 'box')]
SOLID_MODIFY = [item('Press Pull', '', 'presspull', 'Q'), FILLET, CHAMFER, SHELL,
    item('Draft', 'PartDesign_Draft', 'construct'), item('Scale'), COMBINE,
    item('Offset Face'), item('Replace Face'), item('Split Face'), item('Split Body'), None,
    item('Move / Copy', 'Std_TransformManip', 'move', 'M'), item('Align'),
    item('Delete', 'Std_Delete', 'trim', 'Del'), None,
    item('Appearance', 'Std_SetAppearance', 'image', 'A'),
    item('Compute All', 'Std_Recompute', 'configure', 'F5')]
SKETCH_CREATE = [LINE, item('Single Line', 'Sketcher_CreateLine', 'line'),
    ('Rectangle', [RECT, item('Center Rectangle', 'Sketcher_CreateRectangle_Center', 'rectangle')]),
    ('Circle', [CIRCLE, item('3-Point Circle', 'Sketcher_Create3PointCircle', 'circle')]),
    ('Arc', [item('Center Point Arc', 'Sketcher_CreateArc', 'arc'), item('3-Point Arc', 'Sketcher_Create3PointArc', 'arc')]),
    ('Polygon', [item('Polygon', 'Sketcher_CreateHexagon', 'polygon')]),
    item('Ellipse', 'Sketcher_CreateEllipseByCenter', 'circle'),
    ('Slot', [item('Straight Slot', 'Sketcher_CreateSlot', 'slot'), item('Arc Slot', 'Sketcher_CreateArcSlot', 'slot')]),
    ('Spline', [item('Control Point Spline', 'Sketcher_CreateBSpline', 'line'), item('Fit Point Spline', 'Sketcher_CreateBSplineByInterpolation', 'line'),
                item('Closed Control Point Spline', 'Sketcher_CreatePeriodicBSpline', 'line'), item('Closed Fit Point Spline', 'Sketcher_CreatePeriodicBSplineByInterpolation', 'line')]),
    item('Point', 'Sketcher_CreatePoint', 'select'), item('Text'), None,
    item('Mirror', 'Sketcher_Symmetry', 'pattern'), item('Rectangular Pattern', 'Sketcher_RectangularArray', 'pattern'), None,
    ('Project / Include', [item('Project', 'Sketcher_Projection', 'insert', 'P'), item('Intersect', 'Sketcher_Intersection', 'insert'), item('Carbon Copy', 'Sketcher_CarbonCopy', 'sketch')]), DIM]
SKETCH_MODIFY = [SFILLET, item('Chamfer', 'Sketcher_CreateChamfer', 'chamfer'), item('Blend Curve'),
    OFFSET, None, TRIM, item('Extend', 'Sketcher_Extend', 'line'), item('Break', 'Sketcher_Split', 'line'),
    item('Sketch Scale', 'Sketcher_Scale', 'rectangle'), item('Move / Copy', 'Sketcher_Move', 'move', 'M'),
    item('Rotate', 'Sketcher_Rotate', 'revolve')]
CONSTRAINTS = [DIM, None] + [item(label, 'Sketcher_Constrain'+cmd, 'constraints') for label,cmd in
    [('Coincident','Coincident'),('Horizontal / Vertical','HorVer'),('Parallel','Parallel'),
     ('Perpendicular','Perpendicular'),('Tangent','Tangent'),('Equal','Equal'),('Symmetry','Symmetric'),
     ('Fix / Unfix','Block'),('Horizontal Distance','DistanceX'),('Vertical Distance','DistanceY'),
     ('Angle','Angle'),('Radius','Radius'),('Diameter','Diameter')]] + [None,
    item('Driven / Driving Dimension','Sketcher_ToggleDrivingConstraint','dimension'),
    item('Find Under-Constrained','Sketcher_SelectElementsWithDoFs','select')]
from fusionflow_construct import LABELS as CONSTRUCTION_LABELS
CONSTRUCT = []
for _kind,_label in CONSTRUCTION_LABELS.items():
    if _kind in ('OffsetPlane','CylinderAxis','VertexPoint'):CONSTRUCT.append(None)
    CONSTRUCT.append(item(_label,'FusionFlow_'+_kind,'axis' if 'Axis' in _kind else 'point' if _kind.endswith('Point') else 'construct'))
INSPECT = [MEASURE, item('Interference','FusionFlow_Interference','combine'),
    item('Section Analysis','FusionFlow_Section','section'), None,
    item('Curvature Comb Analysis','FusionFlow_CurvatureComb','spline'),
    item('Curvature Map Analysis','FusionFlow_CurvatureMap','appearance'),
    item('Draft Analysis','FusionFlow_Draft','draft'),
    item('Environment Map Analysis','FusionFlow_Environment','appearance'),
    item('Isocurve Analysis','FusionFlow_Isocurve','surface'),
    item('Zebra Analysis','FusionFlow_Zebra','surface'), None,
    item('Accessibility Analysis','FusionFlow_Accessibility','select'),
    item('Center of Mass','FusionFlow_CenterOfMass','point'),
    item('Minimum Radius Analysis','FusionFlow_MinimumRadius','arc'),None,
    item('Navigator','FusionFlow_Navigator','select'),
    item('Display Component Colors','FusionFlow_ComponentColors','appearance'),
    item('Display Mesh Face Groups','FusionFlow_MeshGroups','mesh'),
    item('History','FusionFlow_History','history'),
    item('Sustainability Insights · information','FusionFlow_Sustainability','inspect'),None,
    item('Check Geometry','Part_CheckGeometry','inspect'),None,
    item('Native Measure','Std_Measure','inspect'),
    item('Fit', 'Std_ViewFitAll', 'select'),
    item('Isometric', 'Std_ViewIsometric', 'box'), item('Top', 'Std_ViewTop', 'rectangle'),
    item('Front', 'Std_ViewFront', 'rectangle'), item('Right', 'Std_ViewRight', 'rectangle')]
INSPECT_QUICK=[MEASURE,item('Section Analysis','FusionFlow_Section','section')]
INSERT = [IMPORT, item('Insert Image', 'Std_ViewLoadImage', 'image'), item('Export', 'Std_Export', 'insert')]
SELECT_MENU = [SELECT, item('Select All', 'Std_SelectAll', 'select'),
    item('Select Visible', 'Std_SelectVisibleObjects', 'select')]
CONFIGURE = [item('Show / Hide Sketches', 'FusionFlow_Sketches', 'sketch'),
    item('Preferences', 'Std_DlgPreferences', 'configure'), item('Customize', 'Std_DlgCustomize', 'configure')]
ASSEMBLE = [item('Assembly Workbench', '@AssemblyWorkbench', 'assemble')]

MENU_STYLE = '''QMenu {background:#454f60;color:#f0f3f7;border:1px solid #657082;padding:4px 0;font:12px "Segoe UI";}
QMenu::item {padding:5px 32px 5px 9px;min-width:177px;background:transparent;color:#f0f3f7;}
QMenu::item:selected {background:#546b83;} QMenu::item:disabled {color:#8f9aa9;}
QMenu::separator {height:1px;background:#8390a3;margin:5px 8px;}
QMenu::icon {padding-left:6px;}'''

CHROME_STYLE = '''
QWidget {font:12px "Segoe UI";}
QMainWindow {background:#303641;}
QMainWindow::separator {background:#303641;width:4px;height:4px;}
QDockWidget {color:#e1e7ef;background:#394352;font:12px "Segoe UI";}
QDockWidget::title {background:#3b4656;padding:5px;}
QDockWidget QWidget {background:#3b4555;color:#e1e7ef;}
QDockWidget QTreeView, QDockWidget QListView {background:#343e4c;color:#e3e9f2;border:0;alternate-background-color:#3a4556;selection-background-color:#526d86;}
QDockWidget QTreeView::item, QDockWidget QListView::item {padding:3px;}
QDockWidget QTreeView::item {color:#e3e9f2;}
QDockWidget QTreeView::item:selected {color:white;background:#526d86;}
QDockWidget QHeaderView::section {background:#424e60;color:#e1e7ef;border:0;padding:4px;}
QDockWidget QLineEdit, QDockWidget QAbstractSpinBox, QDockWidget QComboBox {background:#2f3846;border:1px solid #65738a;border-radius:2px;padding:4px;color:#f1f4f8;}
QDockWidget QPushButton {background:#48586c;border:1px solid #718199;border-radius:2px;padding:5px 10px;color:#f1f4f8;}
QDockWidget QPushButton:hover {background:#56718d;}
QDockWidget QTabBar::tab {background:#3b4555;color:#c8d6e9;padding:5px 14px;border:0;}
QDockWidget QTabBar::tab:selected {background:#4b6078;color:white;}
QTabWidget::pane {border:0;background:#303641;}
QTabBar::tab {background:#394352;color:#c8d6e9;border:0;padding:5px 14px;}
QTabBar::tab:selected {background:#4b6078;color:white;}
QMdiArea {background:#303641;}
QStatusBar, QStatusBar QWidget {background:#394352;color:#c5cfde;}
QToolTip {background:#222b38;color:#f3f6fa;border:1px solid #75869c;padding:6px;}
'''

RIBBON_STYLE = '''
#FusionRibbon, #FusionRibbon QWidget {background:#394352;color:#e4ebf5;font:12px "Segoe UI";}
#FusionRibbon QToolButton {background:transparent;border:0;border-radius:0;padding:2px;}
#FusionRibbon QToolButton:hover, #FusionRibbon QToolButton:checked {background:#50667d;}
#FusionRibbon QToolButton:disabled {color:#8290a3;}
#FusionRibbon QToolButton::menu-indicator {image:none;width:0;}
#FusionRibbon QToolButton[groupFooter="true"] {font:11px "Segoe UI";letter-spacing:1px;}
#FusionRibbon #DesignButton {border:1px solid #77869b;border-radius:4px;font-weight:600;margin:6px;}
#FusionRibbon #QuickStrip, #FusionRibbon #QuickStrip QWidget {background:#252c36;}
#FusionRibbon #QuickStrip QToolButton:hover {background:#50667d;}
#FusionRibbon QTabBar::tab {background:#394352;color:#d2ddec;border:0;border-bottom:3px solid transparent;padding:5px 18px;font:11px "Segoe UI";}
#FusionRibbon QTabBar::tab:selected {color:white;border-bottom:3px solid #ebeff5;}
#FusionRibbon QTabBar::tab:disabled {color:#7f8c9d;}
#FusionRibbon QTabBar::tab:hover {background:#465468;}
#FusionRibbon QScrollArea, #FusionRibbon QScrollArea QWidget {border:0;}
#FusionRibbon QFrame[groupSeparator="true"] {background:#566173;max-width:1px;}
#FusionRibbon QScrollBar:horizontal {height:5px;background:#303946;}
#FusionRibbon QScrollBar::handle:horizontal {background:#65758a;min-width:25px;}
#FusionRibbon QScrollBar::add-line:horizontal, #FusionRibbon QScrollBar::sub-line:horizontal {width:0;}
'''


def icon(name, small=False):
    return icons.icon(name,small)


def native_action(name):
    command = Gui.Command.get(name) if name in Gui.listCommands() else None
    if command:
        result = command.getAction()
        return (result[0] if result else None) if isinstance(result, (tuple,list)) else result


class DocumentTabs(W.QTabBar):
    """Mirror MDI windows without reparenting FreeCAD's private tab widget."""
    def __init__(self, main):
        super().__init__()
        self.setObjectName('DocumentTabs')
        self.mdi=main.findChild(W.QMdiArea)
        self.windows=[]
        self.hidden_tabs={}
        self.old_margins=None
        self.setExpanding(False)
        self.setDrawBase(False)
        self.setUsesScrollButtons(True)
        self.setTabsClosable(True)
        self.setElideMode(C.Qt.ElideRight)
        self.setSizePolicy(W.QSizePolicy.Expanding,W.QSizePolicy.Fixed)
        self.setFixedHeight(28)
        self.setStyleSheet('QTabBar::tab {background:#252c36;color:#bcc8d8;border:0;padding:4px 12px;margin-right:2px;font:12px "Segoe UI";} QTabBar::tab:selected {background:#394352;color:#f4f6fa;} QTabBar::tab:hover {background:#465468;}')
        self.currentChanged.connect(self.activate)
        self.tabCloseRequested.connect(self.close_window)

    def tabSizeHint(self,index):
        size=super().tabSizeHint(index)
        return C.QSize(max(100,min(215,size.width())),28)

    def sync(self):
        if not self.mdi:
            return
        windows=self.mdi.subWindowList(W.QMdiArea.CreationOrder)
        blocker=C.QSignalBlocker(self)
        if windows!=self.windows:
            while self.count():
                self.removeTab(0)
            self.windows=windows
            for window in windows:
                self.addTab('')
        for index,window in enumerate(windows):
            title=window.windowTitle().replace('[*]','*' if window.isWindowModified() else '')
            self.setTabText(index,title)
            self.setTabToolTip(index,title)
        active=self.mdi.activeSubWindow()
        self.setCurrentIndex(windows.index(active) if active in windows else -1)
        del blocker
        # Keep TabbedView and native close/save handling. Only its redundant bar is hidden.
        for bar in self.mdi.findChildren(W.QTabBar):
            if bar.parentWidget() is self.mdi:
                if self.old_margins is None:
                    self.old_margins=self.mdi.viewportMargins()
                if bar not in self.hidden_tabs:
                    self.hidden_tabs[bar]=(bar.isVisible(),bar.styleSheet(),bar.minimumHeight(),bar.maximumHeight())
                    bar.setStyleSheet('QTabBar::tab {height:0;min-height:0;max-height:0;padding:0;margin:0;border:0;} QTabBar::close-button {width:0;height:0;margin:0;padding:0;image:none;}')
                    bar.setFixedHeight(0)
                bar.hide()
        if self.hidden_tabs:
            self.mdi.setViewportMargins(0,0,0,0)

    def activate(self,index):
        if Gui.Control.activeDialog():
            self.sync()
            return
        if 0<=index<len(self.windows) and self.windows[index] in self.mdi.subWindowList():
            self.mdi.setActiveSubWindow(self.windows[index])

    def close_window(self,index):
        if Gui.Control.activeDialog():
            self.sync()
            return
        if 0<=index<len(self.windows) and self.windows[index] in self.mdi.subWindowList():
            # QMdiSubWindow.close invokes FreeCAD's own save/discard/cancel prompt.
            self.windows[index].close()
            self.sync()

    def restore(self):
        if self.mdi:
            for bar in self.mdi.findChildren(W.QTabBar):
                if bar in self.hidden_tabs:
                    visible,style,minimum,maximum=self.hidden_tabs[bar]
                    bar.setStyleSheet(style)
                    bar.setMinimumHeight(minimum)
                    bar.setMaximumHeight(maximum)
                    bar.setVisible(visible)
            if self.old_margins is not None:
                self.mdi.setViewportMargins(self.old_margins)


class RibbonGroup(W.QWidget):
    """One command group; its full and compact views share the same menu."""
    def __init__(self, ribbon, title, visible, entries):
        super().__init__()
        self.title=title;self.mode='full'
        self.setObjectName('Group_'+title.replace(' ','_'))
        self.setSizePolicy(W.QSizePolicy.Fixed,W.QSizePolicy.Fixed)
        outer=W.QHBoxLayout(self);outer.setContentsMargins(6,0,0,0);outer.setSpacing(6)
        column=W.QVBoxLayout();column.setSpacing(0);outer.addLayout(column)
        self.row=W.QWidget();row=W.QHBoxLayout(self.row);row.setContentsMargins(0,0,0,0)
        sketch=ribbon.context=='SKETCH';row.setSpacing(1 if sketch else 3)
        for spec in visible:
            button=W.QToolButton();button.setObjectName('Ribbon_'+spec[1])
            action=ribbon.action(spec,button);button.setDefaultAction(action)
            button.setToolButtonStyle(C.Qt.ToolButtonIconOnly)
            button.setToolTip(spec[0]+(' ('+spec[3]+')' if spec[3] else ''))
            button.setFixedSize(48,50)
            button.setIconSize(C.QSize(40,40))
            row.addWidget(button);ribbon.widgets.append(action)
        column.addWidget(self.row)
        # Some pinned commands are absent from the original footer menu. Keep
        # them reachable when their icons collapse (e.g. Insert Image / Save).
        def commands(items):
            result=set()
            for entry in items:
                if entry is None:continue
                if len(entry)==2:result.update(commands(entry[1]))
                elif entry[1]:result.add(entry[1])
            return result
        available=commands(entries)
        missing=[s for s in visible if s[1] and s[1] not in available]
        complete=missing+([None] if missing and entries else [])+entries
        self.menu=ribbon.menu(complete,self);self.menu.setTitle(title)
        if visible:self.menu.setIcon(icons.command_icon(visible[0][1],visible[0][2]))
        self.compact=W.QToolButton();self.compact.setObjectName('Compact_'+title.replace(' ','_'))
        self.compact.setIcon(self.menu.icon());self.compact.setIconSize(C.QSize(40,40))
        self.compact.setFixedHeight(50)
        self.compact.setSizePolicy(W.QSizePolicy.Expanding,W.QSizePolicy.Fixed)
        self.compact.setMenu(self.menu);self.compact.setPopupMode(W.QToolButton.InstantPopup)
        self.compact.setToolTip(title+' — všechny nástroje skupiny');self.compact.setAccessibleName(title)
        self.compact.setCheckable(True)
        column.addWidget(self.compact);self.compact.hide()
        self.footer=W.QToolButton();self.footer.setProperty('groupFooter',True)
        self.footer.setText(title+' ⌄' if entries else title);self.footer.setFixedHeight(21)
        self.footer.setSizePolicy(W.QSizePolicy.Expanding,W.QSizePolicy.Fixed)
        if entries:
            self.footer.setMenu(self.menu);self.footer.setPopupMode(W.QToolButton.InstantPopup)
        elif visible:self.footer.clicked.connect(lambda:ribbon.run(visible[0]))
        column.addWidget(self.footer)
        separator=W.QFrame();separator.setProperty('groupSeparator',True);separator.setFixedSize(1,71)
        outer.addWidget(separator)

    def widths(self):
        self.ensurePolished()
        footer=self.footer.sizeHint().width()
        return max(self.row.sizeHint().width(),footer)+13, max(48,footer)+13

    def set_mode(self, mode):
        if self.mode!=mode:
            self.mode=mode
            self.row.setVisible(mode=='full');self.compact.setVisible(mode=='compact')
            self.setVisible(mode!='overflow')
        self.setFixedWidth(self.widths()[0 if mode=='full' else 1])


class Ribbon(W.QToolBar):
    def __init__(self):
        super().__init__('FusionFlow Ribbon', Gui.getMainWindow())
        self.setObjectName('FusionFlowRibbon')
        self.setMovable(False)
        self.setFloatable(False)
        self.setAllowedAreas(C.Qt.TopToolBarArea)
        self.setSizePolicy(W.QSizePolicy.Expanding,W.QSizePolicy.Fixed)
        self.main = Gui.getMainWindow()
        self.old_style = self.main.styleSheet()
        self.old_menu_visible = self.main.menuBar().isVisible()
        self.old_status_visible = self.main.statusBar().isVisible()
        self.main.statusBar().hide()
        self.dock_styles={dock:dock.styleSheet() for dock in self.main.findChildren(W.QDockWidget)}
        for dock in self.dock_styles:
            dock.setStyleSheet('QWidget {background:#3b4555;color:#e1e7ef;}\n'+CHROME_STYLE)
        self.hidden_bars = {}
        self.widgets = []
        self.context = None
        self.native_menus = list(self.main.menuBar().actions())
        view=App.ParamGet('User parameter:BaseApp/Preferences/View')
        view.SetBool('Simple',True)
        view.SetBool('Gradient',False)
        view.SetBool('RadialGradient',False)
        view.SetUnsigned('BackgroundColor',0x303641FF)
        main_prefs=App.ParamGet('User parameter:BaseApp/Preferences/MainWindow')
        main_prefs.SetBool('OverlayActive',False)
        self.was_editing=False
        self.main.setStyleSheet(self.old_style+'\n'+CHROME_STYLE)
        self.main.menuBar().hide()
        self.compact_history()
        self.root = W.QWidget()
        self.root.setObjectName('FusionRibbon')
        self.root.setStyleSheet(RIBBON_STYLE)
        self.root.setSizePolicy(W.QSizePolicy.Expanding, W.QSizePolicy.Fixed)
        outer = W.QVBoxLayout(self.root)
        outer.setContentsMargins(0,0,0,0)
        outer.setSpacing(0)
        quick = W.QWidget()
        quick.setObjectName('QuickStrip')
        quick.setFixedHeight(28)
        q = W.QHBoxLayout(quick)
        q.setContentsMargins(8,0,10,0)
        q.setSpacing(5)
        file_button = W.QToolButton()
        file_button.setText('☰  FILE')
        file_button.setToolTip('Původní nabídky FreeCADu')
        full_menu = W.QMenu(file_button)
        full_menu.setStyleSheet(MENU_STYLE)
        for action in self.native_menus:
            full_menu.addAction(action)
        file_button.setMenu(full_menu)
        file_button.setPopupMode(W.QToolButton.InstantPopup)
        q.addWidget(file_button)
        for name in ('Std_New','Std_Open','Std_Save','Std_Undo','Std_Redo'):
            button = W.QToolButton()
            native = native_action(name)
            if native:
                button.setDefaultAction(native)
                button.setIcon(icons.command_icon(name,small=True))
            else:
                button.setText(name[4:])
                button.clicked.connect(lambda checked=False, cmd=name: Gui.runCommand(cmd))
            button.setIconSize(C.QSize(17,17))
            button.setFixedSize(27,25)
            q.addWidget(button)
        self.document_tabs = DocumentTabs(self.main)
        q.addWidget(self.document_tabs,1)
        search = W.QToolButton()
        search.setIcon(icon('search'))
        search.setText('Search  S')
        search.setToolButtonStyle(C.Qt.ToolButtonTextBesideIcon)
        search.clicked.connect(lambda: Gui.runCommand('FusionFlow_Search'))
        q.addWidget(search)
        outer.addWidget(quick)
        body = W.QHBoxLayout()
        body.setContentsMargins(12,0,12,3)
        body.setSpacing(6)
        design = W.QToolButton()
        design.setObjectName('DesignButton')
        design.setText('DESIGN ⌄')
        design.setFixedSize(122,82)
        design_menu = W.QMenu(design)
        design_menu.setStyleSheet(MENU_STYLE)
        for label,wb in [('Design','PartDesignWorkbench'),('Surface','SurfaceWorkbench'),('Mesh','MeshWorkbench'),
                         ('Assembly','AssemblyWorkbench'),('Drawing','TechDrawWorkbench'),('Manufacture','CAMWorkbench')]:
            a = design_menu.addAction(label)
            a.setEnabled(wb in Gui.listWorkbenches())
            a.triggered.connect(lambda checked=False, workbench=wb: self.switch_workbench(workbench))
        extra=design_menu.addMenu('All FreeCAD workbenches')
        extra.setStyleSheet(MENU_STYLE)
        for wb,instance in Gui.listWorkbenches().items():
            a=extra.addAction(getattr(instance,'MenuText',wb))
            a.triggered.connect(lambda checked=False, workbench=wb:self.switch_workbench(workbench))
        design.setMenu(design_menu)
        design.setPopupMode(W.QToolButton.InstantPopup)
        body.addWidget(design)
        right=W.QVBoxLayout()
        right.setSpacing(0)
        self.tabs=W.QTabBar()
        self.tabs.setStyleSheet('QTabBar::tab {background:#394352;color:#d2ddec;border:0;border-bottom:3px solid transparent;padding:5px 18px;font:11px "Segoe UI";} QTabBar::tab:selected {border-bottom:3px solid #ebeff5;color:white;} QTabBar::tab:disabled {color:#7f8c9d;}')
        self.tabs.setExpanding(False)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setDrawBase(False)
        self.tabs.setFixedHeight(28)
        self.tab_names=['SOLID','SURFACE','MESH','SHEET METAL','PLASTIC','MANAGE','UTILITIES','SKETCH']
        for name in self.tab_names:
            self.tabs.addTab(name)
        for idx in (3,4):
            self.tabs.setTabEnabled(idx,False)
            self.tabs.setTabToolTip(idx,'Tato sada nástrojů Fusionu není v této instalaci dostupná.')
        self.tabs.currentChanged.connect(self.tab_changed)
        right.addWidget(self.tabs)
        self.scroll=W.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(W.QFrame.NoFrame)
        self.scroll.setVerticalScrollBarPolicy(C.Qt.ScrollBarAlwaysOff)
        self.scroll.setHorizontalScrollBarPolicy(C.Qt.ScrollBarAlwaysOff)
        self.scroll.setFixedHeight(84)
        self.groups=[]
        self.reflow_timer=C.QTimer(self)
        self.reflow_timer.setSingleShot(True)
        self.reflow_timer.timeout.connect(self.reflow)
        self.scroll.viewport().installEventFilter(self)
        right.addWidget(self.scroll)
        body.addLayout(right,1)
        outer.addLayout(body)
        self.addWidget(self.root)
        self.setStyleSheet('QToolBar#FusionFlowRibbon {border:0;padding:0;spacing:0;background:#394352;}')
        self.main.addToolBar(C.Qt.TopToolBarArea,self)
        self.main.workbenchActivated.connect(self.workbench_changed)
        self.timer=C.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(350)
        self.workbench_changed()
        self.refresh()
        C.QTimer.singleShot(750,self.fit_window_to_screen)
        if not Gui.Control.activeDialog() and not (Gui.activeDocument() and Gui.activeDocument().getInEdit()):
            tasks=self.main.findChild(W.QDockWidget,'Tasks')
            if tasks:
                tasks.hide()

    def fit_window_to_screen(self):
        """FreeCAD's saved client height can put the frame below the taskbar."""
        if self.main.isMinimized() or self.main.isMaximized() or self.main.isFullScreen():
            return
        available=self.main.screen().availableGeometry()
        frame=self.main.frameGeometry()
        if available.contains(frame):
            return
        borders=frame.size()-self.main.size()
        self.main.resize(min(self.main.width(),available.width()-borders.width()),
                         min(self.main.height(),available.height()-borders.height()))
        frame=self.main.frameGeometry()
        self.main.move(max(available.left(),min(frame.left(),available.right()-frame.width()+1)),
                       max(available.top(),min(frame.top(),available.bottom()-frame.height()+1)))

    def switch_workbench(self, wb):
        if Gui.activeDocument() and Gui.activeDocument().getInEdit():
            W.QMessageBox.information(self.main,'Finish Sketch','Nejprve dokončete otevřenou editaci tlačítkem Finish Sketch / Close.')
            return
        Gui.activateWorkbench(wb)

    def compact_history(self):
        import fusionflow_ui as ui
        timeline=ui._timeline
        self.timeline=timeline
        self.dock_titles={}
        for dock in self.main.findChildren(W.QDockWidget):
            if dock.objectName() in ('Model','Tree view','Property view','Tasks'):
                self.dock_titles[dock]=dock.windowTitle()
                dock.setWindowTitle({'Model':'BROWSER','Tree view':'BROWSER','Property view':'PROPERTIES','Tasks':'TASKS'}[dock.objectName()])
        if not timeline:
            return
        self.history_features=timeline.features()
        timeline.setFeatures(W.QDockWidget.NoDockWidgetFeatures)
        timeline.setFloating(False)
        self.main.addDockWidget(C.Qt.BottomDockWidgetArea,timeline)
        timeline.show()
        timeline.setTitleBarWidget(W.QWidget(timeline))
        timeline.setFixedHeight(40)
        timeline.list.setMinimumHeight(30)
        timeline.list.setMaximumHeight(34)
        timeline.list.setIconSize(C.QSize(20,20))
        timeline.list.setGridSize(C.QSize(27,30))
        timeline.list.setSpacing(0)
        timeline.list.setVerticalScrollBarPolicy(C.Qt.ScrollBarAlwaysOff)
        timeline.list.setStyleSheet('QListView {border:0;background:#394352;} QListView::item {padding:0;border:0;} QListView::item:selected {background:#526d86;} QScrollBar:horizontal {height:5px;background:#303641;} QScrollBar::handle:horizontal {background:#74869c;min-width:18px;} QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal {width:0;}')
        timeline.list.setItemDelegate(HistoryIcons(timeline.list))
        timeline.ghost.hide()
        for button in timeline.findChildren(W.QPushButton):
            button.hide()
        self.history_controls=W.QWidget(timeline)
        controls=W.QHBoxLayout(self.history_controls)
        controls.setContentsMargins(0,0,5,0)
        controls.setSpacing(1)
        self.history_buttons=[]
        for direction,tip,picture in [
            ('first','První krok — náhled',W.QStyle.SP_MediaSkipBackward),
            ('previous','Předchozí krok — náhled',W.QStyle.SP_MediaSeekBackward),
            ('next','Následující krok — náhled',W.QStyle.SP_MediaSeekForward),
            ('end','Konec historie — obnovit výsledný model',W.QStyle.SP_MediaSkipForward)]:
            button=W.QToolButton()
            button.setObjectName('History_'+direction)
            button.setIcon(icon('history_'+direction,True))
            button.setIconSize(C.QSize(16,16))
            button.setFixedSize(23,28)
            button.setToolTip(tip)
            button.setStyleSheet('QToolButton {border:0;background:transparent;} QToolButton:hover {background:#526d86;}')
            button.clicked.connect(lambda checked=False,d=direction:self.navigate_history(d))
            controls.addWidget(button)
            self.history_buttons.append(button)
        timeline.widget().layout().insertWidget(0,self.history_controls)

    def navigate_history(self,direction):
        timeline=self.timeline
        count=timeline.list.count()
        if not count:
            return
        current=timeline.list.history_position
        if direction=='first':
            position=0
        elif direction=='end':
            position=count
        else:
            position=max(0,min(count,current+(-1 if direction=='previous' else 1)))
        timeline.go_to(position)

    def tab_changed(self, index):
        name=self.tab_names[index]
        wb={'SOLID':'PartDesignWorkbench','SURFACE':'SurfaceWorkbench','MESH':'MeshWorkbench','SKETCH':'SketcherWorkbench'}.get(name)
        if wb and Gui.activeWorkbench().name()!=wb:
            if Gui.activeDocument() and Gui.activeDocument().getInEdit():
                self.workbench_changed()
                return
            Gui.activateWorkbench(wb)
        self.build(name)

    def workbench_changed(self,workbench=None):
        # The signal supplies the name before a Python workbench finishes initialization.
        wb=workbench or Gui.activeWorkbench().name()
        name={'PartDesignWorkbench':'SOLID','SketcherWorkbench':'SKETCH','SurfaceWorkbench':'SURFACE','MeshWorkbench':'MESH'}.get(wb,'UTILITIES')
        self.tabs.blockSignals(True)
        self.tabs.setCurrentIndex(self.tab_names.index(name))
        self.tabs.blockSignals(False)
        self.build(name)
        C.QTimer.singleShot(50,self.hide_native_bars)
        from fusionflow_ui import reconcile_shortcuts
        C.QTimer.singleShot(50,reconcile_shortcuts)

    def run(self, spec):
        cmd=spec[1]
        if cmd.startswith('@'):
            self.switch_workbench(cmd[1:])
        elif cmd:
            try:
                Gui.runCommand(cmd)
            except Exception as exc:
                W.QMessageBox.warning(self.main,spec[0],str(exc))
        self.refresh()

    def action(self, spec, parent, small=False):
        label,cmd,picture,key=spec
        a=G.QAction(icons.command_icon(cmd,picture,small), label+('\t'+key if key else ''),parent)
        a.setProperty('FusionIcon',icons.COMMANDS.get(cmd,picture))
        a.setProperty('FusionSmallIcon',small)
        a.setData(cmd)
        a.setToolTip(label if cmd else label+' — není implementováno ve FusionFlow.')
        a.triggered.connect(lambda checked=False,s=spec:self.run(s))
        self.sync_action(a)
        return a

    def sync_action(self,a):
        cmd=a.data()
        if not cmd:
            a.setEnabled(False)
        elif cmd.startswith('@'):
            a.setEnabled(True)
        elif cmd not in Gui.listCommands():
            a.setEnabled(False)
            a.setToolTip('Příkaz není dostupný v této instalaci FreeCADu: '+cmd)
        else:
            source=native_action(cmd)
            a.setEnabled(source.isEnabled() if source else bool(App.ActiveDocument) or cmd.startswith('Std_'))
            if source and source.isCheckable():
                a.setCheckable(True)
                a.setChecked(source.isChecked())
            elif self.context=='SKETCH' and cmd.startswith('Sketcher_Create'):
                import fusionflow_sketch as sketch
                palette=sketch._manager.palette if sketch._manager else None
                family=palette.feature_options.family if palette else ''
                active={'Circle':'Sketcher_CreateCircle','Arc':'Sketcher_CreateArc',
                        'Rectangle':'Sketcher_CreateRectangle','BSpline':'Sketcher_CreateBSplineByInterpolation',
                        'Polygon':'Sketcher_CreateHexagon','Slot':'Sketcher_CreateSlot',
                        'ArcSlot':'Sketcher_CreateArcSlot','Line':'Sketcher_CreateLine'}.get(family)
                a.setCheckable(True);a.setChecked(cmd==active)

    def menu(self, entries, parent):
        menu=W.QMenu(parent)
        menu.setStyleSheet(MENU_STYLE)
        menu.setToolTipsVisible(True)
        for entry in entries:
            if entry is None:
                menu.addSeparator()
            elif len(entry)==2 and isinstance(entry[1],list):
                sub=self.menu(entry[1],menu)
                sub.setTitle(entry[0])
                menu.addMenu(sub)
            else:
                menu.addAction(self.action(entry,menu,True))
        menu.aboutToShow.connect(lambda:self.sync_menu(menu))
        return menu

    def sync_menu(self, menu):
        for a in menu.actions():
            if a.menu():
                self.sync_menu(a.menu())
            elif not a.isSeparator():
                self.sync_action(a)

    def group(self,title,visible,entries,layout):
        group=RibbonGroup(self,title,visible,entries)
        self.groups.append(group)
        layout.addWidget(group)

    def eventFilter(self,obj,event):
        if obj is self.scroll.viewport() and event.type()==C.QEvent.Resize:
            self.reflow_timer.start(0)
        return super().eventFilter(obj,event)

    def reflow(self):
        if not self.groups:return
        available=self.scroll.viewport().width()
        widths=[g.widths() for g in self.groups]
        modes=['full']*len(self.groups)
        total=sum(w[0] for w in widths)
        core=('CREATE','DOCUMENT','MODIFY','CONSTRAINTS')
        secondary=[i for i,g in reversed(list(enumerate(self.groups))) if g.title not in (*core,'FINISH SKETCH')]
        primary=[i for title in reversed(core) for i,g in enumerate(self.groups) if g.title==title]
        more_width=self.more.sizeHint().width()+8
        # Keep drawing tools expanded for as long as possible. Secondary groups
        # compact first, then move into More; Finish Sketch never moves there.
        for indices in (secondary,primary):
            for i in indices:
                if total<=available:break
                if widths[i][1]<widths[i][0]:
                    modes[i]='compact';total-=widths[i][0]-widths[i][1]
            for i in indices:
                if total<=available:break
                if 'overflow' not in modes:total+=more_width
                total-=widths[i][0 if modes[i]=='full' else 1];modes[i]='overflow'
        for group,mode in zip(self.groups,modes):
            group.set_mode(mode)
            group.menu.menuAction().setVisible(mode=='overflow')
        self.more.setVisible('overflow' in modes)
        self.scroll.widget().layout().activate()

    def build(self,name):
        self.context=name
        self.scroll.setFixedHeight(84)
        self.widgets=[]
        self.groups=[]
        old=self.scroll.takeWidget()
        if old:
            old.deleteLater()
        container=W.QWidget()
        layout=W.QHBoxLayout(container)
        layout.setContentsMargins(0,0,0,2)
        layout.setSpacing(0)
        layout.setSizeConstraint(W.QLayout.SetNoConstraint)
        if name=='SKETCH':
            self.group('CREATE',[LINE,RECT,CIRCLE,item('Spline','Sketcher_CreateBSplineByInterpolation','spline'),item('Polygon','Sketcher_CreateHexagon','polygon'),DIM],SKETCH_CREATE,layout)
            self.group('MODIFY',[SFILLET,TRIM,OFFSET],SKETCH_MODIFY,layout)
            self.group('CONSTRAINTS',[CONSTRAINTS[i] for i in (3,6,7,4,5)],CONSTRAINTS,layout)
            self.group('CONFIGURE',[item('Construction Geometry','Sketcher_ToggleConstruction','construction','X')],
                [item('Construction Geometry','Sketcher_ToggleConstruction','configure','X'), item('Sketch Grid','Sketcher_Grid','pattern'),item('Snap','Sketcher_Snap','select')],layout)
            self.group('INSPECT',INSPECT_QUICK,INSPECT,layout)
            self.group('INSERT',[item('Project','Sketcher_Projection','insert','P'),INSERT[1]],SKETCH_CREATE[-2][1],layout)
            self.group('SELECT',[SELECT],SELECT_MENU,layout)
            self.group('FINISH SKETCH',[FINISH],[],layout)
        elif name=='SOLID':
            self.group('CREATE',[SKETCH,EXTRUDE,REVOLVE,HOLE],SOLID_CREATE,layout)
            self.group('MODIFY',[COMBINE,FILLET,SHELL],SOLID_MODIFY,layout)
            self.group('CONFIGURE',[CONFIGURE[0],CONFIGURE[1]],CONFIGURE,layout)
            self.group('CONSTRUCT',[item('Offset Plane','FusionFlow_OffsetPlane','construct')],CONSTRUCT,layout)
            self.group('INSPECT',INSPECT_QUICK,INSPECT,layout)
            self.group('INSERT',[IMPORT,INSERT[1]],INSERT,layout)
            self.group('ASSEMBLE',[ASSEMBLE[0]],ASSEMBLE,layout)
            self.group('SELECT',[SELECT],SELECT_MENU,layout)
        elif name=='SURFACE':
            entries=[item('Surface Filling','Surface_Filling','surface'),item('Boundary Surface','Surface_GeomFillSurface','surface'),item('Sections','Surface_Sections','surface')]
            self.group('CREATE',entries,entries,layout)
            entries=[item('Extend Face','Surface_ExtendFace','surface'),item('Blend Curve','Surface_BlendCurve','arc')]
            self.group('MODIFY',entries,entries,layout)
            self.group('INSPECT',INSPECT_QUICK,INSPECT,layout)
            self.group('INSERT',[IMPORT],INSERT,layout)
        elif name=='MESH':
            entries=[item('Import Mesh','Mesh_Import','insert'),item('Create Mesh','Mesh_FromPartShape','mesh')]
            self.group('CREATE',entries,entries,layout)
            entries=[item('Reduce','Mesh_Decimating','mesh'),item('Smooth','Mesh_Smoothing','surface'),item('Split','Mesh_SplitComponents','combine')]
            self.group('MODIFY',entries,entries,layout)
            self.group('INSPECT',[item('Evaluate Mesh','Mesh_Evaluation','inspect')],[item('Evaluate Mesh','Mesh_Evaluation','inspect')],layout)
        else:
            self.group('DOCUMENT',[item('New','Std_New','sketch'),IMPORT,item('Save','Std_Save','box')],INSERT,layout)
            self.group('CONFIGURE',[CONFIGURE[1],CONFIGURE[2]],CONFIGURE+[item('Macros','Std_DlgMacroExecute','configure')],layout)
            self.group('INSPECT',INSPECT_QUICK,INSPECT,layout)
            self.group('ASSEMBLE',[ASSEMBLE[0]],ASSEMBLE,layout)
        self.more=W.QToolButton();self.more.setObjectName('RibbonMore')
        self.more.setText('MORE ⌄');self.more.setFixedHeight(71)
        self.more.setIcon(icon('more'));self.more.setIconSize(C.QSize(40,40))
        self.more.setToolButtonStyle(C.Qt.ToolButtonTextUnderIcon)
        self.more.setToolTip('Další skupiny nástrojů — při rozšíření okna se vrátí do pásu')
        self.more.setAccessibleName('Další skupiny nástrojů')
        self.more_menu=W.QMenu(self.more);self.more_menu.setStyleSheet(MENU_STYLE)
        for group in self.groups:self.more_menu.addMenu(group.menu)
        self.more.setMenu(self.more_menu);self.more.setPopupMode(W.QToolButton.InstantPopup)
        # Keep Finish Sketch on the right even when the preceding groups overflow.
        layout.insertWidget(len(self.groups)-(1 if name=='SKETCH' else 0),self.more)
        layout.addStretch(1)
        container.setMinimumWidth(0)
        self.scroll.setWidget(container)
        self.reflow()

    def hide_native_bars(self):
        for bar in self.main.findChildren(W.QToolBar):
            if bar is not self and bar.isVisible():
                self.hidden_bars.setdefault(bar.objectName(),bar)
                bar.hide()

    def refresh(self):
        if not self.isVisible():
            return
        self.hide_native_bars()
        self.document_tabs.sync()
        if self.timeline:
            # FreeCAD restores per-workbench dock visibility after activation.
            # History belongs to the document and stays present in every context.
            if self.timeline.isHidden():
                self.timeline.show()
            for button in self.history_buttons:
                button.setEnabled(self.timeline.list.count()>0 and not Gui.Control.activeDialog())
        editing=Gui.activeDocument().getInEdit() if Gui.activeDocument() else None
        sketch_edit=bool(editing and editing.Object.TypeId=='Sketcher::SketchObject')
        if self.was_editing and not sketch_edit and self.context=='SKETCH':
            Gui.activateWorkbench('PartDesignWorkbench')
        self.was_editing=sketch_edit
        if sketch_edit and self.context!='SKETCH':
            self.tabs.setCurrentIndex(7)
        for a in self.widgets:
            self.sync_action(a)
        for group in self.groups:
            actions=[b.defaultAction() for b in group.row.findChildren(W.QToolButton)]
            group.compact.setChecked(any(a.isChecked() for a in actions))
            if group.title=='FINISH SKETCH':group.footer.setEnabled(actions[0].isEnabled())

    def uninstall(self):
        import fusionflow_browser
        fusionflow_browser.uninstall()
        import fusionflow_sketch
        fusionflow_sketch.uninstall()
        import fusionflow_view
        fusionflow_view.uninstall()
        icons.uninstall_browser()
        icons.uninstall_commands()
        self.timer.stop()
        self.main.workbenchActivated.disconnect(self.workbench_changed)
        self.main.setStyleSheet(self.old_style)
        for dock,style in self.dock_styles.items():
            dock.setStyleSheet(style)
        self.main.menuBar().setVisible(self.old_menu_visible)
        self.main.statusBar().setVisible(self.old_status_visible)
        self.document_tabs.restore()
        for dock,title in self.dock_titles.items():
            dock.setWindowTitle(title)
        if self.timeline:
            self.timeline.end_preview()
            self.timeline.setFeatures(self.history_features)
            self.timeline.setTitleBarWidget(None)
            self.timeline.setMinimumHeight(0)
            self.timeline.setMaximumHeight(120)
            self.timeline.list.setGridSize(C.QSize())
            self.timeline.list.setSpacing(3)
            self.timeline.list.setIconSize(C.QSize(28,28))
            self.timeline.list.setStyleSheet('')
            self.timeline.list.setVerticalScrollBarPolicy(C.Qt.ScrollBarAsNeeded)
            self.timeline.list.setMinimumHeight(64)
            self.timeline.list.setMaximumHeight(74)
            self.timeline.list.setItemDelegate(W.QStyledItemDelegate(self.timeline.list))
            self.timeline.widget().layout().removeWidget(self.history_controls)
            self.history_controls.deleteLater()
            self.timeline.ghost.show()
            for button in self.timeline.findChildren(W.QPushButton):
                button.show()
        for bar in self.hidden_bars.values():
            bar.show()
        self.hide()
        self.main.removeToolBar(self)
        self.deleteLater()


class HistoryIcons(W.QStyledItemDelegate):
    def paint(self,painter,option,index):
        painter.save()
        if index.row()>=self.parent().history_position:
            painter.setOpacity(0.3)
        super().paint(painter,option,index)
        painter.restore()

    def initStyleOption(self, option, index):
        super().initStyleOption(option,index)
        option.text=''
        doc=App.ActiveDocument
        obj=doc.getObject(index.data(C.Qt.UserRole)) if doc else None
        if obj:
            import fusionflow_inspect as inspect
            option.icon=icons.status_badge(icons.feature_icon(obj),inspect.diagnostics(obj)[0])

    def sizeHint(self,option,index):
        return C.QSize(27,30)


def install():
    global _ribbon
    if _ribbon is None and App.ParamGet(PREF).GetBool('RibbonEnabled',True):
        _ribbon=Ribbon()
        icons.install_browser()
        icons.install_commands()
    return _ribbon


def uninstall():
    global _ribbon
    if _ribbon:
        _ribbon.uninstall()
        _ribbon=None
