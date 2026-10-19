"""Geometry checks: bundled FreeCAD Python, no running GUI or user documents."""
import sys
from pathlib import Path
import FreeCAD as A, Part
sys.path.insert(0,str(Path(__file__).parent))
from fusionflow_core import suggest_operation,profile_anchor,extrude,body_of
from test_face_extrude import box,near
from test_core import sketch

def state(doc):
    return [(o.Name,getattr(o,'Visibility',None),getattr(o,'Tip',None),
             o.Shape.Volume if hasattr(o,'Shape') else None) for o in doc.Objects]

def run():
    d=A.newDocument('AutoExtrude');d.UndoMode=1
    b,p=box(d)
    for face in range(1,7):
        before=state(d)
        d.openTransaction('Auto preview')
        op,target=suggest_operation(p,['Face%d'%face],length=2)
        assert op=='Join' and target==b,(face,op,target)
        assert state(d)==before,'Probe changed original model'
        assert suggest_operation(p,['Face%d'%face],length=2,reverse=True)==('Cut',None)
        assert state(d)==before,'Probe changed original model'
        d.abortTransaction()
    b.Placement=A.Placement(A.Vector(50,20,30),A.Rotation(A.Vector(0,1,0),90));d.recompute()
    centre,normal=profile_anchor(p,['Face6'])
    near(centre.x,60);near(centre.y,25);near(centre.z,25)
    assert suggest_operation(p,['Face6'],length=3)==('Join',b)
    assert suggest_operation(p,['Face6'],length=3,start=2)==('New body',None)
    assert suggest_operation(p,['Face6'],length=3,reverse=True,taper=10)==('Cut',None)
    A.closeDocument(d.Name)
    d=A.newDocument('SketchAuto');d.UndoMode=1
    s=sketch(d)
    assert suggest_operation(s,[1],length=5)==('New body',None)
    first=extrude(s,[1],length=10);b=body_of(first)
    assert suggest_operation(s,[2],length=10)==('Join',b),'Adjacent regions should join'
    assert suggest_operation(s,[1],length=3)==('Cut',None),'Overlapping region should cut'
    assert suggest_operation(s,[1],length=3,start=12)==('New body',None)
    b.Visibility=False
    assert suggest_operation(s,[1],length=3)==('Cut',None),'Cut includes hidden bodies by user preference'
    before=state(d)
    try:
        suggest_operation(s,[1],length=0)
        raise AssertionError('Zero length accepted')
    except ValueError:
        pass
    assert state(d)==before,'Invalid probe leaked objects or visibility'
    assert suggest_operation(s,[1],extent='All')==('Cut',None)
    A.closeDocument(d.Name)
    d=A.newDocument('ContactAuto')
    b,_=box(d)
    profile=d.addObject('Part::Feature','FaceProfile')
    profile.Shape=Part.makePlane(10,10,A.Vector(10,0,10));d.recompute()
    assert suggest_operation(profile,['Face1'],length=3)==('New body',None),'Edge contact is not Join'
    profile.Shape=Part.makePlane(10,10,A.Vector(10,10,10));d.recompute()
    assert suggest_operation(profile,['Face1'],length=3)==('New body',None),'Point contact is not Join'
    other,_=box(d,(10,0,0))
    profile.Shape=Part.makePlane(20,10,A.Vector(0,0,10));d.recompute()
    assert suggest_operation(profile,['Face1'],length=3)==('Join',None),'Ambiguous Join requires a target'
    A.closeDocument(d.Name)
    print('PASS: face directions, rotated Body, regions, offset/taper, hidden bodies, edge/point contact, ambiguous Join, probe cleanup')

if __name__=='__main__':
    run()
