import os,sys,math
import FreeCAD as A,Part
sys.path.insert(0,os.path.dirname(__file__))
from fusionflow_analysis_math import calculate
from fusionflow_analysis import section_caps,plane_frame

def run():
    d=A.newDocument('AnalysisMath')
    a=d.addObject('Part::Feature','A');a.Shape=Part.makeBox(10,10,10)
    b=d.addObject('Part::Feature','B');b.Shape=Part.makeBox(10,10,10,A.Vector(5,0,0));d.recompute()
    r=calculate('Interference',[(a,['']),(b,[''])],{});assert len(r['solids'])==1 and abs(r['solids'][0].Volume-500)<1e-6
    r=calculate('CenterOfMass',[(a,['']),(b,[''])],{'density':1000});assert (r['markers'][0]-A.Vector(7.5,5,5)).Length<1e-6
    hole=Part.makeBox(10,10,10).cut(Part.makeCylinder(2,10,A.Vector(5,5,0)))
    cap=section_caps(hole,plane_frame(dict(plane='XY',offset=4)));assert abs(cap.Area-(100-4*math.pi))<1e-6 and len(cap.Wires)==2
    c=d.addObject('Part::Feature','C');c.Shape=hole;d.recompute()
    r=calculate('MinimumRadius',[(c,[''])],{'quality':4,'limit':3});assert '2 mm' in r['text'],r['text']
    assert any(color==(.91,.24,.22) for mesh in r['meshes'] for color in mesh['colors'])
    r=calculate('Draft',[(a,[''])],{'quality':4});assert '-90' in r['text'] and '90' in r['text']
    r=calculate('Accessibility',[(a,[''])],{'quality':4});colors={color for mesh in r['meshes'] for color in mesh['colors']};assert (.32,.75,.43) in colors and (.9,.25,.23) in colors
    sphere=d.addObject('Part::Feature','Sphere');sphere.Shape=Part.makeSphere(5);d.recompute()
    for kind in ('CurvatureMap','Zebra','Environment','ComponentColors'):
        r=calculate(kind,[(sphere,[''])],{'quality':4});assert r['meshes'] and r['mask']==[sphere]
    r=calculate('CurvatureComb',[(sphere,[''])],{'count':8});assert r['lines']
    r=calculate('Isocurve',[(sphere,[''])],{'count':3});assert r['lines']
    points=[]
    for p in (A.Vector(),A.Vector(3,4,0)):
        obj=d.addObject('Part::Feature','Point');obj.Shape=Part.Vertex(p);points.append((obj,['']))
    r=calculate('Measure',points,{});assert r['groups'][0][1][0]==('Minimum distance',5,'mm') and len(r['lines'])==2
    r=calculate('Measure',[(a,['Vertex1','Vertex2'])],{});assert r['groups'][0][1][0]==('Minimum distance',10,'mm') and len(r['markers'])==2
    # A selected datum carries an in-plane rotation, not just a normal.
    parent=d.addObject('App::Part','Component')
    parent.Placement=A.Placement(A.Vector(17,-8,11),A.Rotation(31,23,-14))
    datum=d.addObject('App::Plane','ReferencePlane');parent.addObject(datum)
    datum.Placement=A.Placement(A.Vector(4,2,9),A.Rotation(-37,13,51));d.recompute()
    options=dict(plane='Selection',angle_x=18,angle_y=-11,offset=7,reference_axes=True)
    local=A.Rotation(A.Vector(1,0,0),18)*A.Rotation(A.Vector(0,1,0),-11)
    placement=datum.getGlobalPlacement();expected=placement.Rotation*local
    frame=plane_frame(options,[(datum,[''])])
    for axis in (A.Vector(1,0,0),A.Vector(0,1,0),A.Vector(0,0,1)):
        assert (frame.Rotation.multVec(axis)-expected.multVec(axis)).Length<1e-8
    assert (frame.Base-placement.Base-expected.multVec(A.Vector(0,0,7))).Length<1e-8
    # Absence of the flag must preserve old saved tilted sections exactly.
    del options['reference_axes']
    legacy=A.Rotation(A.Vector(0,0,1),placement.Rotation.multVec(A.Vector(0,0,1)))*local
    assert (plane_frame(options,[(datum,[''])]).Rotation.multVec(A.Vector(0,0,1))-legacy.multVec(A.Vector(0,0,1))).Length<1e-8
    parent.addObject(a);a.Placement=A.Placement(A.Vector(3,6,7),A.Rotation(17,-24,39));d.recompute()
    from fusionflow_core import global_shape
    for i,face in enumerate(global_shape(a).Faces,1):
        options.update(reference_axes=True,angle_x=0,angle_y=0)
        frame=plane_frame(options,[(a,['Face%d'%i])])
        assert (frame.Rotation.multVec(A.Vector(0,0,1))-face.normalAt(0,0)).Length<1e-8
        assert (frame.Rotation.multVec(A.Vector(1,0,0))-face.Surface.tangent(0,0)[0]).Length<1e-8
    A.closeDocument(d.Name)
    print('PASS: exact interference, homogeneous centroid, holed section, concave radius, signed draft, ray accessibility, curvature maps, comb and trimmed isocurves')

if __name__=='__main__':run()
