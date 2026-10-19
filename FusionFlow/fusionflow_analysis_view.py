"""Transient Coin rendering for saved analysis objects; no model replacement."""
import json
import math
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore as C
from pivy import coin
from fusionflow_core import global_shape
from fusionflow_analysis import visible_shapes, plane_frame, section_caps, displayed_object

manager = None


def points_node(points, color, lines=True):
    root = coin.SoSeparator()
    style=coin.SoDrawStyle();style.linePattern=0xffff;style.lineWidth=1;root.addChild(style)
    material = coin.SoBaseColor(); material.rgb = color; root.addChild(material)
    coordinates = coin.SoCoordinate3(); coordinates.point.setValues(0,len(points),[tuple(p) for p in points]); root.addChild(coordinates)
    if lines:
        shape = coin.SoLineSet(); shape.numVertices.setValues(0,len(points)//2,[2]*(len(points)//2))
    else:
        style = coin.SoDrawStyle(); style.pointSize=7; root.addChild(style)
        shape = coin.SoPointSet()
    root.addChild(shape)
    return root


def mesh_node(shape, color, shift=App.Vector()):
    root = coin.SoSeparator()
    offset=coin.SoPolygonOffset();offset.factor=1;offset.units=2;root.addChild(offset)
    if shape.isNull():
        return root
    points, triangles = shape.tessellate(max(.01, shape.BoundBox.DiagonalLength/500))
    coordinates = coin.SoCoordinate3(); coordinates.point.setValues(0,len(points),[tuple(p+shift) for p in points]); root.addChild(coordinates)
    material=coin.SoMaterial(); material.diffuseColor=color; material.emissiveColor=tuple(c*.15 for c in color); root.addChild(material)
    hint=coin.SoShapeHints(); hint.vertexOrdering=coin.SoShapeHints.UNKNOWN_ORDERING; hint.shapeType=coin.SoShapeHints.UNKNOWN_SHAPE_TYPE; root.addChild(hint)
    indices=[i for triangle in triangles for i in (*triangle,-1)]
    faces=coin.SoIndexedFaceSet();faces.coordIndex.setValues(0,len(indices),indices);root.addChild(faces)
    return root


def surface_node(mesh, kind, settings):
    root=coin.SoSeparator()
    coordinates=coin.SoCoordinate3();coordinates.point.setValues(0,len(mesh['points']),[tuple(p) for p in mesh['points']]);root.addChild(coordinates)
    normals=coin.SoNormal();normals.vector.setValues(0,len(mesh['normals']),[tuple(n) for n in mesh['normals']]);root.addChild(normals)
    binding=coin.SoNormalBinding();binding.value=coin.SoNormalBinding.PER_VERTEX_INDEXED;root.addChild(binding)
    material=coin.SoMaterial();material.diffuseColor.setValues(0,len(mesh['colors']),mesh['colors']);root.addChild(material)
    binding=coin.SoMaterialBinding();binding.value=coin.SoMaterialBinding.PER_VERTEX_INDEXED;root.addChild(binding)
    if kind in ('Zebra','Environment'):
        vertex=coin.SoVertexShader();vertex.sourceType=coin.SoShaderObject.GLSL_PROGRAM
        vertex.sourceProgram='varying vec3 N; varying vec3 E; void main(){ vec4 p=gl_ModelViewMatrix*gl_Vertex; N=gl_NormalMatrix*gl_Normal; E=p.xyz; gl_ClipVertex=p; gl_Position=ftransform(); }'
        fragment=coin.SoFragmentShader();fragment.sourceType=coin.SoShaderObject.GLSL_PROGRAM
        angle=math.radians(settings.get('rotation',0));bands=settings.get('stripes',12)
        reflected='vec3 r=reflect(normalize(E),normalize(N)); float f=r.x*%.9f+r.y*%.9f;'%(math.cos(angle),math.sin(angle))
        body=('float v=smoothstep(-0.04,0.04,sin(f*%.6f)); gl_FragColor=vec4(vec3(0.08+v*0.85),1.0);'%(bands*math.pi)) if kind=='Zebra' else 'vec3 sky=mix(vec3(.12,.16,.24),vec3(.86,.91,.97),smoothstep(-.2,.85,r.y)); float light=pow(max(0.,cos(f*7.)),28.); gl_FragColor=vec4(sky+vec3(light*.55),1.);'
        fragment.sourceProgram='varying vec3 N; varying vec3 E; void main(){'+reflected+body+'}'
        program=coin.SoShaderProgram();program.shaderObject.setValues(0,2,[vertex,fragment]);root.addChild(program)
    indices=[i for tri in mesh['triangles'] for i in (*tri,-1)]
    shape=coin.SoIndexedFaceSet();shape.coordIndex.setValues(0,len(indices),indices);root.addChild(shape)
    return root


def analysis_node(kind,references,settings):
    from fusionflow_analysis_math import calculate
    result=calculate(kind,references,settings)
    root=coin.SoSeparator();pick=coin.SoPickStyle();pick.style=coin.SoPickStyle.UNPICKABLE;root.addChild(pick)
    for mesh in result['meshes']:root.addChild(surface_node(mesh,kind,settings))
    for shape in result['solids']:root.addChild(mesh_node(shape,(.97,.25,.13)))
    if result['lines']:
        offset=coin.SoPolygonOffset();offset.factor=-1;offset.units=-1;root.addChild(offset)
        root.addChild(points_node(result['lines'],(.97,.76,.28)))
    if result['markers']:root.addChild(points_node(result['markers'],(.98,.82,.3),False))
    return root,result


def section_node(objects, settings, references):
    frame=plane_frame(settings,references)
    normal=frame.Rotation.multVec(App.Vector(0,0,1))
    retained=normal*(1 if settings.get('flip') else -1)
    clip=coin.SoClipPlane();clip.plane=coin.SbPlane(coin.SbVec3f(*retained),coin.SbVec3f(*frame.Base))
    root=coin.SoSeparator();pick=coin.SoPickStyle();pick.style=coin.SoPickStyle.UNPICKABLE;root.addChild(pick)
    area=0; count=0
    if settings.get('caps',True):
        for index,obj in enumerate(objects):
            shape=global_shape(obj);caps=section_caps(shape,frame)
            if caps.isNull():continue
            count+=1;area+=caps.Area
            epsilon=max(1e-5,shape.BoundBox.DiagonalLength*1e-6)
            shift=retained*epsilon
            palette=((.80,.65,.42),(.50,.73,.83),(.72,.61,.81),(.57,.75,.59))
            root.addChild(mesh_node(caps,palette[index%len(palette)],shift*3))
            edges=[]
            for edge in caps.Edges:
                vertices=edge.discretize(Deflection=max(.03,shape.BoundBox.DiagonalLength/500))
                for a,b in zip(vertices,vertices[1:]):edges.extend((a+shift*2,b+shift*2))
            root.addChild(points_node(edges,(.16,.18,.21)))
            if settings.get('hatch',True):
                # Clip diagonal strokes against the actual cap face, preserving holes.
                local=caps.copy();local.Placement=frame.inverse()*caps.Placement
                bounds=local.BoundBox;step=max(.5,bounds.DiagonalLength/22);strokes=[]
                begin=math.floor((bounds.XMin-bounds.YMax)/step)
                end=math.ceil((bounds.XMax-bounds.YMin)/step)
                for n in range(begin,end+1):
                    a=App.Vector(n*step+bounds.YMin,bounds.YMin,0)
                    b=App.Vector(n*step+bounds.YMax,bounds.YMax,0)
                    if (b-a).Length<1e-7:continue
                    import Part
                    line=Part.makeLine(frame.multVec(a),frame.multVec(b))
                    for edge in line.common(caps).Edges:
                        strokes.extend((edge.Vertexes[0].Point+shift,edge.Vertexes[-1].Point+shift))
                root.addChild(points_node(strokes,(.24,.26,.28)))
    if not settings.get('caps',True):
        for obj in objects:
            cap=section_caps(global_shape(obj),frame)
            if not cap.isNull():count+=1;area+=cap.Area
    return clip,root,'Řez protíná %d těles · plocha %.3f mm²'%(count,area)


class AnalysisView:
    def __init__(self, view):
        view.Proxy=self

    def attach(self, view):
        self.Object=view.Object
        view.addDisplayMode(coin.SoSeparator(),'Analysis')

    def getDisplayModes(self, view):return ['Analysis']
    def getDefaultDisplayMode(self):return 'Analysis'
    def getIcon(self):
        import fusionflow_icons as icons
        return icons.icon_path(icons.ANALYSIS_ICONS.get(getattr(getattr(self,'Object',None),'AnalysisType',''),'inspect'),True)
    def onChanged(self, view, prop):
        if prop=='Visibility' and view.Visibility and view.Object.AnalysisType=='Section':
            for obj in view.Object.Document.Objects:
                if obj!=view.Object and getattr(obj,'AnalysisType','')=='Section' and obj.ViewObject.Visibility:
                    obj.ViewObject.Visibility=False
        surface=('CurvatureMap','Draft','Accessibility','MinimumRadius','Zebra','Environment','ComponentColors','MeshGroups')
        if prop=='Visibility' and view.Visibility and view.Object.AnalysisType in surface:
            for obj in view.Object.Document.Objects:
                if obj!=view.Object and getattr(obj,'AnalysisType','') in surface and obj.ViewObject.Visibility:
                    obj.ViewObject.Visibility=False
        if manager:manager.dirty=True
    def updateData(self, obj, prop):
        if manager:manager.dirty=True
    def doubleClicked(self, view):
        from fusionflow_analysis_ui import open_analysis
        open_analysis(view.Object.AnalysisType,view.Object)
        return True
    def onDelete(self, view, subelements):
        if manager:manager.dirty=True
        return True
    def dumps(self):return None
    def loads(self, state):pass


class Manager:
    def __init__(self):
        self.nodes=[];self.wrappers=[];self.hidden=[];self.signature=None;self.dirty=True
        self.timer=C.QTimer(Gui.getMainWindow());self.timer.timeout.connect(self.update);self.timer.start(350)
        App.addDocumentObserver(self)

    def clear(self):
        for scene,node in self.nodes:
            try:
                if scene.findChild(node)>=0:scene.removeChild(node)
            except RuntimeError:pass
        self.nodes=[]
        for scene,wrapper,original in self.wrappers:
            try:
                if scene.findChild(wrapper)>=0:scene.replaceChild(wrapper,original)
            except RuntimeError:pass
        self.wrappers=[]
        for obj,node,material in self.hidden:
            try:
                if node.findChild(material)>=0:node.removeChild(material)
            except (RuntimeError,ReferenceError):pass
        self.hidden=[]
        self.signature=None

    def slotDeletedDocument(self, doc):
        self.clear();self.signature=None;self.dirty=True

    def slotChangedObject(self,obj,prop):
        if prop in ('Shape','Mesh','Placement'):self.dirty=True

    def update(self):
        doc=App.ActiveDocument
        active=Gui.activeDocument()
        analyses=[o for o in doc.Objects if getattr(o,'AnalysisType','') and o.ViewObject.Visibility] if doc else []
        view=active.activeView() if active else None
        if not view or not hasattr(view,'getSceneGraph') or not analyses:
            if self.nodes or self.wrappers or self.hidden:self.clear()
            self.signature=None
            return
        objects=visible_shapes(doc,displayed=True)
        references={}
        for analysis in analyses:
            refs=[]
            for source,subs in analysis.References:
                shown=displayed_object(source)
                if shown is None:continue
                # A stored Face index belongs to the final Body topology. Never
                # reinterpret it on an earlier feature during history preview.
                if source.TypeId=='PartDesign::Body' and any(subs) and shown!=source.Tip:continue
                refs.append((shown,subs))
            references[analysis.Name]=refs
        signature=(doc.Name,view,
                   tuple((o.Name,o.Shape.hashCode(),str(o.getGlobalPlacement())) for o in objects),
                   tuple((o.Name,o.Settings,str(o.References),str(references[o.Name])) for o in analyses))
        if signature==self.signature and not self.dirty:return
        self.clear();self.signature=signature;self.dirty=False
        scene=view.getSceneGraph()
        render_scene=scene
        for obj in sorted(analyses,key=lambda o:o.AnalysisType!='Section'):
            try:
                settings=json.loads(obj.Settings)
                if obj.AnalysisType=='Section':
                    clip,root,result=section_node(objects,settings,obj.References)
                    # FreeCAD's ObjectGroup contains the physical model. Scope
                    # clipping to it; the grid, cube and edit handles stay intact.
                    group=next((scene.getChild(i) for i in range(scene.getNumChildren())
                                if str(scene.getChild(i).getName())=='ObjectGroup'),None)
                    if group is None:raise ValueError('V tomto pohledu chybí skupina 3D modelu.')
                    wrapper=coin.SoSeparator();wrapper.addChild(clip);wrapper.addChild(group)
                    scene.replaceChild(group,wrapper);self.wrappers.append((scene,wrapper,group))
                    render_scene=wrapper
                    self.nodes.append((wrapper,clip))
                    wrapper.addChild(root);self.nodes.append((wrapper,root))
                    if obj.Result!=result:obj.Result=result
                else:
                    refs=references[obj.Name]
                    if not refs:
                        message='Analýza čeká na viditelnou referenční geometrii.'
                        if obj.Result!=message:obj.Result=message
                        continue
                    root,result=analysis_node(obj.AnalysisType,refs,settings)
                    render_scene.addChild(root);self.nodes.append((render_scene,root))
                    for source in result['mask']:
                        node=source.ViewObject.RootNode
                        if not any(old==node for _,old,_ in self.hidden):
                            # Hide only native paint. Keeping native geometry in
                            # the graph preserves its Face/Edge picking details.
                            material=coin.SoMaterial();material.transparency=1
                            material.setOverride(True);node.insertChild(material,0)
                            self.hidden.append((source,node,material))
                    if obj.Result!=result['text']:obj.Result=result['text']
            except Exception as error:
                message='Analýza: '+str(error)
                if obj.Result!=message:obj.Result=message
        self.dirty=False


def install():
    global manager
    if manager is None:manager=Manager()
