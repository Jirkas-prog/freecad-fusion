"""Exact measurement checks, using the bundled FreeCAD Python runtime."""
import sys,math
from pathlib import Path
import FreeCAD as A,Part
sys.path.insert(0,str(Path(__file__).parent))
from fusionflow_analysis_math import calculate,measure_value

def run():
    doc=A.newDocument('MeasureMath')
    def feature(name,shape):
        obj=doc.addObject('Part::Feature',name);obj.Shape=shape;return obj
    def measure(*objects,**settings):return calculate('Measure',[(o,['']) for o in objects],settings)
    def row(result,label):
        return next(value for _,rows in result['groups'] for name,value,unit in rows if name==label)
    def near(value,expected):assert abs(value-expected)<1e-7,(value,expected)
    p=feature('Point1',Part.Vertex(A.Vector(1,2,3)));q=feature('Point2',Part.Vertex(A.Vector(4,6,15)))
    data=measure(p,q,precision=0);near(row(data,'Minimum distance'),13)
    for label,value in [('Δ X',3),('Δ Y',4),('Δ Z',12)]:near(row(data,label),value)
    assert row(data,'Minimum distance')==13 # Formatting cannot quantize calculations.
    assert not any(name.startswith('Δ') for _,rows in measure(p,q,delta='None')['groups'] for name,_,_ in rows)
    circle=feature('Circle1',Part.makeCircle(5))
    circle2=feature('Circle2',Part.makeCircle(3,A.Vector(20,0,0)))
    data=measure(circle,circle2);near(row(data,'Minimum distance'),12);near(row(data,'Center distance'),20)
    near(row(data,'Radius'),5);near(row(data,'Diameter'),10);near(row(data,'Length'),math.tau*5)
    assert not any(name.startswith('Position') for _,rows in data['groups'] for name,_,_ in rows)
    # A full circle's single seam vertex is not a point selection.
    cylinder=feature('CylinderFace',Part.makeCylinder(5,12).Faces[0])
    data=measure(cylinder);near(row(data,'Radius'),5);near(row(data,'Area'),math.tau*5*12)
    ring=feature('Ring',Part.Face(Part.Wire(Part.makeCircle(8))).cut(Part.Face(Part.Wire(Part.makeCircle(3)))))
    data=measure(ring);near(row(data,'Area'),math.pi*(64-9))
    line1=feature('Horizontal',Part.makeLine(A.Vector(),A.Vector(5,0,0)))
    line2=feature('Angled',Part.makeLine(A.Vector(),A.Vector(5,5,0)))
    near(row(measure(line1,line2),'Smaller angle'),45)
    plane=feature('Plane',Part.makePlane(10,10))
    upright=feature('Vertical',Part.makeLine(A.Vector(),A.Vector(0,0,5)))
    near(row(measure(plane,upright),'Smaller angle'),90)
    # Frame rotations apply to a displacement, not to an absolute position.
    group=doc.addObject('App::Part','Component');group.addObject(p)
    group.Placement=A.Placement(A.Vector(40,50,60),A.Rotation(A.Vector(0,0,1),90))
    p.Placement=A.Placement(A.Vector(2,0,0),A.Rotation())
    doc.recompute()
    from fusionflow_core import global_shape
    q.Shape=Part.Vertex(global_shape(p).Vertexes[0].Point+A.Vector(0,10,0));doc.recompute()
    data=measure(p,q,delta='Selection 1');near(row(data,'Δ X'),10);near(row(data,'Δ Y'),0)
    data=measure(p,q,delta='Global');near(row(data,'Δ X'),0);near(row(data,'Δ Y'),10)
    assert measure_value(25.4,'mm',{'precision':3,'secondary':'in'})=='25.400 mm (1.000 in)'
    assert measure_value(25.4**2,'mm²',{'precision':3,'secondary':'in'})=='645.160 mm² (1.000 in²)'
    assert measure_value(304.8**3,'mm³',{'precision':0,'secondary':'ft'}).endswith('(1 ft³)')
    assert measure_value(-1e-8,'mm',{'precision':3})=='0.000 mm'
    assert measure_value(45,'°',{'precision':2,'secondary':'in'})=='45.00 °'
    data=measure(q,selection_numbers=[2]);assert data['groups'][0][0].startswith('Selection 2')
    A.closeDocument(doc.Name)
    print('PASS: exact distances, circular centres, surface radius, angles, transformed frames, dimensional unit conversion, display precision and selection numbering')

if __name__=='__main__':run()
