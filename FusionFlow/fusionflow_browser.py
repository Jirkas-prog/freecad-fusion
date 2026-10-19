"""Two presentations of the same document, in FreeCAD's native dock/overlay."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore as C, QtGui as G, QtWidgets as W
from shiboken6 import isValid
import fusionflow_icons as icons
import fusionflow_inspect as inspect

PREF='User parameter:BaseApp/Preferences/Mod/FusionFlow'
OVERLAY='User parameter:BaseApp/MainWindow/DockWindows/OverlayLeft'
STYLE='''
QDockWidget, QDockWidget QWidget {background:transparent;color:#dce4ed;}
QDockWidget QTreeView {background:transparent;alternate-background-color:transparent;
  border:0;selection-background-color:#526f89;outline:0;}
QDockWidget QTreeView::item {padding:1px 2px;color:#dce4ed;}
QDockWidget QTreeView::item:selected {background:#526f89;color:white;}
QDockWidget QTreeView::item:hover {background:rgba(100,126,150,90);}
QDockWidget QTreeView::branch {background:transparent;border:0;}
#FusionBrowserHeader {background:#394352;border:1px solid #536071;}
#FusionBrowserHeader QLabel {background:transparent;font:10px "Segoe UI";letter-spacing:1px;}
#FusionBrowserHeader QToolButton {border:0;background:transparent;color:#bccbd9;padding:0;}
#FusionBrowserHeader QToolButton:hover {background:#52677c;color:white;}
QDockWidget QLineEdit {background:#273341;border:1px solid #7c9cb8;color:white;}
QDockWidget QScrollBar:vertical {background:transparent;width:7px;margin:0;}
QDockWidget QScrollBar::handle:vertical {background:#657182;min-height:24px;border-radius:3px;}
QDockWidget QScrollBar::add-line:vertical,QDockWidget QScrollBar::sub-line:vertical {height:0;}
QDockWidget QScrollBar::add-page:vertical,QDockWidget QScrollBar::sub-page:vertical {background:transparent;}
Gui--PropertyView {background:rgba(52,62,76,235);}
QToolTip {background:#222b38;color:#f3f6fa;border:1px solid #75869c;padding:6px;}
'''
STYLE+='\nQTreeView::branch:closed:has-children {image:url("'+(icons.ROOT/'browser-chevron-right.svg').as_posix()+'");}'
STYLE+='\nQTreeView::branch:open:has-children {image:url("'+(icons.ROOT/'browser-chevron-down.svg').as_posix()+'");}'
_browser=None


class Header(W.QWidget):
    def paintEvent(self,event):
        painter=G.QPainter(self);painter.fillRect(self.rect(),G.QColor('#394352'))
        painter.setPen(G.QColor('#596677'));painter.drawRect(self.rect().adjusted(0,0,-1,-1))


class Rows(W.QStyledItemDelegate):
    def paint(self,painter,option,index):
        opt=W.QStyleOptionViewItem(option);self.initStyleOption(opt,index)
        width=min(opt.rect.width(),opt.fontMetrics.horizontalAdvance(opt.text)+opt.decorationSize.width()+14)
        painter.fillRect(C.QRect(opt.rect.x(),opt.rect.y()+1,width,opt.rect.height()-2),G.QColor(57,67,82,175))
        self.parent().style().drawControl(W.QStyle.CE_ItemViewItem,opt,painter,self.parent())

    def sizeHint(self,option,index):
        size=super().sizeHint(option,index);size.setHeight(22);return size


class GroupedTree(W.QTreeWidget):
    def __init__(self,browser):
        super().__init__();self.browser=browser
        self.setObjectName('FusionGroupedTree');self.setHeaderHidden(True)
        self.setIndentation(18);self.setIconSize(C.QSize(38,16))
        self.setSelectionMode(W.QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(W.QAbstractItemView.NoEditTriggers)
        self.setItemDelegate(Rows(self));self.setContextMenuPolicy(C.Qt.CustomContextMenu)
        self.itemSelectionChanged.connect(browser.select)
        self.itemChanged.connect(browser.rename)
        self.customContextMenuRequested.connect(browser.context_menu)

    def mousePressEvent(self,event):
        item=self.itemAt(event.position().toPoint())
        if item and event.button()==C.Qt.LeftButton:
            rect=self.visualItemRect(item)
            if 0<=event.position().x()-rect.x()<18 and self.browser.targets(item):
                self.browser.visibility(item);event.accept();return
        super().mousePressEvent(event)

    def keyPressEvent(self,event):
        if event.key()==C.Qt.Key_Space:
            for item in self.selectedItems():self.browser.visibility(item)
            event.accept();return
        if event.key()==C.Qt.Key_F2 and self.browser.obj(self.currentItem()):
            self.editItem(self.currentItem());event.accept();return
        super().keyPressEvent(event)

    def mouseDoubleClickEvent(self,event):
        item=self.itemAt(event.position().toPoint())
        if event.button()==C.Qt.LeftButton and self.browser.obj(item):
            self.browser.edit(item);event.accept();return
        super().mouseDoubleClickEvent(event)


class Browser(C.QObject):
    def __init__(self,native_tree,dock):
        super().__init__(Gui.getMainWindow())
        self.main=Gui.getMainWindow();self.dock=dock;self.native_tree=native_tree
        self.native=dock.widget();self.native_panel=native_tree.parentWidget()
        self.closed=False;self.collapsed=False;self.busy=False;self.saved={};self.signature=None
        self.items={};self.expanded={};self.icon_cache={};self.title_sizes={}
        self.old_style=dock.styleSheet();self.old_native_hidden=self.native.isHidden()
        self.old_panel_hidden=self.native_panel.isHidden()
        self.properties=next((w for w in self.native.findChildren(W.QWidget)
                              if w.metaObject().className()=='Gui::PropertyView'),None)
        self.properties_visible=self.properties and not self.properties.isHidden()
        self.content=W.QWidget();self.content.setObjectName('FusionBrowserContent')
        layout=W.QVBoxLayout(self.content);layout.setContentsMargins(3,3,3,0);layout.setSpacing(2)
        self.header=Header();self.header.setObjectName('FusionBrowserHeader');self.header.setFixedHeight(23)
        self.header.setAttribute(C.Qt.WA_StyledBackground,True)
        self.header.setStyleSheet('QWidget#FusionBrowserHeader {background:#394352;border:1px solid #596677;}')
        row=W.QHBoxLayout(self.header);row.setContentsMargins(2,0,3,0);row.setSpacing(3)
        self.fold=W.QToolButton();self.fold.setText('«');self.fold.setFixedSize(17,19)
        self.fold.setToolTip('Sbalit / rozbalit browser');self.fold.clicked.connect(self.toggle)
        row.addWidget(self.fold);row.addWidget(W.QLabel('BROWSER'));row.addStretch()
        self.problems=W.QToolButton();self.problems.setObjectName('FusionBrowserProblems')
        self.problems.setToolButtonStyle(C.Qt.ToolButtonTextBesideIcon)
        self.problem_menu=W.QMenu(self.problems)
        self.problem_menu.aboutToShow.connect(self.fill_problems)
        self.problems.setMenu(self.problem_menu);self.problems.setPopupMode(W.QToolButton.InstantPopup)
        row.addWidget(self.problems)
        self.links=W.QToolButton();self.links.setText('↔');self.links.setFixedSize(23,19)
        self.links.setObjectName('FusionBrowserRelations');self.links.setToolTip('Vstupy a navazující operace vybraného objektu')
        self.link_menu=W.QMenu(self.links);self.link_menu.aboutToShow.connect(self.fill_links)
        self.links.setMenu(self.link_menu);self.links.setPopupMode(W.QToolButton.InstantPopup);row.addWidget(self.links)
        menu_button=W.QToolButton();menu_button.setText('⌄');menu_button.setFixedSize(22,19)
        menu_button.setObjectName('FusionBrowserModes');menu_button.setToolTip('Režim browseru a zobrazení')
        menu=W.QMenu(menu_button)
        from fusionflow_ribbon import MENU_STYLE
        menu.setStyleSheet(MENU_STYLE)
        self.problem_menu.setStyleSheet(MENU_STYLE);self.link_menu.setStyleSheet(MENU_STYLE)
        self.problem_menu.setToolTipsVisible(True);self.link_menu.setToolTipsVisible(True)
        self.modes={};group=G.QActionGroup(menu);group.setExclusive(True)
        for key,label in [('grouped','Fusion · Bodies / Sketches'),('native','FreeCAD · strom operací')]:
            action=menu.addAction(label);action.setCheckable(True);group.addAction(action)
            action.triggered.connect(lambda checked=False,mode=key:self.set_mode(mode));self.modes[key]=action
        menu.addSeparator()
        self.overlay_action=menu.addAction('Průhledně přes model');self.overlay_action.setCheckable(True)
        self.overlay_action.toggled.connect(self.set_overlay)
        self.props=menu.addAction('Vlastnosti objektu · Data / View');self.props.setCheckable(True)
        self.props.setEnabled(self.properties is not None);self.props.toggled.connect(self.show_properties)
        menu_button.setMenu(menu);menu_button.setPopupMode(W.QToolButton.InstantPopup);row.addWidget(menu_button)
        self.minimize=W.QToolButton();self.minimize.setText('−');self.minimize.setFixedSize(19,19)
        self.minimize.setToolTip('Sbalit / rozbalit browser');self.minimize.clicked.connect(self.toggle)
        row.addWidget(self.minimize);layout.addWidget(self.header)
        self.tree=GroupedTree(self);layout.addWidget(self.tree,1)
        self.native.setParent(self.content);layout.addWidget(self.native,1)
        dock.setWidget(self.content);dock.setStyleSheet(STYLE)
        self.native_tree.setProperty('FusionOverlayBrowser',True)
        self.overlay=self.main.findChild(W.QWidget,'OverlayLeft')
        self.old_maximum=self.overlay.maximumHeight() if self.overlay else 16777215
        pref=App.ParamGet(PREF)
        self.set_mode(pref.GetString('BrowserMode','grouped'))
        self.set_overlay(pref.GetBool('BrowserOverlay',True))
        self.timer=C.QTimer(self);self.timer.timeout.connect(self.sync);self.timer.start(250);self.sync()

    def set_pref(self,path,kind,key,value):
        group=App.ParamGet(path);identity=(path,kind,key)
        if identity not in self.saved:
            self.saved[identity]=next((e[2] for e in group.GetContents() if e[1]==key),None)
        getattr(group,'Set'+kind)(key,value)

    def set_overlay(self,on):
        if self.collapsed:self.toggle()
        App.ParamGet(PREF).SetBool('BrowserOverlay',on)
        self.overlay_action.blockSignals(True);self.overlay_action.setChecked(on);self.overlay_action.blockSignals(False)
        pref=App.ParamGet(OVERLAY)
        widgets=[n for n in pref.GetString('Widgets','').split(',') if n and n!=self.dock.objectName()]
        if on:widgets.append(self.dock.objectName())
        self.set_pref(OVERLAY,'String','Widgets',','.join(widgets)+(',' if widgets else ''))
        if on:
            self.set_pref(OVERLAY,'Bool','Transparent',True)
            self.set_pref(OVERLAY,'Int','Width',App.ParamGet(PREF).GetInt('BrowserWidth',290))
            for key in ('AutoHide','EditHide','EditShow','TaskShow'):self.set_pref(OVERLAY,'Bool',key,False)
        self.dock.setStyleSheet(STYLE if on else STYLE+'\n#FusionBrowserContent {background:#343e4c;}')

    def set_mode(self,mode):
        self.mode=mode if mode in self.modes else 'grouped'
        App.ParamGet(PREF).SetString('BrowserMode',self.mode);self.modes[self.mode].setChecked(True)
        self.show_properties(self.props.isChecked())

    def show_properties(self,on):
        native=self.mode=='native'
        self.tree.setVisible(not native and not self.collapsed)
        self.native.setVisible((native or on) and not self.collapsed)
        self.native_panel.setVisible(native)
        if self.properties:self.properties.setVisible(bool(native or on))

    def toggle(self):
        self.collapsed=not self.collapsed;self.show_properties(self.props.isChecked())
        self.fold.setText('»' if self.collapsed else '«');self.minimize.setText('+' if self.collapsed else '−')
        if self.overlay and self.overlay_action.isChecked():
            height=self.header.mapTo(self.overlay,C.QPoint()).y()+self.header.height()+3
            self.overlay.setMaximumHeight(height if self.collapsed else self.old_maximum)

    def obj(self,item):
        key=item.data(0,C.Qt.UserRole) if item else None
        doc=App.listDocuments().get(key[0]) if key else None
        return doc.getObject(key[1]) if doc and key[1] and not key[1].startswith('@') else None

    def targets(self,item):
        obj=self.obj(item)
        if obj:return [obj]
        key=item.data(0,C.Qt.UserRole) if item else None
        if not key or not key[1].startswith('@'):return []
        return [obj for i in range(item.childCount()) for obj in self.targets(item.child(i))]

    def artwork(self,art,visible,severity=0):
        cache=(art.cacheKey(),visible,severity)
        if cache not in self.icon_cache:
            if len(self.icon_cache)>512:self.icon_cache.clear()
            pix=G.QPixmap(38,16);pix.fill(C.Qt.transparent);p=G.QPainter(pix)
            icons.icon('eye' if visible else 'eye_off',True).paint(p,0,0,16,16)
            p.setOpacity(1 if visible else .55);art.paint(p,21,0,16,16)
            if severity:
                p.setOpacity(1);icons.icon('status_error' if severity==2 else 'status_warning',True).paint(p,27,5,11,11)
            p.end();self.icon_cache[cache]=G.QIcon(pix)
        return self.icon_cache[cache]

    def add(self,parent,key,label,art,obj=None,expanded=False):
        item=W.QTreeWidgetItem(parent,[label]);item.setData(0,C.Qt.UserRole,key)
        item.setIcon(0,icons.feature_icon(obj) if obj else icons.icon(art,True))
        item.setExpanded(self.expanded.get(tuple(key),expanded));self.items[tuple(key)]=item
        if obj:
            item.setFlags(item.flags()|C.Qt.ItemIsEditable)
            item.setToolTip(0,obj.Label+' · '+obj.TypeId+'\n'+obj.Document.Name+'#'+obj.Name)
        return item

    def sync_titles(self):
        titles=[self.dock.titleBarWidget()]
        # The overlay has its own hover title, separate from the dock title.
        # Keep it available when the container also holds another panel.
        if self.overlay and self.overlay.isAncestorOf(self.dock) and self.overlay.count()==1:
            titles.append(self.overlay.findChild(W.QWidget,'OverlayTitle',C.Qt.FindDirectChildrenOnly))
        for title,(minimum,maximum) in list(self.title_sizes.items()):
            if not isValid(title):self.title_sizes.pop(title)
            elif title not in titles:
                title.setMinimumHeight(minimum);title.setMaximumHeight(maximum);self.title_sizes.pop(title)
        for title in titles:
            if title:
                if title not in self.title_sizes:self.title_sizes[title]=(title.minimumHeight(),title.maximumHeight())
                title.setFixedHeight(0)

    def sync(self):
        if self.closed:return
        self.sync_titles()
        if self.tree.state()==W.QAbstractItemView.EditingState:return
        doc=App.ActiveDocument;objects=list(doc.Objects) if doc else []
        signature=(doc.Name if doc else None,tuple((o.Name,o.TypeId) for o in objects))
        self.busy=True
        try:
            if signature!=self.signature:
                for key,item in self.items.items():self.expanded[key]=item.isExpanded()
                self.tree.clear();self.items={};self.signature=signature
                if doc:
                    root=self.add(self.tree,(doc.Name,''),doc.Label,'component',expanded=True)
                    bodies=self.add(root,(doc.Name,'@bodies'),'Bodies','folder',expanded=True)
                    sketches=self.add(root,(doc.Name,'@sketches'),'Sketches','folder',expanded=True)
                    origin=self.add(root,(doc.Name,'@origin'),'Origin','origin')
                    construction=None;other=None;analyses=None
                    for obj in objects:
                        if getattr(obj,'AnalysisType',''):
                            if analyses is None:analyses=self.add(root,(doc.Name,'@analysis'),'Analysis','folder',expanded=True)
                            self.add(analyses,(doc.Name,obj.Name),obj.Label,'section',obj)
                        elif obj.TypeId=='PartDesign::Body' or (obj.isDerivedFrom('Part::Feature') and not obj.isDerivedFrom('PartDesign::Feature') and obj.TypeId!='Sketcher::SketchObject' and getattr(obj,'Shape',None) and obj.Shape.Solids):
                            self.add(bodies,(doc.Name,obj.Name),obj.Label,'body',obj)
                        elif obj.TypeId=='Sketcher::SketchObject':self.add(sketches,(doc.Name,obj.Name),obj.Label,'sketch_feature',obj)
                        elif obj.TypeId=='App::Origin':
                            owner=next((o for o in obj.InList if o.TypeId=='PartDesign::Body'),None)
                            node=self.add(origin,(doc.Name,obj.Name),(owner.Label+' · ' if owner else '')+obj.Label,'origin',obj)
                            for axis in obj.OriginFeatures:self.add(node,(doc.Name,axis.Name),axis.Label,'axis',axis)
                        elif getattr(obj,'ConstructionMode','') or obj.TypeId in ('PartDesign::Plane','PartDesign::Line','PartDesign::Point','PartDesign::SubShapeBinder','PartDesign::ShapeBinder'):
                            if construction is None:construction=self.add(root,(doc.Name,'@construction'),'Construction','folder')
                            self.add(construction,(doc.Name,obj.Name),obj.Label,'construct',obj)
                        elif not obj.isDerivedFrom('PartDesign::Feature') and obj.TypeId not in ('App::Line','App::Plane','App::Point'):
                            if other is None:other=self.add(root,(doc.Name,'@other'),'Other objects','folder')
                            self.add(other,(doc.Name,obj.Name),obj.Label,'component',obj)
                    for folder in (bodies,sketches,origin):folder.setHidden(folder.childCount()==0)
            selected={(o.Document.Name,o.Name) for o in Gui.Selection.getSelection()}
            findings={o.Name:inspect.diagnostics(o) for o in objects}
            problems=[(o,findings[o.Name]) for o in objects if findings[o.Name][0]]
            self.problems.setVisible(bool(problems))
            self.problems.setText(str(len(problems)))
            self.problems.setIcon(icons.icon('status_error' if any(result[0]==2 for o,result in problems) else 'status_warning',True))
            self.problems.setToolTip('Objekty vyžadující pozornost: %d\nKlikni pro diagnostiku.' % len(problems))
            self.links.setEnabled(len(selected)==1)
            for key,item in self.items.items():
                obj=self.obj(item)
                if not obj:
                    if key[1]=='' and doc:item.setText(0,doc.Label)
                    targets=self.targets(item)
                    if targets:item.setIcon(0,self.artwork(icons.icon('origin' if key[1]=='@origin' else 'folder',True),any(o.Visibility for o in targets)))
                    continue
                if obj.TypeId!='App::Origin':item.setText(0,obj.Label)
                item.setSelected(key in selected)
                result=findings[obj.Name]
                item.setIcon(0,self.artwork(icons.feature_icon(obj),obj.ViewObject.Visibility,result[0]))
                item.setToolTip(0,inspect.tooltip(obj,result))
        finally:self.busy=False

    def fill_problems(self):
        self.problem_menu.clear()
        for obj in App.ActiveDocument.Objects if App.ActiveDocument else []:
            level,notes=inspect.diagnostics(obj)
            if level:
                identity=inspect.key(obj)
                action=self.problem_menu.addAction(icons.status_badge(icons.feature_icon(obj),level),obj.Label,
                    lambda checked=False,k=identity:inspect.edit_diagnostic(k))
                action.setToolTip('\n'.join(notes));action.setData(identity);action.setEnabled(inspect.can_edit(obj))

    def fill_links(self):
        for action in self.link_menu.actions():
            if action.menu():action.menu().deleteLater()
        self.link_menu.clear()
        selected=Gui.Selection.getSelection()
        if len(selected)==1:
            obj=selected[0]
            self.link_menu.addAction(obj.Label).setEnabled(False)
            inspect.add_diagnostics(self.link_menu,obj)
            inspect.add_relations(self.link_menu,obj)

    def select(self):
        if self.busy:return
        Gui.Selection.clearSelection()
        for item in self.tree.selectedItems():
            obj=self.obj(item)
            if obj:Gui.Selection.addSelection(obj)

    def visibility(self,item):
        targets=self.targets(item);show=not any(obj.Visibility for obj in targets)
        for obj in targets:obj.ViewObject.Visibility=show
        self.sync()

    def edit(self,item,*_):
        obj=self.obj(item)
        if not obj or Gui.Control.activeDialog() or Gui.activeDocument().getInEdit():return
        from fusionflow_core import body_of
        body=body_of(obj)
        if body:Gui.activeDocument().activeView().setActiveObject('pdbody',body)
        if obj.TypeId!='PartDesign::Body':
            from fusionflow_ui import edit_feature
            try:edit_feature(obj)
            except Exception as error:App.Console.PrintWarning(str(error)+'\n')

    def rename(self,item,*_):
        if self.busy:return
        obj=self.obj(item)
        if obj and item.text(0)!=obj.Label:
            obj.Document.openTransaction('Rename object');obj.Label=item.text(0);obj.Document.commitTransaction()

    def context_menu(self,point):
        item=self.tree.itemAt(point);obj=self.obj(item)
        if not obj:return
        menu=W.QMenu(self.tree)
        from fusionflow_ribbon import MENU_STYLE
        menu.setStyleSheet(MENU_STYLE)
        menu.setToolTipsVisible(True)
        inspect.add_diagnostics(menu,obj)
        menu.addAction('Upravit / aktivovat',lambda:self.edit(item))
        if getattr(obj, 'FusionFlowCut', ''):
            from fusionflow_ui import edit_feature
            menu.addAction('Upravit nativní Pocket', lambda:edit_feature(obj, native=True))
        menu.addAction('Skrýt' if obj.Visibility else 'Zobrazit',lambda:self.visibility(item))
        menu.addAction('Přejmenovat · F2',lambda:self.tree.editItem(item))
        menu.addAction('Vlastnosti',lambda:self.props.setChecked(True))
        menu.addSeparator();inspect.add_relations(menu,obj)
        from fusionflow_ui import history_objects
        if obj in history_objects(obj.Document):
            identity=inspect.key(obj)
            menu.addAction('Najít v historii',lambda:inspect.reveal(identity))
        menu.exec(self.tree.viewport().mapToGlobal(point))
        menu.deleteLater()

    def close(self):
        if self.closed:return
        self.closed=True;self.timer.stop()
        if self.collapsed:self.toggle()
        if isValid(self.dock):
            self.native.setParent(self.dock);self.dock.setWidget(self.native)
            self.native.setVisible(not self.old_native_hidden);self.native_panel.setVisible(not self.old_panel_hidden)
            if self.properties:self.properties.setVisible(bool(self.properties_visible))
            self.dock.setStyleSheet(self.old_style);self.native_tree.setProperty('FusionOverlayBrowser',False)
            self.content.deleteLater()
        for title,(minimum,maximum) in self.title_sizes.items():
            if isValid(title):title.setMinimumHeight(minimum);title.setMaximumHeight(maximum)
        for (path,kind,key),value in self.saved.items():
            group=App.ParamGet(path)
            if value is None:getattr(group,'Rem'+kind)(key)
            else:getattr(group,'Set'+kind)(key,value)
        self.deleteLater()


def install():
    global _browser
    if _browser:return
    for tree in Gui.getMainWindow().findChildren(W.QTreeWidget):
        if tree.metaObject().className()!='Gui::TreeWidget':continue
        dock=None;parent=tree.parentWidget()
        while parent:
            if isinstance(parent,W.QDockWidget):dock=parent
            parent=parent.parentWidget()
        if dock:_browser=Browser(tree,dock);return


def uninstall():
    global _browser
    if _browser:_browser.close();_browser=None
