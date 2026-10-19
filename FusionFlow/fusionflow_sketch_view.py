"""Sketch presentation using native colours, grid, picking and solved geometry."""
import math
import FreeCAD as App
import FreeCADGui as Gui
from pivy import coin

PREF = 'User parameter:BaseApp/Preferences/Mod/FusionFlow'
GENERAL = 'User parameter:BaseApp/Preferences/Mod/Sketcher/General'


def configure():
    pref = App.ParamGet(PREF)
    view = App.ParamGet('User parameter:BaseApp/Preferences/View')
    if not pref.GetBool('SketchReadable32Configured',False):
        for name,size in {'ConstraintSymbolSize':16,'EditSketcherFontSize':18}.items():
            view.SetInt(name,max(size,view.GetInt(name,size)))
        pref.SetBool('SketchReadable32Configured',True)
    if pref.GetBool('SketchAppearance12Configured', False):
        return
    for name, color in {
        'EditedEdgeColor':0x319dc0ff, 'FullyConstraintElementColor':0xe0e5eaff,
        'FullyConstrainedColor':0xe0e5eaff, 'ConstructionColor':0xe5a55dff,
        'FullyConstraintConstructionElementColor':0xe5c69eff,
        'InternalAlignedGeoColor':0x8296b0ff, 'FullyConstraintInternalAlignmentColor':0xb3bdcaff,
        'ExternalColor':0xb298d9ff, 'ExternalDefiningColor':0xb298d9ff,
        'ConstrainedDimColor':0xd3d8dfff, 'ConstrainedIcoColor':0xc7ced8ff,
        'NonDrivingConstrDimColor':0x9da6b3ff, 'ExprBasedConstrDimColor':0xa6bfe2ff,
        'DeactivatedConstrDimColor':0x727d8bff, 'InvalidSketchColor':0xf26968ff,
        'CursorTextColor':0xe5eaf0ff, 'HighlightColor':0x83d6f0ff,
        'SelectionColor':0x5abdeaff, 'AxisXColor':0x98545aff, 'AxisYColor':0x6c955eff,
    }.items():
        view.SetUnsigned(name,color)
    view.SetInt('MarkerSize',5)
    general = App.ParamGet(GENERAL)
    for name,value in {'GridSizePixelThreshold':10,'GridNumberSubdivision':5,
                       'GridLinePattern':65535,'GridDivLinePattern':65535,
                       'GridLineWidth':1,'GridDivLineWidth':1,'GridTransparency':0}.items():
        general.SetInt(name,value)
    general.SetUnsigned('GridLineColor',0x414954ff)
    general.SetUnsigned('GridDivLineColor',0x59626eff)
    general.SetBool('ShowGrid',True);general.SetBool('GridAuto',True)
    sketch=App.ParamGet('User parameter:BaseApp/Preferences/Mod/Sketcher')
    sketch.SetBool('HideUnits',True);sketch.SetBool('ShowDimensionalName',False)
    lines=App.ParamGet('User parameter:BaseApp/Preferences/Mod/Sketcher/View')
    lines.SetInt('ExternalPattern',65535);lines.SetInt('ExternalDefiningPattern',65535)
    general.GetGroup('GridSize').SetString('GridSize','5 mm')
    App.ParamGet('User parameter:BaseApp/Preferences/Mod/Sketcher/Tools').SetInt('OnViewParameterVisibility',1)
    snap=App.ParamGet('User parameter:BaseApp/Preferences/Mod/Sketcher/Snap')
    snap.SetBool('Snap',True);snap.SetBool('SnapToGrid',True)
    pref.SetBool('SketchGrid',True);pref.SetBool('SketchAdaptive',True)
    pref.SetBool('SketchAppearance12Configured',True)


def named(root, name):
    search = coin.SoSearchAction();search.setName(name);search.setSearchingAll(True)
    search.apply(root)
    return search.getPath().getTail() if search.getPath() else None


def nodes(root, node_type):
    search = coin.SoSearchAction();search.setType(node_type.getClassTypeId())
    search.setInterest(coin.SoSearchAction.ALL);search.setSearchingAll(True);search.apply(root)
    return [p.getTail() for p in search.getPaths()]


class SketchSection:
    """Fill native Slice cuts with transient, unpickable solid cross-sections."""
    def __init__(self, sketch, scene):
        self.sketch=sketch
        self.scene=scene
        self.signature=None
        self.error=''
        self.caps={}
        self.root=coin.SoSwitch();self.root.setName('FusionFlowSketchSection')
        scene.addChild(self.root)

    def update(self):
        from fusionflow_analysis import visible_shapes,section_caps
        from fusionflow_analysis_view import mesh_node,points_node
        from fusionflow_core import global_shape
        self.root.whichChild=coin.SO_SWITCH_NONE
        if not self.sketch.ViewObject.SectionView:return
        edit=Gui.editDocument()
        if not edit:return
        frame=App.Placement(edit.EditingTransform)
        objects=[]
        for obj in visible_shapes(edit.Document,displayed=True):
            if obj.Shape.Solids:objects.append(obj)
        signature=(str(frame),tuple((obj.Name,obj.Shape.hashCode(),str(obj.getGlobalPlacement())) for obj in objects))
        if signature==self.signature:
            self.root.whichChild=coin.SO_SWITCH_ALL
            return
        self.signature=signature;self.root.removeAllChildren();self.caps={};self.error=''
        group=coin.SoSeparator()
        pick=coin.SoPickStyle();pick.style=coin.SoPickStyle.UNPICKABLE;group.addChild(pick)
        light=coin.SoLightModel();light.model=coin.SoLightModel.BASE_COLOR;group.addChild(light)
        for obj in objects:
            try:
                shape=global_shape(obj);caps=section_caps(shape,frame)
                if caps.isNull():continue
                self.caps[obj.Name]=caps
                group.addChild(mesh_node(caps,(.66,.62,.50)))
                edges=[]
                for edge in caps.Edges:
                    vertices=edge.discretize(Deflection=max(.005,shape.BoundBox.DiagonalLength/1000))
                    for a,b in zip(vertices,vertices[1:]):edges.extend((a,b))
                group.addChild(points_node(edges,(.16,.18,.21)))
            except Exception as error:
                self.error='%s: %s'%(obj.Label,error)
                App.Console.PrintWarning('Sketch Slice: '+self.error+'\n')
        self.root.addChild(group);self.root.whichChild=coin.SO_SWITCH_ALL

    def close(self):
        if self.scene.findChild(self.root)>=0:self.scene.removeChild(self.root)
        self.caps.clear()


class SketchPresentation:
    def __init__(self, sketch):
        self.sketch = sketch
        self.view = Gui.activeDocument().activeView()
        self.scene = self.view.getSceneGraph();self.scene.ref()
        self.closed = False
        self.section=SketchSection(sketch,self.scene)
        self.signature = None
        self.labels = coin.SoSeparator();self.labels.setName('FusionFlowSketchScale')
        self.root = coin.SoSwitch()
        skip = coin.SoType.fromName('SoSkipBoundingGroup').createInstance()
        skip.getField('mode').setValue('EXCLUDE_BBOX');self.root.addChild(skip)
        group = coin.SoSeparator();skip.addChild(group)
        pick = coin.SoPickStyle();pick.style=coin.SoPickStyle.UNPICKABLE
        light = coin.SoLightModel();light.model=coin.SoLightModel.BASE_COLOR
        depth = coin.SoDepthBuffer();depth.test=False;depth.write=False
        color = coin.SoBaseColor();color.rgb=(.70,.73,.77)
        font = coin.SoFont();font.name='Arial';font.size=12
        for node in (pick,light,depth,color,font,self.labels):group.addChild(node)
        self.scene.addChild(self.root)
        self.style_defaults = {}
        self.pick_styles = {}
        self.fixed_groups=None
        App.addDocumentObserver(self)
        self.viewport=self.view.graphicsView()
        self.viewport.destroyed.connect(self.close)
        # The user's global Sketch Grid choice also applies to previously saved sketches.
        pref = App.ParamGet(PREF)
        sketch.ViewObject.ShowGrid = pref.GetBool('SketchGrid',True)
        sketch.ViewObject.GridAuto = pref.GetBool('SketchAdaptive',True)
        if sketch.ViewObject.GridAuto:
            sketch.ViewObject.GridSize = 5

    def update(self):
        if self.closed:return
        self.section.update()
        pref = App.ParamGet(PREF)
        edit = named(self.scene,'Sketch_EditRoot')
        if edit:
            # FreeCAD treats circle/arc centres as construction points. Keep normal
            # points neutral in the dark canvas, while retaining hover/error/projection.
            colors=App.ParamGet('User parameter:BaseApp/Preferences/View')
            normal=[]
            for key in ('EditedEdgeColor','ConstructionColor','FullyConstraintConstructionElementColor'):
                packed=colors.GetUnsigned(key)
                normal.append(tuple(((packed>>shift)&255)/255 for shift in (24,16,8)))
            for material in nodes(edit,coin.SoMaterial):
                if not str(material.getName()).startswith('PointsMaterials_'):continue
                for i,color in enumerate(material.diffuseColor.getValues()):
                    if any(all(abs(color[j]-candidate[j])<1e-5 for j in range(3)) for candidate in normal):
                        material.diffuseColor.set1Value(i,(.85,.88,.91))
            self.update_fixed_curves(edit,colors)
            for style in nodes(edit,coin.SoDrawStyle):
                name = str(style.getName())
                key = 'SketchPoints' if name.startswith('PointsDrawStyle') else \
                      'SketchConstruction' if name=='CurvesConstructionDrawStyle' else \
                      'SketchProjected' if name in ('CurvesExternalDrawStyle','CurvesExternalDefiningDrawStyle') else None
                if key:
                    if style not in self.style_defaults:
                        style.ref();self.style_defaults[style]=style.style.getValue()
                    value = self.style_defaults[style] if pref.GetBool(key,True) else coin.SoDrawStyle.INVISIBLE
                    if style.style.getValue()!=value:style.style=value
            # SoDrawStyle::INVISIBLE alone still participates in Coin picking.
            search=coin.SoSearchAction();search.setType(coin.SoDrawStyle.getClassTypeId())
            search.setInterest(coin.SoSearchAction.ALL);search.setSearchingAll(True);search.apply(edit)
            for path in search.getPaths():
                style=path.getTail()
                if style not in self.style_defaults:continue
                parent=path.getNodeFromTail(1)
                if parent not in self.pick_styles:
                    parent.ref();pick=coin.SoPickStyle();parent.insertChild(pick,0)
                    self.pick_styles[parent]=pick
                self.pick_styles[parent].style=coin.SoPickStyle.UNPICKABLE if style.style.getValue()==coin.SoDrawStyle.INVISIBLE else coin.SoPickStyle.SHAPE
            # A two-pixel axis remains readable where a grid line coincides with it.
            axes = named(edit,'RootCrossDrawStyle')
            if axes:axes.lineWidth=2
        self.update_labels()

    def update_fixed_curves(self, edit, colors):
        """Colour native Block geometry without replacing selection/error colours."""
        import Part
        if self.fixed_groups is None:
            self.fixed_groups={}
            for facade in self.sketch.GeometryFacadeList:
                if isinstance(facade.Geometry,Part.Point):continue
                sublayer=2 if facade.InternalType!='None' else 1 if facade.Construction else 0
                layer=facade.GeometryLayerId
                self.fixed_groups.setdefault(layer*10+sublayer,[]).append(facade.Blocked)
        ordinary=[]
        for key in ('FullyConstrainedColor','FullyConstraintElementColor',
                    'FullyConstraintConstructionElementColor','FullyConstraintInternalAlignmentColor'):
            packed=colors.GetUnsigned(key)
            ordinary.append(tuple(((packed>>shift)&255)/255 for shift in (24,16,8)))
        for group,blocked in self.fixed_groups.items():
            material=named(edit,'CurvesMaterials'+str(group))
            if not material or material.diffuseColor.getNum()!=len(blocked):continue
            for i,fixed in enumerate(blocked):
                color=material.diffuseColor[i]
                if fixed and any(all(abs(color[j]-base[j])<1e-5 for j in range(3)) for base in ordinary):
                    material.diffuseColor.set1Value(i,(.40,.77,.48))

    def slotChangedObject(self,obj,prop):
        if obj==self.sketch and prop in ('Geometry','Constraints'):
            self.fixed_groups=None

    def update_labels(self):
        visible = self.sketch.ViewObject.ShowGrid
        self.root.whichChild=coin.SO_SWITCH_ALL if visible else coin.SO_SWITCH_NONE
        if not visible:return
        # The edited grid is attached directly to the viewer, not ViewObject.RootNode.
        grid = named(self.scene,'GridRoot')
        if not grid:return
        coordinates=nodes(grid,coin.SoVertexProperty)
        if not coordinates:return
        # The second native grid set contains major lines. Read its exact coordinates
        # rather than approximating spacing independently of Sketcher's Snap.
        points=coordinates[-1].vertex.getValues()
        placement=App.Placement(Gui.editDocument().EditingTransform)
        factor=App.Units.Quantity(1,App.Units.Length).getUserPreferred()[1]
        width,height=self.view.getSize()
        signature=(self.view.getCamera(),width,height,tuple(tuple(p) for p in points),str(placement),factor)
        if signature==self.signature:return
        self.signature=signature;self.labels.removeAllChildren()
        camera=self.view.getCameraNode()
        span=camera.height.getValue() if hasattr(camera,'height') else 2*camera.focalDistance.getValue()*math.tan(camera.heightAngle.getValue()/2)
        unit=span/max(1,min(width,height))
        volume=camera.getViewVolume(width/max(1,height))
        if width<height:volume.scale(height/max(1,width))
        seen=set()
        for a,b in zip(points[::2],points[1::2]):
            axis=0 if abs(a[0]-b[0])<1e-7 else 1
            value=float(a[axis])
            if abs(value)<1e-8 or (axis,value) in seen:continue
            seen.add((axis,value))
            position=App.Vector(value+unit*2,-unit*5,0) if axis==0 else App.Vector(unit*4,value-unit*2,0)
            position=placement.multVec(position)
            screen=volume.projectToScreen(coin.SbVec3f(*position))
            if not (.025<screen[0]<.975 and .04<screen[1]<.96):continue
            label=coin.SoSeparator();move=coin.SoTranslation();move.translation=tuple(position)
            rotate=coin.SoRotation()
            rotation=placement.Rotation.multiply(App.Rotation(App.Vector(0,0,1),-90))
            rotate.rotation=coin.SbRotation(*rotation.Q)
            font=coin.SoFont();font.name='Arial';font.size=unit*26
            text=coin.SoText3();text.parts=coin.SoText3.FRONT;text.string=format(value/factor,'.6g')
            # One consistent unit for all ticks, including very large coordinates.
            for node in (move,rotate,font,text):label.addChild(node)
            self.labels.addChild(label)

    def close(self,*_):
        if self.closed:return
        self.closed=True
        self.section.close()
        App.removeDocumentObserver(self)
        from shiboken6 import isValid
        if isValid(self.viewport):self.viewport.destroyed.disconnect(self.close)
        for style,value in self.style_defaults.items():
            style.style=value;style.unref()
        self.style_defaults.clear()
        for parent,pick in self.pick_styles.items():
            parent.removeChild(pick);parent.unref()
        self.pick_styles.clear()
        self.scene.removeChild(self.root);self.scene.unref()
