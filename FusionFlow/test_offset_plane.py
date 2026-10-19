"""To Object: native attachment, common coordinates, legacy edits and saved links."""
import os,sys,tempfile
import FreeCAD as A,Part
sys.path.insert(0,os.path.dirname(__file__))
from fusionflow_construct import create,placement
from fusionflow_core import global_shape

def run():
    d=A.newDocument('OffsetToObject')
    group=d.addObject('App::Part','Component')
    body=d.addObject('PartDesign::Body','Body');group.addObject(body)
    source=body.newObject('PartDesign::AdditiveBox','Box');source.Length=20;source.Width=30;source.Height=40
    target=body.newObject('PartDesign::Point','Target');target.Placement.Base=A.Vector(12,14,50)
    body.Tip=source
    body.Placement=A.Placement(A.Vector(10,20,30),A.Rotation(27,19,-31))
    group.Placement=A.Placement(A.Vector(-9,15,21),A.Rotation(-11,42,13));d.recompute()
    planes=[]
    def check(obj,face,offset):
        f=global_shape(source).getElement(face);n=f.normalAt(0,0)
        q=global_shape(target).Vertexes[0].Point;loc=obj.getGlobalPlacement()
        assert 'Invalid' not in obj.State,obj.getStatusString()
        assert (loc.Rotation.multVec(A.Vector(0,0,1))-n).Length<1e-7
        assert abs(n.dot(loc.Base-q)-offset)<1e-7,(loc.Base,q,n,offset)
    for i in range(1,7):
        face='Face%d'%i;plane=create(d,'OffsetPlane',[(source,[face])],{'Distance':3})
        # Simulate a saved pre-0.19.9 native datum with no new property.
        plane.removeProperty('OffsetMode');original_rotation=plane.Placement.Rotation
        create(d,'OffsetPlane',[(source,[face]),(target,['Vertex1'])],{'OffsetMode':'To object','Distance':-2},plane)
        check(plane,face,-2);assert plane.Placement.Rotation.isSame(original_rotation,1e-8)
        assert plane.TypeId=='PartDesign::Plane' and body.Tip==source
        assert '._shape' in plane.ExpressionEngine[0][1] or any('._shape' in expr for _,expr in plane.ExpressionEngine)
        planes.append(plane)
    target.Placement.Base=A.Vector(17,-8,61);source.Height=45;d.recompute()
    for i,plane in enumerate(planes,1):check(plane,'Face%d'%i,-2)
    # Lateral target motion must not translate or rotate an attached sketch.
    top=planes[-1];old=top.Placement
    sketch=body.newObject('Sketcher::SketchObject','Sketch');sketch.AttachmentSupport=[(top,[''])];sketch.MapMode='ObjectXY'
    d.recompute();old_sketch=sketch.Placement
    target.Placement.Base.x+=20;target.Placement.Base.y-=11;d.recompute()
    assert top.Placement.isSame(old,1e-8) and sketch.Placement.isSame(old_sketch,1e-8)
    target.Placement.Base.z+=9;d.recompute();assert abs(sketch.Placement.Base.z-old_sketch.Base.z-9)<1e-8
    # Whole datum planes and merged face/vertex references also remain associative.
    datum=create(d,'OffsetPlane',[(top,['']),(target,['Vertex1'])],{'OffsetMode':'To object','Distance':4})
    check(datum,'Face6',4)
    tilted=create(d,'OffsetPlane',[(planes[0],['']),(target,['Vertex1'])],{'OffsetMode':'To object','Distance':5})
    check(tilted,'Face1',5)
    merged=create(d,'OffsetPlane',[(source,['Face6','Vertex1'])],{'OffsetMode':'To object','Distance':2})
    q=source.Shape.Vertexes[0].Point;n=source.Shape.Face6.normalAt(0,0)
    assert abs(n.dot(merged.Placement.Base-q)-2)<1e-8
    target_sketch=body.newObject('Sketcher::SketchObject','TargetSketch')
    target_sketch.addGeometry(Part.Point(A.Vector(3,4,0)),False);target_sketch.Placement.Base.z=23;d.recompute()
    from_sketch=create(d,'OffsetPlane',[(source,['Face6']),(target_sketch,['Vertex1'])],{'OffsetMode':'To object','Distance':1})
    target_sketch.Placement.Base.z=42;d.recompute();assert abs(from_sketch.Placement.Base.z-43)<1e-8
    # Reject bad inputs before mutating the original feature or document.
    saved=top.Placement;names={o.Name for o in d.Objects};refs=list(top.References)
    for inputs in ([(source,['Face6'])],[(source,['Face6']),(source,['Edge1'])],[(source,['Face6']),(target,['Vertex1']),(target,['Vertex1'])]):
        try:create(d,'OffsetPlane',inputs,{'OffsetMode':'To object'},top)
        except ValueError:pass
        else:raise AssertionError('Invalid To Object reference accepted')
        assert top.Placement.isSame(saved,1e-8) and top.References==refs and {o.Name for o in d.Objects}==names
    # Across components, the existing custom plane path uses global coordinates.
    point=d.addObject('Part::Feature','ExternalPoint');point.Shape=Part.Vertex(A.Vector(70,80,90))
    cross=create(d,'OffsetPlane',[(source,['Face6']),(point,['Vertex1'])],{'OffsetMode':'To object','Distance':6})
    assert cross.TypeId=='Part::FeaturePython'
    group.Placement=A.Placement(A.Vector(8,2,11),A.Rotation(23,-19,7));d.recompute()
    check(top,'Face6',-2);check(datum,'Face6',4)
    f=global_shape(source).Face6;n=f.normalAt(0,0)
    assert abs(n.dot(cross.Placement.Base-point.Shape.Vertexes[0].Point)-6)<1e-7
    # Native edit cannot silently reinterpret coordinates from another container.
    try:create(d,'OffsetPlane',[(source,['Face6']),(point,['Vertex1'])],{'OffsetMode':'To object'},top)
    except ValueError:pass
    else:raise AssertionError('Cross-container native edit accepted')
    filename=os.path.join(tempfile.mkdtemp(prefix='fusionflow-offset-'),'to-object.FCStd')
    top_name=top.Name;datum_name=datum.Name;tilted_name=tilted.Name
    names=[p.Name for p in planes];d.saveAs(filename);A.closeDocument(d.Name)
    d=A.openDocument(filename);source=d.getObject('Box');target=d.getObject('Target')
    target.Placement.Base.z+=11;d.recompute()
    check(d.getObject(top_name),'Face6',-2);check(d.getObject(datum_name),'Face6',4)
    check(d.getObject(tilted_name),'Face1',5)
    for i,name in enumerate(names,1):check(d.getObject(name),'Face%d'%i,-2)
    assert not [o.Name for o in d.Objects if 'Invalid' in o.State]
    A.closeDocument(d.Name)
    print('PASS: six transformed faces, preserved axes/origin, target motion, datum/merged refs, validation, cross-component plane, save/reopen')

if __name__=='__main__':run()
