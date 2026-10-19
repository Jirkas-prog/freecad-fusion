"""Run with FreeCAD's Python: associative sizing must not move sketch support."""
import os,sys,tempfile
import FreeCAD as A
import Part,Sketcher
sys.path.insert(0,os.path.dirname(__file__))
from fusionflow_construct import create,plane_size

def run():
    d=A.newDocument('PlaneSizing')
    box=d.addObject('Part::Box','Box');box.Length=240;box.Width=80;box.Height=20
    box.Placement=A.Placement(A.Vector(75,-42,30),A.Rotation(A.Vector(1,2,3),37));d.recompute()
    native=create(d,'OffsetPlane',[(box,['Face6'])],{'Distance':5})
    assert native.SizeMode=='Automatic' and native.ResizeMode=='Automatic'
    assert not any(path in ('Length','Width') for path,_ in native.ExpressionEngine)
    plane=create(d,'Midplane',[(box,['Face5','Face6'])],{})
    sketch=d.addObject('Sketcher::SketchObject','Sketch');sketch.AttachmentSupport=[(plane,['Face1'])];sketch.MapMode='FlatFace'
    sketch.addGeometry(Part.Circle(A.Vector(8,6,0),A.Vector(0,0,1),4),False);d.recompute()
    before=sketch.Placement
    # The stable support frame need not align with the rotated rectangle.
    # Its finite display must contain every projected reference corner.
    corners=[plane.Placement.inverse().multVec(v.Point) for f in (box.Shape.Faces[4],box.Shape.Faces[5]) for v in f.Vertexes]
    width,height=plane_size(plane.References,plane.Placement,60)
    assert all(abs(p.x)<width/2 and abs(p.y)<height/2 for p in corners)
    assert plane.Shape.Area>240*80
    # Resizing only changes finite display geometry, not its attachment frame.
    create(d,'Midplane',plane.References,{'SizeMode':'Manual','Size':17},plane);d.recompute()
    assert abs(plane.Shape.Area-17**2)<1e-7
    assert (sketch.Placement.Base-before.Base).Length<1e-7 and sketch.Placement.Rotation.isSame(before.Rotation,1e-7)
    create(d,'Midplane',plane.References,{'SizeMode':'Automatic'},plane);d.recompute()
    assert (sketch.Placement.Base-before.Base).Length<1e-7 and sketch.Placement.Rotation.isSame(before.Rotation,1e-7)
    box.Length=400;d.recompute();assert plane.Shape.Area>400*80
    assert plane.Shape.isValid() and 'Invalid' not in sketch.State
    # Pre-existing documents without the property keep their manual dimensions.
    create(d,'Midplane',plane.References,{'SizeMode':'Manual','Size':41},plane);plane.removeProperty('SizeMode');plane.touch();d.recompute()
    assert abs(plane.Shape.Area-41**2)<1e-7
    create(d,'Midplane',plane.References,{'Size':41},plane);assert plane.SizeMode=='Manual'
    for options in ({'SizeMode':'Typo'},{'Size':0},{'Size':float('inf')}):
        names={o.Name for o in d.Objects}
        try:create(d,'OffsetPlane',[],options)
        except ValueError:pass
        else:raise AssertionError('Invalid display size accepted')
        assert names=={o.Name for o in d.Objects}
    assert plane_size([],A.Placement(),60)==(60,60)
    create(d,'Midplane',plane.References,{'SizeMode':'Automatic'},plane)
    path=os.path.join(tempfile.mkdtemp(prefix='fusionflow-sizing-'),'sizing.FCStd');d.saveAs(path);A.closeDocument(d.Name)
    d=A.openDocument(path);d.getObject('Box').Length=600;d.recompute()
    assert d.getObject('Midplane').SizeMode=='Automatic' and d.getObject('Midplane').Shape.Area>600*80
    assert not [o.Name for o in d.Objects if 'Invalid' in o.State]
    A.closeDocument(d.Name)
    print('PASS: automatic/manual sizing, rotated references, unchanged sketch frame, upstream edits, legacy, invalid input, reopen')

if __name__=='__main__':run()
