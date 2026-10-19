"""Associative construction geometry, using native attachment where available."""
import math
import FreeCAD as A
import Part
from fusionflow_core import global_shape

LABELS={
 'UCS':'User Coordinate System (UCS)', 'OffsetPlane':'Offset Plane', 'AnglePlane':'Plane at Angle',
 'TangentPlane':'Tangent Plane','Midplane':'Midplane','PerpendicularPlane':'Perpendicular Plane',
 'TwoEdgesPlane':'Plane Through Two Edges','ThreePointsPlane':'Plane Through Three Points','PathPlane':'Plane Along Path',
 'CylinderAxis':'Axis Through Cylinder/Cone/Torus','NormalAxis':'Axis Perpendicular to Face',
 'TwoPlanesAxis':'Axis Through Two Planes','TwoPointsAxis':'Axis Through Two Points','EdgeAxis':'Axis Through Edge',
 'VertexPoint':'Point At Vertex','TwoEdgesPoint':'Point Through Two Edges','ThreePlanesPoint':'Point Through Three Planes',
 'CenterPoint':'Point At Center Of Circle/Sphere/Torus','EdgePlanePoint':'Point At Edge And Plane','PathPoint':'Point Along Path'}
NATIVE={'OffsetPlane':('Plane','FlatFace'),'AnglePlane':('Plane','NormalToEdge'),
        'TwoEdgesPlane':('Plane','ThreePointsPlane'),'ThreePointsPlane':('Plane','ThreePointsPlane'),
        'TwoPlanesAxis':('Line','IntersectionLine'),'TwoPointsAxis':('Line','TwoPointLine'),
        'EdgeAxis':('Line','Tangent'),'VertexPoint':('Point','Vertex'),'UCS':('CoordinateSystem','FlatFace')}
DEFAULTS=dict(BasePlane='XY',OffsetMode='Distance',Distance=0,Angle=0,Fraction=.5,PathMode='Proportional',Direction='U',
              Size=60,SizeMode='Automatic',Reverse=False,X=0,Y=0,Z=0)
# Required count and ordered reference roles, shared by validation and picking.
REFERENCES={
 'UCS':(0,('Plane',)), 'OffsetPlane':(0,('Plane',)), 'AnglePlane':(1,('Edge / axis',)),
 'TangentPlane':(1,('Face','Point / plane (optional)')),
 'Midplane':(2,('Plane 1','Plane 2')),
 'PerpendicularPlane':(1,('Face / plane','Point / plane (optional)')),
 'TwoEdgesPlane':(2,('Edge 1','Edge 2')), 'ThreePointsPlane':(3,('Point 1','Point 2','Point 3')),
 'PathPlane':(1,('Path','Reference point (To object)')),
 'CylinderAxis':(1,('Face',)), 'NormalAxis':(1,('Face','Point / plane (optional)')),
 'TwoPlanesAxis':(2,('Plane 1','Plane 2')), 'TwoPointsAxis':(2,('Point 1','Point 2')),
 'EdgeAxis':(1,('Edge / axis',)), 'VertexPoint':(1,('Point',)),
 'TwoEdgesPoint':(2,('Edge 1','Edge 2')), 'ThreePlanesPoint':(3,('Plane 1','Plane 2','Plane 3')),
 'CenterPoint':(1,('Circle / face',)), 'EdgePlanePoint':(2,('Edge','Plane')),
 'PathPoint':(1,('Path','Reference point (To object)'))}
_frame_observer=None


def reference_roles(kind,options):
    if kind=='OffsetPlane' and options.get('OffsetMode')=='To object':return 2,('Plane','Point')
    required,roles=REFERENCES[kind]
    if kind in ('PathPlane','PathPoint') and options.get('PathMode')=='To object':required=2
    return required,roles


def offset_expression(references):
    """Native attachment keeps its axes; only its signed normal offset changes.

    Sub-element expression syntax participates in FreeCAD's topology tracking.
    These coordinates share a parent (cross-container planes use Construction).
    """
    (source,sub),(target,vertex)=[(o,s) for o,subs in references for s in subs or ['']]
    target_shape=target.Name+('.<<%s>>'%vertex if vertex else '')+'._shape'
    if source.TypeId in ('PartDesign::Plane','App::Plane') and not sub:
        origin=source.Name+'.Placement.Base'
        # Explicit components avoid FreeCAD re-associating vector/rotation
        # multiplication when it serializes an expression on save/reopen.
        normal='vector(%s; %s; %s)'%tuple(source.Name+'._matrix.A%d3'%i for i in (1,2,3))
    else:
        face=source.Name+('.<<%s>>'%sub if sub else '')+'._shape'
        origin=face+'.CenterOfMass'
        normal='('+face+'.Surface.Axis * ('+face+'.Orientation == <<Reversed>> ? -1 : 1))'
    return '(%s.Point - %s) * %s * 1 mm + Distance'%(target_shape,origin,normal)


def reference_context(references):
    owners=[obj.getParentGeoFeatureGroup() for obj,_ in references]
    return (True,owners[0]) if owners and all(owner==owners[0] for owner in owners) else (not owners,None)


class FrameObserver:
    """Container Placement is not a geometric dependency of its children.

    Touch custom constructions when that frame changes; ordinary recompute
    then evaluates the existing feature DAG without introducing a Body cycle.
    """
    def slotChangedObject(self,obj,prop):
        if prop!='Placement':return
        for construction in obj.Document.Objects:
            if construction==obj or not isinstance(getattr(construction,'Proxy',None),Construction):continue
            for source,_ in construction.References:
                if source is None:continue
                parent=source.getParentGeoFeatureGroup()
                while parent:
                    if parent==obj:construction.touch();break
                    parent=parent.getParentGeoFeatureGroup()


def watch_frames():
    global _frame_observer
    if _frame_observer is None:
        _frame_observer=FrameObserver();A.addDocumentObserver(_frame_observer)


def geometry(references):
    result=[]
    for obj,subs in references:
        shape=global_shape(obj)
        for sub in subs or ['']:
            if sub:result.append(shape.getElement(sub));continue
            if obj.TypeId in ('PartDesign::Plane','App::Plane'):
                frame=obj.getGlobalPlacement()
                result.append(Part.makePlane(100,100,frame.Base,frame.Rotation.multVec(A.Vector(0,0,1))))
            elif shape.ShapeType in ('Face','Edge','Vertex'):result.append(shape)
            elif len(shape.Faces)==1:result.append(shape.Faces[0])
            elif len(shape.Edges)==1:result.append(shape.Edges[0])
            elif len(shape.Vertexes)==1:result.append(shape.Vertexes[0])
            else:raise ValueError('Vyber konkrétní stěnu, hranu nebo vrchol místo celého tělesa.')
    return result


def unit(vector):
    if vector.Length<1e-8:raise ValueError('Reference neurčují jednoznačný směr. Zkontroluj shodné body nebo rovnoběžnost.')
    return vector/vector.Length


def point(shape):
    if shape.ShapeType!='Vertex':raise ValueError('Tato reference musí být vrchol nebo konstrukční bod.')
    return shape.Point


def plane(shape):
    if shape.ShapeType!='Face' or not isinstance(shape.Surface,Part.Plane):raise ValueError('Tato reference musí být rovinná stěna nebo konstrukční rovina.')
    return shape.CenterOfMass,shape.normalAt(0,0)


def line(shape):
    if shape.ShapeType!='Edge' or not isinstance(shape.Curve,(Part.Line,Part.LineSegment)):raise ValueError('Vyber přímou hranu nebo konstrukční osu.')
    return shape.valueAt(shape.FirstParameter),unit(shape.tangentAt(shape.FirstParameter))


def frame(position,normal,x=None):
    rotation=A.Rotation(A.Vector(0,0,1),unit(normal)) if x is None else A.Rotation(unit(x),unit(normal).cross(unit(x)),unit(normal),'ZXY')
    return A.Placement(position,rotation)


def plane_intersection(a,b):
    p,n=plane(a);q,m=plane(b);direction=n.cross(m);den=direction.dot(direction)
    if den<1e-12:raise ValueError('Rovnoběžné roviny nemají jedinou průsečnici.')
    origin=(m.cross(direction)*n.dot(p)+direction.cross(n)*m.dot(q))/den
    return origin,unit(direction)


def along(edge,settings,reference=None):
    if edge.ShapeType!='Edge' or edge.Length<1e-9:raise ValueError('Vyber jednu nenulovou hranu cesty.')
    distance=settings['Fraction']*edge.Length if settings['PathMode']=='Proportional' else settings['Distance']
    if settings['PathMode']=='To object':
        if reference is None:raise ValueError('To object vyžaduje druhou referenci: bod.')
        target=point(reference);_,pairs,_=edge.distToShape(Part.Vertex(target))
        parameter=edge.Curve.parameter(pairs[0][0])
        distance=(Part.Edge(edge.Curve,edge.FirstParameter,parameter).Length if parameter>edge.FirstParameter+1e-10 else 0)+settings['Distance']
    if settings['Reverse']:distance=edge.Length-distance
    bounded=max(0,min(edge.Length,distance))
    parameter=edge.getParameterByLength(bounded)
    tangent=unit(edge.tangentAt(parameter));position=edge.valueAt(parameter)+tangent*(distance-bounded)
    return position,tangent


def placement(kind,references,options):
    s=dict(DEFAULTS,**options);g=geometry(references)
    if kind=='OffsetPlane' and s['OffsetMode'] not in ('Distance','To object'):raise ValueError('Neznámý režim odsazené roviny.')
    required,roles=reference_roles(kind,s)
    if len(g)<required:raise ValueError('Vyber %d referencí pro %s.'%(required,LABELS[kind]))
    if len(g)>len(roles):
        raise ValueError('Příliš mnoho referencí pro '+LABELS[kind]+'.')
    if kind in ('OffsetPlane','UCS'):
        p,n=plane(g[0]) if g else (A.Vector(),{'XY':A.Vector(0,0,1),'XZ':A.Vector(0,-1,0),'YZ':A.Vector(1,0,0)}[s['BasePlane']])
        if kind=='OffsetPlane' and s['OffsetMode']=='To object':p+=n*n.dot(point(g[1])-p)
        f=frame(p+n*s['Distance'],n)
        if kind=='UCS':f.Base+=f.Rotation.multVec(A.Vector(s['X'],s['Y'],s['Z']));f.Rotation=f.Rotation*A.Rotation(A.Vector(0,0,1),s['Angle'])
        return f
    if kind=='AnglePlane':
        p,axis=line(g[0]);base=A.Rotation(A.Vector(0,0,1),axis)
        return A.Placement(p,base*A.Rotation(A.Vector(0,0,1),s['Angle'])*A.Rotation(A.Vector(1,0,0),90))
    if kind=='Midplane':
        p,n=plane(g[0]);q,m=plane(g[1])
        if n.dot(m)<0:m=-m
        if s['Reverse']:m=-m
        normal=unit(n+m);d=n.dot(p)+m.dot(q);center=(p+q)*.5
        center+=normal*(d/(n+m).Length-normal.dot(center))
        return frame(center,normal)
    if kind in ('TangentPlane','PerpendicularPlane','NormalAxis'):
        face=g[0]
        if face.ShapeType!='Face':raise ValueError('První reference musí být stěna.')
        surface=face.Surface;u0,u1,v0,v1=face.ParameterRange
        if len(g)>1:
            anchor=point(g[1]) if g[1].ShapeType=='Vertex' else plane(g[1])[0]
            u,v=surface.parameter(anchor)
        else:u,v=(u0+u1)*.5,(v0+v1)*.5
        if kind=='TangentPlane':
            if not isinstance(surface,(Part.Cylinder,Part.Cone)):raise ValueError('Tangent Plane vyžaduje válcovou nebo kuželovou stěnu.')
            if len(g)==1:u=u0+math.radians(s['Angle'])
        position=face.valueAt(u,v);normal=face.normalAt(u,v)
        if kind=='PerpendicularPlane' and isinstance(surface,Part.Plane):
            normal=unit(surface.tangent(u,v)[0 if s['Direction']=='U' else 1])
        return frame(position+normal*s['Distance'],normal)
    if kind=='ThreePointsPlane':
        a,b,c=[point(x) for x in g];return frame((a+b+c)/3,(b-a).cross(c-a),b-a)
    if kind=='TwoEdgesPlane':
        a,u=line(g[0]);b,v=line(g[1]);normal=u.cross(v)
        if normal.Length<1e-8:normal=u.cross(b-a)
        normal=unit(normal)
        if abs((b-a).dot(normal))>1e-6:raise ValueError('Mimoběžné hrany neleží ve společné rovině.')
        return frame((a+b)*.5,normal,u)
    if kind in ('PathPlane','PathPoint'):return frame(*along(g[0],s,g[1] if len(g)>1 else None))
    if kind=='CylinderAxis':
        surface=g[0].Surface if g[0].ShapeType=='Face' else None
        if not isinstance(surface,(Part.Cylinder,Part.Cone,Part.Toroid)):raise ValueError('Vyber válcovou, kuželovou nebo toroidální stěnu.')
        return frame(surface.Center,surface.Axis)
    if kind=='TwoPlanesAxis':return frame(*plane_intersection(*g))
    if kind=='TwoPointsAxis':return frame(point(g[0]),point(g[1])-point(g[0]))
    if kind=='EdgeAxis':return frame(*line(g[0]))
    if kind=='VertexPoint':return frame(point(g[0]),A.Vector(0,0,1))
    if kind=='ThreePlanesPoint':
        origin,direction=plane_intersection(g[0],g[1]);p,n=plane(g[2]);den=n.dot(direction)
        if abs(den)<1e-10:raise ValueError('Tři roviny nemají jediný společný bod.')
        return frame(origin+direction*n.dot(p-origin)/den,A.Vector(0,0,1))
    if kind=='TwoEdgesPoint':
        a,u=line(g[0]);b,v=line(g[1]);cross=u.cross(v);den=cross.dot(cross)
        if den<1e-12:raise ValueError('Rovnoběžné hrany nemají jediný průsečík.')
        p=a+u*((b-a).cross(v).dot(cross)/den)
        if (p-b).cross(v).Length>1e-6:raise ValueError('Mimoběžné hrany nemají průsečík.')
        return frame(p,A.Vector(0,0,1))
    if kind=='EdgePlanePoint':
        edge,face=g
        p,n=plane(face)
        if edge.ShapeType!='Edge':raise ValueError('První reference musí být hrana.')
        points,curves=edge.Curve.intersectCS(Part.Plane(p,n))
        if len(points)!=1 or curves:raise ValueError('Hrana a rovina musí mít právě jeden průsečík (včetně prodloužení).')
        return frame(A.Vector(points[0].X,points[0].Y,points[0].Z),n)
    if kind=='CenterPoint':
        surface=g[0].Curve if g[0].ShapeType=='Edge' else g[0].Surface if g[0].ShapeType=='Face' else None
        if not isinstance(surface,(Part.Circle,Part.Sphere,Part.Toroid)):raise ValueError('Vyber kružnici, kulovou nebo toroidální stěnu.')
        return frame(surface.Center,A.Vector(0,0,1))
    raise ValueError('Neznámá konstrukce '+kind)


def plane_size(references,location,fallback):
    """Fit reference geometry while keeping the sketch support origin fixed."""
    bounds=A.BoundBox()
    for shape in geometry(references):
        local=shape.copy();local.transformShape(location.inverse().toMatrix())
        bounds.add(local.BoundBox)
    if not bounds.isValid():return fallback,fallback
    half_x=max(abs(bounds.XMin),abs(bounds.XMax));half_y=max(abs(bounds.YMin),abs(bounds.YMax))
    margin=max(2,math.sqrt(half_x*half_y)*.2)
    return max(10,2*(half_x+margin)),max(10,2*(half_y+margin))


class Construction:
    def __init__(self):watch_frames()
    def onDocumentRestored(self,obj):watch_frames()
    def execute(self,obj):
        options={name:getattr(obj,name,default).Value if hasattr(getattr(obj,name,default),'Value') else getattr(obj,name,default) for name,default in DEFAULTS.items()}
        location=placement(obj.ConstructionMode,obj.References,options)
        size=obj.Size.Value
        if obj.ConstructionMode.endswith('Plane') or obj.ConstructionMode=='Midplane':
            length,width=plane_size(obj.References,location,size) if getattr(obj,'SizeMode','Manual')=='Automatic' else (size,size)
            shape=Part.makePlane(length,width,A.Vector(-length/2,-width/2,0))
        elif 'Axis' in obj.ConstructionMode:shape=Part.makeLine(A.Vector(0,0,-size/2),A.Vector(0,0,size/2))
        else:shape=Part.Vertex(A.Vector())
        parent=obj.getParentGeoFeatureGroup()
        if parent:location=parent.getGlobalPlacement().inverse()*location
        obj.Shape=shape;obj.Placement=location
    def dumps(self):return None
    def loads(self,state):pass


class ConstructionView:
    def getIcon(self):
        import fusionflow_icons as icons
        obj=getattr(self,'Object',None)
        return icons.icon_path(icons.feature_name(obj) if obj else 'construct',True)
    def attach(self,view):self.Object=view.Object
    def updateData(self,obj,prop):pass
    def onChanged(self,view,prop):pass
    def doubleClicked(self,view):
        from fusionflow_construct_ui import open_construct
        open_construct(view.Object.ConstructionMode,view.Object);return True
    def dumps(self):return None
    def loads(self,state):pass


def create(doc,kind,references,options,obj=None):
    options=dict(options)
    options.setdefault('SizeMode',getattr(obj,'SizeMode','Manual') if obj else 'Automatic')
    options=dict(DEFAULTS,**options)
    if options['SizeMode'] not in ('Automatic','Manual'):raise ValueError('Velikost zobrazení musí být Automatic nebo Manual.')
    if not math.isfinite(options['Size']) or options['Size']<=0:raise ValueError('Velikost zobrazení musí být kladné konečné číslo.')
    # App::PropertyAngle clamps silently outside this range. Reject before
    # adding or editing geometry so the requested and stored angles agree.
    if kind in ('AnglePlane','TangentPlane','UCS') and not -360<=options['Angle']<=360:
        raise ValueError('Úhel musí být v rozsahu −360° až +360°.')
    location=placement(kind,references,options) # Validate before adding or editing.
    common,parent=reference_context(references)
    native=NATIVE.get(kind) if common else None
    if obj is not None:
        if obj.getParentGeoFeatureGroup()!=parent:
            raise ValueError('Změna rodičovského souřadnicového systému vyžaduje novou konstrukci; existující odkazy zůstanou zachované.')
        native=NATIVE.get(kind) if not isinstance(getattr(obj,'Proxy',None),Construction) else None
        if kind=='OffsetPlane' and native and not common:
            raise ValueError('Pro reference z různých souřadnicových systémů vytvoř novou rovinu; původní vazby zůstanou zachované.')
    if obj is None:
        type_id='PartDesign::'+native[0] if native else 'PartDesign::FeaturePython' if parent and parent.TypeId=='PartDesign::Body' else 'Part::FeaturePython'
        obj=doc.addObject(type_id,kind)
        if parent:
            old_tip=parent.Tip if parent.TypeId=='PartDesign::Body' else None
            old_visibility=old_tip.ViewObject.Visibility if old_tip and A.GuiUp else None
            parent.addObject(obj)
            if parent.TypeId=='PartDesign::Body':parent.Tip=old_tip
            if old_visibility is not None:old_tip.ViewObject.Visibility=old_visibility
        obj.Label=LABELS[kind]
        obj.addProperty('App::PropertyString','ConstructionMode','Construction');obj.ConstructionMode=kind;obj.setEditorMode('ConstructionMode',1)
        obj.addProperty('App::PropertyLinkSubListGlobal','References','Construction')
        obj.setEditorMode('References',1)
        for name,value in DEFAULTS.items():
            prop='App::PropertyBool' if isinstance(value,bool) else 'App::PropertyString' if isinstance(value,str) else 'App::PropertyAngle' if name=='Angle' else 'App::PropertyFloat' if name=='Fraction' else 'App::PropertyLength' if name=='Size' else 'App::PropertyDistance'
            # Native datum planes already have a Size? Respect their properties.
            if name not in obj.PropertiesList:obj.addProperty(prop,name,'Construction')
        if not native:
            obj.Proxy=Construction()
            if A.GuiUp:obj.ViewObject.Proxy=ConstructionView()
        if A.GuiUp:
            for attr,value in [('ShapeColor',(.92,.69,.30)),('LineColor',(.97,.78,.40)),('PointColor',(.97,.78,.40)),('Transparency',70),('LineWidth',2),('PointSize',7)]:
                if hasattr(obj.ViewObject,attr):setattr(obj.ViewObject,attr,value)
    obj.References=references
    # Older constructions predate this option; add it only when editing them.
    if 'OffsetMode' not in obj.PropertiesList:obj.addProperty('App::PropertyString','OffsetMode','Construction')
    if 'SizeMode' not in obj.PropertiesList:obj.addProperty('App::PropertyString','SizeMode','Construction')
    obj.setEditorMode('SizeMode',1)
    if native and kind=='OffsetPlane':obj.setEditorMode('OffsetMode',1)
    for name,value in options.items():setattr(obj,name,value)
    if native:
        for expression,_ in obj.ExpressionEngine:
            if expression.startswith(('AttachmentOffset.','Placement.','Length','Width')):obj.setExpression(expression,None)
        obj.MapMode='Deactivated';obj.AttachmentSupport=[];obj.AttachmentOffset=A.Placement()
        obj.Placement=location
        if references:
            obj.AttachmentSupport=references;obj.MapMode=NATIVE[kind][1]
            if kind in ('OffsetPlane','UCS'):
                if kind=='OffsetPlane':obj.AttachmentSupport=[(references[0][0],[references[0][1][0] if references[0][1] else ''])]
                if not references[0][1] or not any(references[0][1]):obj.MapMode='ObjectXY'
                expression=offset_expression(references) if kind=='OffsetPlane' and options['OffsetMode']=='To object' else 'Distance' if kind=='OffsetPlane' else 'Distance + Z'
                obj.setExpression('AttachmentOffset.Base.z',expression)
                if kind=='UCS':
                    obj.setExpression('AttachmentOffset.Base.x','X');obj.setExpression('AttachmentOffset.Base.y','Y')
                    obj.setExpression('AttachmentOffset.Rotation','rotation(Angle; 0; 0)')
            elif kind=='AnglePlane':obj.setExpression('AttachmentOffset.Rotation','rotation(Angle; 0; 0) * rotation(0; 0; 90)')
        elif kind in ('OffsetPlane','UCS'):
            base=placement('OffsetPlane',[],dict(options,Distance=0))
            columns=[base.Rotation.multVec(A.Vector(*axis)) for axis in ((1,0,0),(0,1,0),(0,0,1))]
            for index,axis in enumerate('xyz'):
                expression='%g * Distance'%columns[2][index]
                if kind=='UCS':expression+=' + '+' + '.join('%g * %s'%(column[index],name) for column,name in zip(columns,'XYZ'))
                obj.setExpression('Placement.Base.'+axis,expression)
            if kind=='UCS':
                angles=base.Rotation.toEuler()
                obj.setExpression('Placement.Rotation','rotation(%g; %g; %g) * rotation(Angle; 0; 0)'%angles)
        if hasattr(obj,'ResizeMode'):
            automatic=obj.TypeId=='PartDesign::Plane' and options['SizeMode']=='Automatic'
            obj.ResizeMode='Automatic' if automatic else 'Manual'
            if not automatic:
                for name in ('Length','Width'):
                    if hasattr(obj,name):obj.setExpression(name,'Size')
    doc.recompute()
    if 'Invalid' in obj.State:raise ValueError(obj.getStatusString())
    return obj
