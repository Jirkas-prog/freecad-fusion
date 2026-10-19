"""OCC inspection calculations and explicitly sampled surface visualizations."""
import math
import FreeCAD as A
import Part
from fusionflow_core import global_shape

PALETTE=((.42,.69,.88),(.91,.64,.36),(.56,.76,.49),(.76,.55,.82),(.88,.48,.53),(.39,.77,.74))
DEFAULTS=dict(direction=[0,0,1],quality=12,count=12,scale=100,limit=3,
              curvature='Gaussian',iso='UV',density=0,stripes=12,rotation=0)


def references_shapes(references):
    result=[]
    for obj,subs in references:
        if not hasattr(obj,'Shape') or obj.Shape.isNull():continue
        shape=global_shape(obj)
        selected=[shape.getElement(s) for s in subs if s]
        result.append((obj,selected[0] if len(selected)==1 else Part.makeCompound(selected) if selected else shape))
    if not result:raise ValueError('Vyber těleso nebo geometrii k analýze.')
    return result


def heat(value):
    value=max(0,min(1,value));stops=((.20,.35,.85),(.22,.73,.81),(.36,.77,.42),(.96,.80,.24),(.92,.23,.21))
    index=min(3,int(value*4));weight=value*4-index
    return tuple(stops[index][i]*(1-weight)+stops[index+1][i]*weight for i in range(3))


def edge_lines(edge):
    points=edge.discretize(Deflection=max(.01,edge.Length/300))
    return [p for a,b in zip(points,points[1:]) for p in (a,b)]


def comb_lines(edge,count,scale):
    if edge.Length<1e-8:return []
    lines=[];tips=[]
    for i in range(count+1):
        t=edge.FirstParameter+(edge.LastParameter-edge.FirstParameter)*i/count
        p=edge.valueAt(t);k=edge.curvatureAt(t)
        tip=p if abs(k)<1e-10 else p+edge.normalAt(t)*k*scale
        lines.extend((p,tip));tips.append(tip)
    lines.extend(p for a,b in zip(tips,tips[1:]) for p in (a,b))
    return lines


def sampled_face(face,spacing):
    vertices,triangles=face.tessellate(max(.002,spacing/8))
    stack=[tuple(vertices[i] for i in tri) for tri in triangles]
    count=0;cache={}
    while stack:
        a,b,c=stack.pop()
        if max((a-b).Length,(a-c).Length,(b-c).Length)>spacing:
            ab,bc,ca=(a+b)*.5,(b+c)*.5,(c+a)*.5
            stack.extend(((a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca)))
        else:
            count+=1
            if count>20000:raise ValueError('Příliš hustá analýza. Sniž Quality nebo počet vybraných těles.')
            # Project subdivided chord vertices back onto the exact surface.
            points=[];normals=[];curvatures=[]
            for p in (a,b,c):
                key=tuple(round(v,9) for v in p)
                if key not in cache:
                    u,v=face.Surface.parameter(p)
                    sign=-1 if face.Orientation=='Reversed' else 1
                    try:curvature=tuple(sign*k for k in face.curvatureAt(u,v))
                    except Part.OCCError:
                        curvature=(-sign/face.Surface.Radius,)*2 if isinstance(face.Surface,Part.Sphere) else (float('nan'),)*2
                    try:normal=face.normalAt(u,v)
                    except Part.OCCError:
                        u0,u1,v0,v1=face.ParameterRange
                        normal=face.normalAt(min(u1-1e-7,max(u0+1e-7,u)),min(v1-1e-7,max(v0+1e-7,v)))
                    cache[key]=(face.valueAt(u,v),normal,curvature)
                point,normal,curvature=cache[key]
                curvatures.append(curvature)
                points.append(point);normals.append(normal)
            yield points,normals,curvatures


def measure_value(value, unit, settings):
    """Format only the display; calculations always retain OCC precision."""
    precision=settings.get('precision')
    def number(v):
        if precision is None:return '%.9g'%v
        digits=max(0,min(9,int(precision)))
        return ('%.*f'%(digits,0 if abs(v)<.5*10**-digits else v))
    text=number(value)+(' '+unit if unit else '')
    secondary=settings.get('secondary','None')
    factors={'cm':10.,'m':1000.,'in':25.4,'ft':304.8}
    if unit in ('mm','mm²','mm³') and secondary in factors:
        power={'mm':1,'mm²':2,'mm³':3}[unit]
        text+=' (%s %s%s)'%(number(value/factors[secondary]**power),secondary,unit[2:])
    return text


def measure(shapes,settings):
    if len(shapes)>12:raise ValueError('Pro přehledné měření vyber nejvýše 12 referencí.')
    result=dict(meshes=[],lines=[],markers=[],solids=[],mask=[],groups=[],text='')
    selections=[];centres=[]
    numbers=settings.get('selection_numbers',list(range(1,len(shapes)+1)))
    if len(numbers)!=len(shapes):numbers=list(range(1,len(shapes)+1))
    def coordinates(rows,p,prefix):
        rows.extend((prefix+' '+axis,value,'mm') for axis,value in zip('XYZ',p))
    for index,(obj,shape) in enumerate(shapes):
        rows=[];centre=None;radius=None
        if shape.Solids:rows.append(('Volume',shape.Volume,'mm³'))
        if shape.Faces:rows.append(('Area',shape.Area,'mm²'))
        if shape.Edges:rows.append(('Loop length' if shape.ShapeType=='Face' else 'Length' if shape.ShapeType=='Edge' else 'Total edge length',shape.Length,'mm'))
        if shape.ShapeType=='Vertex':coordinates(rows,shape.Point,'Position')
        if len(shape.Edges)==1 and isinstance(shape.Edges[0].Curve,Part.Circle):
            curve=shape.Edges[0].Curve;radius=curve.Radius;centre=curve.Center
        elif shape.ShapeType=='Face' and isinstance(shape.Surface,(Part.Cylinder,Part.Sphere)):
            radius=shape.Surface.Radius
            if isinstance(shape.Surface,Part.Sphere):centre=shape.Surface.Center
        if radius is not None:rows.extend((('Radius',radius,'mm'),('Diameter',radius*2,'mm')))
        if centre is not None:coordinates(rows,centre,'Center')
        centres.append(centre)
        selections.append(('Selection %d · %s · %s'%(numbers[index],obj.Label,shape.ShapeType),rows))
    for i,(first,a) in enumerate(shapes):
        for j,(second,b) in enumerate(shapes[i+1:],i+1):
            distance,pairs,_=a.distToShape(b);p,q=pairs[0];delta=q-p
            rows=[('Minimum distance',distance,'mm')]
            result['markers'].extend((p,q))
            if distance>1e-8:result['lines'].extend((p,q))
            if centres[i] is not None and centres[j] is not None:
                rows.append(('Center distance',(centres[j]-centres[i]).Length,'mm'))
            frame=settings.get('delta','Global')
            if frame!='None':
                if frame in ('Selection 1','Selection 2'):
                    source=first if frame=='Selection 1' else second
                    owner=source.getParentGeoFeatureGroup() or source
                    delta=owner.getGlobalPlacement().Rotation.inverted().multVec(delta)
                coordinates(rows,delta,'Δ')
            def direction(shape):
                if shape.ShapeType=='Face' and isinstance(shape.Surface,Part.Plane):return shape.normalAt(0,0),'plane'
                if shape.ShapeType=='Edge' and isinstance(shape.Curve,(Part.Line,Part.LineSegment)):return shape.tangentAt(shape.FirstParameter),'line'
                return None,None
            u,ut=direction(a);v,vt=direction(b)
            if u is not None and v is not None:
                angle=math.degrees(u.getAngle(v));angle=min(angle,180-angle)
                rows.append(('Smaller angle',90-angle if ut!=vt else angle,'°'))
            title='Results' if len(shapes)==2 else 'Results %d ↔ %d'%(i+1,j+1)
            if frame!='None':title+=' · '+frame
            result['groups'].append((title,rows))
    result['groups'].extend(selections)
    result['text']='\n\n'.join(title+'\n'+'\n'.join(label+': '+measure_value(value,unit,settings) for label,value,unit in rows) for title,rows in result['groups'])
    return result


def calculate(kind,references,settings):
    settings=dict(DEFAULTS,**settings)
    if kind=='MeshGroups':return mesh_groups(references,settings)
    if kind=='Measure':references=[(obj,[sub]) for obj,subs in references for sub in subs or ['']]
    shapes=references_shapes(references)
    if kind=='Measure':return measure(shapes,settings)
    bounds=A.BoundBox()
    for _,shape in shapes:bounds.add(shape.BoundBox)
    diagonal=max(bounds.DiagonalLength,1e-5)
    result=dict(meshes=[],lines=[],markers=[],solids=[],mask=[],text='')
    if kind=='Interference':
        if len(shapes)<2 or any(not shape.Solids for _,shape in shapes):
            raise ValueError('Vyber alespoň dvě objemová tělesa.')
        reports=[]
        for i,(first,a) in enumerate(shapes):
            for second,b in shapes[i+1:]:
                if not a.BoundBox.intersect(b.BoundBox):continue
                common=a.common(b)
                if common.Volume>max(1e-7,min(a.Volume,b.Volume)*1e-10):
                    reports.append((common.Volume,first.Label,second.Label));result['solids'].append(common)
        reports.sort(reverse=True)
        result['text']='Průniky: %d\n'%len(reports)+'\n'.join('%s × %s: %.6g mm³'%(a,b,v) for v,a,b in reports)
        if not reports:result['text']+='Žádný objemový průnik. Pouhý dotyk není kolize.'
        return result
    if kind=='CenterOfMass':
        if any(not s.Solids for _,s in shapes):raise ValueError('Pro těžiště vyber objemová tělesa.')
        volume=sum(s.Volume for _,s in shapes)
        if volume<=0:raise ValueError('Vybraná tělesa nemají kladný objem.')
        center=sum((s.CenterOfMass*s.Volume for _,s in shapes),A.Vector())/volume
        result['markers']=[center]
        radius=diagonal/35
        for axis in (A.Vector(1,0,0),A.Vector(0,1,0),A.Vector(0,0,1)):
            result['lines'].extend((center-axis*radius,center+axis*radius))
        result['text']='Rovnoměrná stejná hustota všech těles.\nX %.6g · Y %.6g · Z %.6g mm\nObjem %.6g mm³'%(*center,volume)
        if settings['density']>0:result['text']+='\nHmotnost %.6g kg'%(volume*settings['density']/1e9)
        result['text']+='\nPřekrývající se tělesa se počítají samostatně.'
        return result
    if kind in ('CurvatureComb','Isocurve'):
        count=max(2,min(60,int(settings['count'])))
        for _,shape in shapes:
            if kind=='CurvatureComb':
                for edge in shape.Edges:result['lines'].extend(comb_lines(edge,count,settings['scale']))
            else:
                for face in shape.Faces:
                    u0,u1,v0,v1=face.ParameterRange
                    for direction in settings['iso']:
                        for i in range(1,count+1):
                            t=i/(count+1)
                            curve=face.Surface.uIso(u0+(u1-u0)*t) if direction=='U' else face.Surface.vIso(v0+(v1-v0)*t)
                            edge=curve.toShape(v0,v1) if direction=='U' else curve.toShape(u0,u1)
                            for trimmed in edge.common(face).Edges:result['lines'].extend(edge_lines(trimmed))
        result['text']=('Hřeben křivosti: %d vzorků na hranu · Scale %.6g mm²'%(count+1,settings['scale'])) if kind=='CurvatureComb' else 'Izokřivky %s · %d v každém směru, oříznuté na hranicích ploch.'%(settings['iso'],count)
        if not result['lines']:raise ValueError('Výběr neobsahuje analyzovatelnou hranu nebo plochu. Bodové degenerované hrany se vynechávají.')
        return result
    if kind not in ('CurvatureMap','Draft','Accessibility','MinimumRadius','Zebra','Environment','ComponentColors'):
        raise ValueError('Tato analýza zatím nemá výpočet.')
    direction=A.Vector(*settings['direction'])
    if direction.Length<1e-9:raise ValueError('Směr musí být nenulový vektor.')
    direction.normalize();minimum=float('inf');values=[];tested=0;unknown=0;access_cache={}
    obstruction=Part.makeCompound([s for _,s in shapes]) if kind=='Accessibility' else None
    spacing=diagonal/max(4,min(32,settings['quality']))
    for object_index,(obj,shape) in enumerate(shapes):
        points=[];normals=[];colors=[];triangles=[]
        for face in shape.Faces:
            for ps,ns,ks in sampled_face(face,spacing):
                start=len(points);triangles.append((start,start+1,start+2));points.extend(ps);normals.extend(ns)
                for p,n,k in zip(ps,ns,ks):
                    tested+=1
                    if tested>90000:raise ValueError('Příliš mnoho vzorků. Zvol nižší Quality nebo méně těles.')
                    if kind in ('CurvatureMap','MinimumRadius') and not all(math.isfinite(value) for value in k):
                        color=(.6,.6,.6);unknown+=1
                    elif kind=='CurvatureMap':
                        value=k[0]*k[1] if settings['curvature']=='Gaussian' else min(k) if settings['curvature']=='Minimum' else max(k)
                        values.append(value);color=heat(.5+value*settings['scale']*.5)
                    elif kind=='Draft':
                        value=math.degrees(math.asin(max(-1,min(1,n.dot(direction)))))
                        values.append(value);color=heat(.5+value/(2*max(.1,settings['limit'])))
                    elif kind=='MinimumRadius':
                        curvature=max(k)
                        radius=1/curvature if curvature>1e-8 else float('inf')
                        minimum=min(minimum,radius)
                        color=(.91,.24,.22) if radius<settings['limit'] else (.32,.72,.43) if math.isfinite(radius) else (.58,.63,.69)
                    elif kind=='Accessibility':
                        epsilon=max(1e-6,diagonal*1e-6)
                        key=tuple(round(v,8) for v in p)
                        accessible=False
                        if n.dot(direction)>1e-6:
                            if key not in access_cache:
                                ray=Part.makeLine(p+direction*epsilon,p+direction*diagonal*3)
                                access_cache[key]=ray.common(obstruction).Length<epsilon
                            accessible=access_cache[key]
                        color=(.32,.75,.43) if accessible else (.9,.25,.23)
                    else:color=PALETTE[object_index%len(PALETTE)]
                    colors.append(color)
        result['meshes'].append(dict(points=points,normals=normals,colors=colors,triangles=triangles))
        result['mask'].append(obj)
    result['text']='Vzorkovaná analýza · %d vrcholových vzorků.\nQuality mění hustotu, nikoli geometrii modelu.'%tested
    if unknown:result['text']+='\nNedefinovaná křivost v %d vzorcích (šedě).'%unknown
    if values:
        unit='°' if kind=='Draft' else 'mm⁻²' if settings['curvature']=='Gaussian' else 'mm⁻¹'
        result['text']+='\nRozsah %.6g až %.6g %s'%(min(values),max(values),unit)
    if kind=='MinimumRadius':
        result['text']+='\n'+('Nejmenší vzorkovaný konkávní poloměr %.6g mm.'%minimum if math.isfinite(minimum) else 'Ve vzorcích nejsou konkávní plochy.')
        result['text']+='\nČervená: menší než limit. Šedá: rovné/konvexní.'
    if kind=='Accessibility':result['text']+='\nZelená: přímý výhled po směru. Neověřuje vůli skutečného nástroje ani jiné nevybrané objekty.'
    if kind=='Draft':result['text']+='\nModrá: záporný úkos · zelená: nulový · červená: kladný.'
    if kind=='Environment':result['text']+='\nProcedurální reflexní prostředí; bez HDR fotografie.'
    return result


def mesh_groups(references,settings):
    result=dict(meshes=[],lines=[],markers=[],solids=[],mask=[],text='')
    total=0
    for obj,_ in references:
        if not hasattr(obj,'Mesh') or not obj.Mesh.CountFacets:continue
        mesh=obj.Mesh.copy()
        mesh.Placement=obj.getGlobalPlacement()
        groups=mesh.getPlanarSegments(max(.000001,settings['limit']))
        colors={index:PALETTE[group%len(PALETTE)] for group,indices in enumerate(groups) for index in indices}
        points=[];normals=[];paint=[];triangles=[]
        for index,facet in enumerate(mesh.Facets):
            start=len(points);triangles.append((start,start+1,start+2))
            points.extend(A.Vector(*p) for p in facet.Points)
            normals.extend([facet.Normal]*3);paint.extend([colors.get(index,(.6,.6,.6))]*3)
        result['meshes'].append(dict(points=points,normals=normals,colors=paint,triangles=triangles))
        result['mask'].append(obj);total+=len(groups)
    if not result['meshes']:raise ValueError('Vyber síťový objekt (Mesh), například importované STL.')
    result['text']='%d skupin koplanárních trojúhelníků · tolerance %.6g mm.\nNativní segmentace FreeCAD Mesh; geometrie ani uložené barvy se nemění.'%(total,settings['limit'])
    return result
