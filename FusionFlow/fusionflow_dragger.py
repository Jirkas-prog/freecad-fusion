"""Temporary, pixel-sized Coin controls; nothing is added to the document."""
import math
import FreeCAD as App
import FreeCADGui as Gui
from pivy import coin
from PySide import QtCore
from fusionflow_core import profile_anchor


def color(root, rgb):
    material = coin.SoMaterial()
    material.diffuseColor = rgb
    root.addChild(material)


def lines(root, points, rgb, width=1.5):
    group = coin.SoSeparator()
    color(group, rgb)
    style = coin.SoDrawStyle(); style.lineWidth = width
    group.addChild(style)
    coords = coin.SoCoordinate3(); coords.point.setValues(0, len(points), points)
    group.addChild(coords)
    line = coin.SoLineSet(); line.numVertices.setValue(len(points))
    group.addChild(line); root.addChild(group)


def disk(root, x, radius, rgb):
    color(root, rgb)
    coords = coin.SoCoordinate3()
    coords.point.setValues(0, 40, [(x+radius*math.cos(a*math.tau/40), radius*math.sin(a*math.tau/40), 0) for a in range(40)])
    root.addChild(coords)
    face = coin.SoFaceSet(); face.numVertices.setValue(40)
    root.addChild(face)


def arrow(active=False):
    root = coin.SoSeparator()
    color(root, (.10,.67,.98) if active else (.28,.65,.88))
    coords = coin.SoCoordinate3()
    coords.point.setValues(0, 7, [(5,-3.5,0),(39,-3.5,0),(39,3.5,0),(5,3.5,0),
                                (36,-11,0),(58,0,0),(36,11,0)])
    root.addChild(coords)
    faces = coin.SoFaceSet(); faces.numVertices.setValues(0, 2, [4,3])
    root.addChild(faces)
    lines(root, [(5,-3.5,0),(36,-3.5,0),(36,-11,0),(58,0,0),
                 (36,11,0),(36,3.5,0),(5,3.5,0),(5,-3.5,0)], (.92,.96,1), 2)
    # Invisible geometry is still picked by Coin. The full shaft has a generous
    # 22 px hit area, without drawing a bulky control over the selected face.
    hit = coin.SoSeparator()
    style = coin.SoDrawStyle(); style.style = coin.SoDrawStyle.INVISIBLE
    hit.addChild(style)
    rotation = coin.SoRotation(); rotation.rotation.setValue(coin.SbVec3f(0,0,1), -math.pi/2)
    hit.addChild(rotation)
    position = coin.SoTranslation(); position.translation = (0,30,0)
    hit.addChild(position)
    shaft = coin.SoCylinder(); shaft.radius,shaft.height = 11,56
    hit.addChild(shaft); root.addChild(hit)
    return root


TAPER_RADIUS = 83


def taper_knob(active=False):
    root = coin.SoSeparator()
    disk(root, TAPER_RADIUS, 8, (.91,.95,1))
    disk(root, TAPER_RADIUS, 5.5, (.08,.68,1) if active else (.30,.45,.55))
    disk(root, TAPER_RADIUS, 1.6, (.93,.97,1))
    hit = coin.SoSeparator()
    style = coin.SoDrawStyle(); style.style = coin.SoDrawStyle.INVISIBLE
    hit.addChild(style)
    position = coin.SoTranslation(); position.translation = (TAPER_RADIUS,0,0)
    hit.addChild(position)
    sphere = coin.SoSphere(); sphere.radius = 12
    hit.addChild(sphere); root.addChild(hit)
    return root


class ViewHandles:
    def __init__(self, panel):
        self.panel = panel
        self.view = Gui.activeDocument().activeView()
        self.scene = self.view.getSceneGraph()
        self.root = coin.SoSwitch(); self.root.whichChild = coin.SO_SWITCH_NONE
        self.callbacks = []
        self.syncing = self.dragging = self.closed = False
        self.camera = self.view.getCameraNode()

    def attach(self):
        self.scene.addChild(self.root)
        self.camera_sensor = coin.SoNodeSensor(self.camera_changed,None)
        self.camera_sensor.attach(self.camera)
        self.viewport_size = self.view.getSize()
        self.camera_watcher = QtCore.QTimer()
        self.camera_watcher.setInterval(150)
        self.camera_watcher.timeout.connect(self.watch_camera)
        self.camera_watcher.start()
        from fusionflow_handle_input import HandleInput
        self.editor = HandleInput(self)

    def watch_camera(self):
        if self.closed or self.dragging:return
        camera,size = self.view.getCameraNode(),self.view.getSize()
        if camera != self.camera or size != self.viewport_size:
            self.camera_sensor.detach()
            self.camera = camera
            self.viewport_size = size
            self.camera_sensor.attach(camera)
            self.camera_changed()

    def register(self, dragger, moved, side, angle=False):
        # FreeCAD owns registrations: Pivy's remove*Callback can crash.
        for event,callback in [('addStartCallback',lambda _:self.started(side,angle)),('addValueChangedCallback',moved),('addFinishCallback',self.finished)]:
            handle = self.view.addDraggerCallback(dragger,event,callback)
            self.callbacks.append((dragger,event,handle))

    def started(self,side=0,angle=False):
        self.dragging = True
        self.editor.activate(side,angle)

    def finished(self,*_):
        self.dragging = False
        self.panel.schedule()
        QtCore.QTimer.singleShot(0,self.editor.focus_value)

    def close(self):
        if self.closed:return
        self.closed = True
        self.editor.dispose()
        self.camera_watcher.stop()
        self.camera_watcher.timeout.disconnect(self.watch_camera)
        self.camera_watcher.deleteLater()
        self.camera_sensor.detach()
        for dragger,event,handle in self.callbacks:
            self.view.removeDraggerCallback(dragger,event,handle)
        self.callbacks.clear()
        self.scene.removeChild(self.root)


class ExtrudeHandles(ViewHandles):
    has_taper = True

    def __init__(self, panel):
        super().__init__(panel)
        self.axes,self.draggers,self.flips,self.scales,self.billboards = [],[],[],[],[]
        self.taper_frames,self.taper_draggers,self.taper_scales = [],[],[]
        self.axial_drag = None
        for i in range(2):
            # Annotation uses Coin's delayed pass, preserving the model's depth
            # state and blue face highlight (unlike SoDepthBuffer(test=False)).
            group = coin.SoAnnotation()
            light = coin.SoLightModel(); light.model = coin.SoLightModel.BASE_COLOR
            group.addChild(light)
            pick = coin.SoPickStyle(); pick.style = coin.SoPickStyle.SHAPE_ON_TOP
            group.addChild(pick)
            linear = coin.SoSeparator(); group.addChild(linear)
            axis = coin.SoTransform(); linear.addChild(axis)
            dragger = coin.SoTranslate1Dragger()
            flip,billboard,scale = coin.SoRotation(),coin.SoRotation(),coin.SoScale()
            for part,active in [('translator',False),('translatorActive',True)]:
                art = coin.SoSeparator()
                for node in (billboard,flip,scale,arrow(active)):art.addChild(node)
                dragger.setPart(part,art)
            dragger.setPart('feedback',coin.SoSeparator())
            dragger.setPart('feedbackActive',coin.SoSeparator())
            self.register(dragger, lambda _, index=i, node=dragger: self.moved(index,node), i)
            linear.addChild(dragger)
            self.root.addChild(group)
            self.axes.append(axis); self.draggers.append(dragger)
            self.flips.append(flip); self.scales.append(scale); self.billboards.append(billboard)
            if self.has_taper:
                angular = coin.SoSeparator(); group.addChild(angular)
                frame = coin.SoTransform(); angular.addChild(frame)
                scale = coin.SoScale(); angular.addChild(scale)
                # The arc is decoration, only the circular knob captures clicks.
                guide = coin.SoSeparator()
                no_pick = coin.SoPickStyle(); no_pick.style = coin.SoPickStyle.UNPICKABLE
                guide.addChild(no_pick)
                lines(guide, [(TAPER_RADIUS*math.cos(math.radians(a)),TAPER_RADIUS*math.sin(math.radians(a)),0)
                              for a in range(-90,91,3)], (.49,.60,.68))
                for a in (-90,-45,0,45,90):
                    rad = math.radians(a)
                    lines(guide, [(r*math.cos(rad),r*math.sin(rad),0) for r in (TAPER_RADIUS-3,TAPER_RADIUS+3)], (.65,.76,.83))
                angular.addChild(guide)
                turn = coin.SoRotateDiscDragger()
                turn.setPart('rotator',taper_knob())
                turn.setPart('rotatorActive',taper_knob(True))
                turn.setPart('feedback',coin.SoSeparator())
                turn.setPart('feedbackActive',coin.SoSeparator())
                self.register(turn, lambda _, index=i, node=turn: self.taper_moved(index,node), i, True)
                angular.addChild(turn)
                self.taper_frames.append(frame); self.taper_scales.append(scale); self.taper_draggers.append(turn)
        self.attach()

    def input_options(self,all_fields=False):
        p=self.panel
        result=[(0,False,'Distance',p.distance),(0,True,'Taper Angle',p.taper)]
        if all_fields or p.direction.currentData()=='Two sides':
            result += [(1,False,'Distance 2',p.distance2),(1,True,'Taper Angle 2',p.taper2)]
        return result

    def input_anchor(self,side):
        axis=self.axes[side]
        return axis.translation.getValue()+axis.rotation.getValue().multVec(self.draggers[side].translation.getValue())

    def register(self, dragger, moved, side, angle=False):
        super().register(dragger,moved,side,angle)
        if not angle:
            event='addMotionCallback'
            handle=self.view.addDraggerCallback(dragger,event,lambda _:self.axial_moved(side,dragger))
            self.callbacks.append((dragger,event,handle))

    def camera_changed(self,*_,force=False):
        if self.closed or (self.dragging and not force):return
        cam = self.camera
        height = cam.height.getValue() if hasattr(cam,'height') else 2*cam.focalDistance.getValue()*math.tan(cam.heightAngle.getValue()/2)
        unit = height/max(1,min(self.view.getSize()))
        camera_rotation = cam.orientation.getValue()
        for i,scale in enumerate(self.scales):
            axis_rotation = self.axes[i].rotation.getValue()
            normal = axis_rotation.multVec(coin.SbVec3f(1,0,0))
            distance = self.draggers[i].translation.getValue()[0]
            origin = self.axes[i].translation.getValue()
            anchor = origin + normal*distance
            if not hasattr(cam,'height'):
                depth = -camera_rotation.inverse().multVec(anchor-cam.position.getValue())[2]
                unit = 2*max(depth,1e-6)*math.tan(cam.heightAngle.getValue()/2)/max(1,min(self.view.getSize()))
            screen = camera_rotation.inverse().multVec(normal)
            angle = math.atan2(screen[1],screen[0]) if math.hypot(screen[0],screen[1])>.05 else math.pi/2
            # Rotate art into the screen plane. Its visible size is constant even
            # when the extrusion axis is foreshortened or the view is zoomed.
            facing = coin.SbRotation(coin.SbVec3f(0,0,1),angle)*camera_rotation
            self.billboards[i].rotation = facing*axis_rotation.inverse()
            scale.scaleFactor = (unit,unit,unit)
            if self.has_taper:
                self.taper_frames[i].translation = anchor
                flip = coin.SbRotation(coin.SbVec3f(0,0,1),math.pi if distance<0 else 0)
                self.taper_frames[i].rotation = flip*facing
                self.taper_scales[i].scaleFactor = (unit,unit,unit)
        self.editor.place()

    def started(self,side=0,angle=False):
        super().started(side,angle)
        if not angle:
            node=self.draggers[side]
            normal=self.axes[side].rotation.getValue().multVec(coin.SbVec3f(1,0,0))
            screen=self.camera.orientation.getValue().inverse().multVec(normal)
            projection=math.hypot(screen[0],screen[1])
            if projection<.2 and node.getEvent():
                # A line pointing at the camera has no stable inverse projection.
                # Freeze a screen-space gesture at press time. Cap sensitivity at
                # the transition to native dragging, rather than dividing by zero.
                vector=(screen[0]/projection,screen[1]/projection) if projection>.05 else (0,1)
                self.axial_drag=(side,tuple(node.getEvent().getPosition()),node.translation.getValue()[0],
                                 vector,self.scales[side].scaleFactor.getValue()[0]/.2,node.getProjectorEpsilon())
                node.setProjectorEpsilon(1.0)

    def axial_moved(self,side,node):
        if self.closed or not self.axial_drag or self.axial_drag[0]!=side:return
        _,start,value,vector,unit,_=self.axial_drag
        point=node.getEvent().getPosition()
        delta=((point[0]-start[0])*vector[0]+(point[1]-start[1])*vector[1])*unit
        node.translation=(value+delta,0,0)

    def moved(self,index,dragger):
        if self.closed or self.syncing:return
        p = self.panel
        distance = value = dragger.translation.getValue()[0]
        symmetric = p.direction.currentData()=='Symmetric'
        if symmetric:value = max(0,value)*2
        elif index==1:value = max(0,value)
        if index==0 and p.reverse.isChecked():value = -value
        field = p.distance2 if index==1 and not symmetric else p.distance
        field.setValue(round(value,3))
        self.flips[index].rotation.setValue(coin.SbVec3f(0,0,1),math.pi if distance<0 else 0)
        if symmetric:
            self.syncing = True
            try:self.draggers[1-index].translation = (max(0,distance),0,0)
            finally:self.syncing = False
        self.camera_changed(force=True)
        # Debounced native preview, outside the Coin event callback.
        p.schedule()

    def taper_moved(self,index,dragger):
        if self.closed or self.syncing:return
        vector = dragger.rotation.getValue().multVec(coin.SbVec3f(1,0,0))
        angle = math.degrees(math.atan2(vector[1],vector[0]))
        field = self.panel.taper2 if index==1 and self.panel.direction.currentData()=='Two sides' else self.panel.taper
        field.setValue(round(angle,1))
        # Keep the knob at the allowed value if the user drags past +/-89°.
        self.syncing = True
        try:
            dragger.rotation.setValue(coin.SbVec3f(0,0,1),math.radians(field.value()))
            if self.panel.direction.currentData()=='Symmetric':
                self.taper_draggers[1-index].rotation = dragger.rotation.getValue()
        finally:self.syncing = False
        self.panel.schedule()

    def finished(self,*_):
        if self.axial_drag:
            self.draggers[self.axial_drag[0]].setProjectorEpsilon(self.axial_drag[-1])
            self.axial_drag=None
        super().finished()

    def sync(self):
        if self.closed or self.dragging:return
        p = self.panel; self.syncing = True
        try:
            source,regions = p.profile()
            if not source or not regions or p.extent.currentData()!='Distance':
                self.root.whichChild = coin.SO_SWITCH_NONE
                return
            centre,normal = profile_anchor(source,regions,on_face=True)
            if p.start.currentData()=='offset':centre += normal*p.offset.value()
            symmetric = p.direction.currentData()=='Symmetric'
            two = p.direction.currentData()=='Two sides'
            signed = p.distance.value()*(-1 if p.reverse.isChecked() else 1)
            for i in range(2):
                direction = normal if i==0 else -normal
                if i==1 and two and signed<0:direction = normal
                self.axes[i].translation = tuple(centre)
                self.axes[i].rotation.setValue(coin.SbRotation(coin.SbVec3f(1,0,0),coin.SbVec3f(*direction)))
                distance = abs(signed)/2 if symmetric else signed if i==0 else p.distance2.value()
                self.draggers[i].translation = (distance,0,0)
                self.flips[i].rotation.setValue(coin.SbVec3f(0,0,1),math.pi if distance<0 else 0)
                angle = p.taper2.value() if i==1 and two else p.taper.value()
                self.taper_draggers[i].rotation.setValue(coin.SbVec3f(0,0,1),math.radians(angle))
            self.root.whichChild = coin.SO_SWITCH_ALL if two or symmetric else 0
            self.camera_changed()
        except (ValueError,RuntimeError):self.root.whichChild = coin.SO_SWITCH_NONE
        finally:
            self.syncing = False
            self.editor.refresh()

    def close(self):
        if self.closed:return
        if self.axial_drag:
            self.draggers[self.axial_drag[0]].setProjectorEpsilon(self.axial_drag[-1])
            self.axial_drag=None
        super().close()


class OffsetHandle(ExtrudeHandles):
    """One signed distance along a plane normal, sharing the extrusion arrow."""
    has_taper = False

    def __init__(self, panel, field, label):
        self.offset, self.offset_label = field, label
        super().__init__(panel)

    def input_options(self,all_fields=False):
        return [(0,False,self.offset_label,self.offset)]

    def sync(self):
        if self.closed or self.dragging:return
        self.syncing=True
        try:
            if not self.panel.result:
                self.root.whichChild=coin.SO_SWITCH_NONE
                return
            frame=self.frame()
            normal=frame.Rotation.multVec(App.Vector(0,0,1))
            self.axes[0].translation=tuple(frame.Base)
            self.axes[0].rotation.setValue(coin.SbRotation(coin.SbVec3f(1,0,0),coin.SbVec3f(*normal)))
            self.draggers[0].translation=(self.offset.value(),0,0)
            self.root.whichChild=0
            self.camera_changed()
        except (ValueError,RuntimeError):self.root.whichChild=coin.SO_SWITCH_NONE
        finally:
            self.syncing=False
            self.editor.refresh()

    def moved(self,index,dragger):
        if not self.closed and not self.syncing:
            self.offset.setValue(round(dragger.translation.getValue()[0],3))
            self.camera_changed(force=True)
            self.panel.schedule()


class SectionHandle(OffsetHandle):
    def __init__(self, panel):
        super().__init__(panel,panel.offset,'Section offset')

    def frame(self):
        from fusionflow_analysis import plane_frame,visible_shapes
        from fusionflow_core import global_shape
        p=self.panel
        frame=plane_frame(dict(p.settings(),offset=0),p.references)
        normal=frame.Rotation.multVec(App.Vector(0,0,1))
        bounds=App.BoundBox()
        for obj in visible_shapes(p.doc):bounds.add(global_shape(obj).BoundBox)
        centre=bounds.Center if bounds.isValid() else frame.Base
        frame.Base=centre-normal*normal.dot(centre-frame.Base)
        return frame


class ConstructionOffsetHandle(OffsetHandle):
    def __init__(self, panel):
        super().__init__(panel,panel.widgets['Distance'],'Distance')

    def frame(self):
        from fusionflow_construct import placement
        p=self.panel
        return placement(p.kind,p.references,dict(p.options(),Distance=0))


class ConstructionAngleHandle(ViewHandles):
    """Readable screen-facing dial; the native datum rotates around its edge."""
    def __init__(self,panel):
        super().__init__(panel)
        self.angle=panel.widgets['Angle']
        self.frame_node=coin.SoTransform();self.scale=coin.SoScale()
        group=coin.SoAnnotation();self.root.addChild(group)
        light=coin.SoLightModel();light.model=coin.SoLightModel.BASE_COLOR;group.addChild(light)
        pick=coin.SoPickStyle();pick.style=coin.SoPickStyle.SHAPE_ON_TOP;group.addChild(pick)
        group.addChild(self.frame_node);group.addChild(self.scale)
        guide=coin.SoSeparator();group.addChild(guide)
        no_pick=coin.SoPickStyle();no_pick.style=coin.SoPickStyle.UNPICKABLE;guide.addChild(no_pick)
        lines(guide,[(TAPER_RADIUS*math.cos(math.radians(a)),TAPER_RADIUS*math.sin(math.radians(a)),0)
                     for a in range(0,361,3)],(.49,.60,.68))
        for a in range(0,360,30):
            rad=math.radians(a)
            lines(guide,[(r*math.cos(rad),r*math.sin(rad),0) for r in (TAPER_RADIUS-4,TAPER_RADIUS+4)],(.65,.76,.83))
        self.dragger=coin.SoRotateDiscDragger()
        self.dragger.setPart('rotator',taper_knob())
        self.dragger.setPart('rotatorActive',taper_knob(True))
        self.dragger.setPart('feedback',coin.SoSeparator())
        self.dragger.setPart('feedbackActive',coin.SoSeparator())
        group.addChild(self.dragger)
        self.register(self.dragger,self.moved,0,True)
        self.attach()

    def input_options(self,all_fields=False):
        return [(0,True,'Angle',self.angle)]

    def input_anchor(self,side):
        point=self.dragger.rotation.getValue().multVec(coin.SbVec3f(TAPER_RADIUS,0,0))*self.scale.scaleFactor.getValue()[0]
        return self.frame_node.translation.getValue()+self.frame_node.rotation.getValue().multVec(point)

    def camera_changed(self,*_,force=False):
        if self.closed or (self.dragging and not force):return
        cam=self.camera
        if hasattr(cam,'height'):height=cam.height.getValue()
        else:
            depth=-cam.orientation.getValue().inverse().multVec(self.frame_node.translation.getValue()-cam.position.getValue())[2]
            height=2*max(1e-6,depth)*math.tan(cam.heightAngle.getValue()/2)
        unit=height/max(1,min(self.view.getSize()))
        self.scale.scaleFactor=(unit,unit,unit)
        # Keep the dial usable when looking along or across the selected edge.
        self.frame_node.rotation=cam.orientation.getValue()
        self.editor.place()

    def moved(self,*_):
        if self.closed or self.syncing:return
        vector=self.dragger.rotation.getValue().multVec(coin.SbVec3f(1,0,0))
        raw=math.degrees(math.atan2(vector[1],vector[0]))
        current=self.angle.value()
        value=current+(raw-current+180)%360-180
        self.angle.setValue(round(value,self.angle.decimals()))
        # Preserve signed turns across the +/-180 degree branch and clamp at
        # the same bounds as numeric input, without accumulating hidden motion.
        self.syncing=True
        try:self.dragger.rotation.setValue(coin.SbVec3f(0,0,1),math.radians(self.angle.value()))
        finally:self.syncing=False
        self.editor.place();self.panel.schedule()

    def sync(self):
        if self.closed or self.dragging:return
        self.syncing=True
        try:
            if not self.panel.result:
                self.root.whichChild=coin.SO_SWITCH_NONE;return
            from fusionflow_construct import geometry
            edge=geometry(self.panel.references)[0]
            self.frame_node.translation=tuple(edge.CenterOfMass)
            self.dragger.rotation.setValue(coin.SbVec3f(0,0,1),math.radians(self.angle.value()))
            self.root.whichChild=0
            self.camera_changed()
        except (ValueError,RuntimeError):self.root.whichChild=coin.SO_SWITCH_NONE
        finally:
            self.syncing=False
            self.editor.refresh()
