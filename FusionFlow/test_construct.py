import os,sys,math,tempfile
import FreeCAD as A,Part
sys.path.insert(0,os.path.dirname(__file__))
from fusionflow_construct import create,placement

def run():
    d=A.newDocument('ConstructMath')
    box=d.addObject('Part::Box','Box');box.Length=20;box.Width=30;box.Height=40;d.recompute()
    def shape(name,geometry):
        o=d.addObject('Part::Feature',name);o.Shape=geometry;return o
    points=[shape('Point',Part.Vertex(A.Vector(*p))) for p in [(0,0,0),(10,0,0),(0,10,0),(3,4,7)]]
    line=shape('Line',Part.makeLine(A.Vector(-10,0,0),A.Vector(10,0,0)))
    line2=shape('Line',Part.makeLine(A.Vector(0,-10,0),A.Vector(0,10,0)))
    circle=shape('Circle',Part.makeCircle(5))
    cylinder=shape('Cylinder',Part.makeCylinder(5,20))
    sphere=shape('Sphere',Part.makeSphere(6))
    yz=shape('YZ',Part.makePlane(20,20,A.Vector(),A.Vector(1,0,0)))
    xz=shape('XZ',Part.makePlane(20,20,A.Vector(),A.Vector(0,1,0)))
    xy=shape('XY',Part.makePlane(20,20))
    refs=lambda *objects:[(o,['']) for o in objects]
    cases={
      'UCS':([],{'X':2,'Y':3,'Z':4,'Angle':30}),
      'OffsetPlane':([(box,['Face6'])],{'Distance':5}),
      'AnglePlane':(refs(line),{'Angle':30}),
      'TangentPlane':([(cylinder,['Face1'])],{'Angle':90}),
      'Midplane':([(box,['Face5','Face6'])],{}),
      'PerpendicularPlane':(refs(xy,points[3]),{'Direction':'U','Distance':2}),
      'TwoEdgesPlane':(refs(line,line2),{}),
      'ThreePointsPlane':(refs(*points[:3]),{}),
      'PathPlane':(refs(circle),{'Fraction':.25}),
      'CylinderAxis':([(cylinder,['Face1'])],{}),
      'NormalAxis':([(sphere,['Face1']),(points[3],[''])],{}),
      'TwoPlanesAxis':(refs(yz,xz),{}),
      'TwoPointsAxis':(refs(*points[:2]),{}),
      'EdgeAxis':(refs(line),{}),
      'VertexPoint':(refs(points[3]),{}),
      'TwoEdgesPoint':(refs(line,line2),{}),
      'ThreePlanesPoint':(refs(xy,yz,xz),{}),
      'CenterPoint':(refs(circle),{}),
      'EdgePlanePoint':(refs(line,yz),{}),
      'PathPoint':(refs(circle),{'Fraction':.25})}
    built={kind:create(d,kind,r,s) for kind,(r,s) in cases.items()}
    # Native PropertyAngle silently clamps; reject unsupported input atomically.
    for kind in ('AnglePlane','TangentPlane','UCS'):
        for value in (-361,361,float('nan')):
            names={o.Name for o in d.Objects};old=built[kind].Angle.Value
            for existing in (None,built[kind]):
                try:create(d,kind,cases[kind][0],dict(cases[kind][1],Angle=value),existing)
                except ValueError:pass
                else:raise AssertionError('Out-of-range angle accepted: '+kind)
                assert {o.Name for o in d.Objects}==names and built[kind].Angle.Value==old
    assert all('Invalid' not in o.State and not o.Shape.isNull() for o in built.values())
    for kind,obj in built.items():
        if kind.endswith('Point'):
            assert len(obj.Shape.Vertexes)==1 and not obj.Shape.Edges and not obj.Shape.Faces,kind
    assert abs(built['OffsetPlane'].Placement.Base.z-45)<1e-7
    assert abs(built['Midplane'].Placement.Base.z-20)<1e-7
    assert (built['PathPoint'].Placement.Base-A.Vector(0,5,0)).Length<1e-7
    assert (built['VertexPoint'].Placement.Base-A.Vector(3,4,7)).Length<1e-7
    assert (built['UCS'].Placement.Base-A.Vector(2,3,4)).Length<1e-7
    assert abs(built['AnglePlane'].Placement.Rotation.multVec(A.Vector(0,0,1)).dot(A.Vector(1,0,0)))<1e-7
    # Native support and custom LinkSubList recompute from upstream changes.
    box.Height=60;d.recompute()
    assert abs(built['OffsetPlane'].Placement.Base.z-65)<1e-7
    assert abs(built['Midplane'].Placement.Base.z-30)<1e-7
    built['OffsetPlane'].Distance=8;d.recompute();assert abs(built['OffsetPlane'].Placement.Base.z-68)<1e-7
    world=create(d,'OffsetPlane',[],{'BasePlane':'YZ','Distance':7});world.Distance=9;d.recompute();assert abs(world.Placement.Base.x-9)<1e-7
    # Non-uniform B-spline path uses true OCC length, including extrapolation.
    curve=Part.BSplineCurve();curve.interpolate([A.Vector(0,0,0),A.Vector(2,3,0),A.Vector(30,10,5),A.Vector(31,20,10)])
    path=shape('Spline',curve.toShape());half=create(d,'PathPoint',refs(path),{'Fraction':.5})
    expected=path.Shape.valueAt(path.Shape.getParameterByLength(path.Shape.Length/2));assert (half.Placement.Base-expected).Length<1e-6
    end=create(d,'PathPoint',refs(path),{'PathMode':'Distance','Distance':path.Shape.Length+10})
    assert abs((end.Placement.Base-path.Shape.Vertexes[-1].Point).Length-10)<1e-6
    near=create(d,'PathPoint',refs(line,points[3]),{'PathMode':'To object'});assert (near.Placement.Base-A.Vector(3,0,0)).Length<1e-6
    body=d.addObject('PartDesign::Body','Body');source=body.newObject('PartDesign::AdditiveBox','BoxInBody')
    source.Length=source.Width=source.Height=10
    body.Placement=A.Placement(A.Vector(70,20,40),A.Rotation(A.Vector(0,1,0),90));d.recompute()
    native=create(d,'OffsetPlane',[(source,['Face6'])],{'Distance':5})
    custom=create(d,'Midplane',[(source,['Face5','Face6'])],{})
    assert abs(native.getGlobalPlacement().Base.x-85)<1e-7 and abs(custom.getGlobalPlacement().Base.x-75)<1e-7
    assert body.Tip==source and abs(body.Shape.Volume-1000)<1e-6
    cross=create(d,'Midplane',[(source,['Face1']),(yz,[''])],{})
    old_cross=cross.Placement.Base
    body.Placement.Base.x=100;d.recompute()
    assert abs(native.getGlobalPlacement().Base.x-115)<1e-7 and abs(custom.getGlobalPlacement().Base.x-105)<1e-7
    assert (cross.Placement.Base-old_cross).Length>1, 'Container placement did not update external construction'
    for kind,r in [('Midplane',refs(xy,xy)),('TwoEdgesPlane',refs(line,line)),('ThreePointsPlane',refs(points[0],points[1],points[1]))]:
        try:placement(kind,r,{'Reverse':True} if kind=='Midplane' else {})
        except ValueError:pass
        else:raise AssertionError('Degenerate geometry accepted: '+kind)
    # Sketch support remains associative to a custom plane face.
    sketch=d.addObject('Sketcher::SketchObject','Sketch');sketch.AttachmentSupport=[(built['Midplane'],['Face1'])];sketch.MapMode='FlatFace';d.recompute()
    assert abs(sketch.Placement.Base.z-30)<1e-7
    file=os.path.join(tempfile.mkdtemp(prefix='fusionflow-construct-'),'test.FCStd');d.saveAs(file);A.closeDocument(d.Name)
    d=A.openDocument(file);d.getObject('Box').Height=80;d.recompute()
    assert abs(d.getObject('Sketch').Placement.Base.z-40)<1e-7
    assert abs(d.getObject('OffsetPlane').Placement.Base.z-88)<1e-7
    A.closeDocument(d.Name)
    print('PASS: 20 constructions, invalid references, upstream propagation, native expressions, true arc length, sketch support, save/reopen')

if __name__=='__main__':run()
