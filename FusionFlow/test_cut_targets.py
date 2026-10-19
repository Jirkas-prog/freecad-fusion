"""Native multi-body cut selection, rollback and FCStd persistence."""
import os,sys,tempfile
import FreeCAD as A,Part
sys.path.insert(0,os.path.dirname(__file__))
from fusionflow_core import cut_all,extrude,body_of
from test_face_extrude import box,near

def snapshot(body):
    return body.Tip.Name,body.AllowCompound,body.Shape.exportBrepToString(),body.Visibility

def run():
    d=A.newDocument('SelectiveCut');d.UndoMode=1
    a,source=box(d);b,_=box(d,(0,5,0));miss,_=box(d,(30,0,0))
    tiny,_=box(d,(6,1,1),(2,2,2))
    pref=A.ParamGet('User parameter:BaseApp/Preferences/Document');old=pref.GetBool('DuplicateLabels',False)
    pref.SetBool('DuplicateLabels',True);a.Label=b.Label='Same label';pref.SetBool('DuplicateLabels',old)
    assert a.Label==b.Label
    b.Visibility=False
    original={o.Name for o in d.Objects};original_a=snapshot(a);original_miss=snapshot(miss)
    d.openTransaction('Selected bodies')
    cuts=cut_all(source,['Face2'],targets=[b,tiny,b,miss],length=5,reverse=True)
    assert {body_of(f).Name for f in cuts}=={b.Name,tiny.Name}
    assert len(cuts)==2
    near(a.Shape.Volume,1000);near(b.Shape.Volume,750);near(tiny.Shape.Volume,0)
    assert snapshot(a)==original_a and snapshot(miss)==original_miss
    assert not any('Invalid' in o.State for o in d.Objects)
    d.abortTransaction();d.recompute()
    assert {o.Name for o in d.Objects}==original and not b.Visibility
    print('PASS: arbitrary subset, duplicate labels/targets, excluded source unchanged, missed body unchanged, complete removal, rollback')
    for targets in ([],[miss]):
        d.openTransaction('Invalid selection')
        try:
            cut_all(source,['Face2'],targets=targets,length=5,reverse=True)
            raise AssertionError('Empty or missed selection accepted')
        except ValueError:pass
        d.abortTransaction();d.recompute()
        assert {o.Name for o in d.Objects}==original and snapshot(a)==original_a
    foreign=A.newDocument('Other');foreign_body,_=box(foreign);A.setActiveDocument(d.Name)
    d.openTransaction('Wrong document')
    try:
        cut_all(source,['Face2'],targets=[b,foreign_body],length=5,reverse=True)
        raise AssertionError('Mixed documents accepted')
    except ValueError:pass
    d.abortTransaction();A.closeDocument(foreign.Name)
    print('PASS: zero selected never means all; nonintersecting and cross-document targets rejected')
    # Subset wrapper preserves the native extent/direction/taper calculations.
    for options in (dict(length=4,start=-1,taper=6,reverse=True),
                    dict(length=3,length2=4,direction='Two sides'),
                    dict(length=6,direction='Symmetric'),
                    dict(extent='All',reverse=True),
                    dict(extent='To object',end_face=(source,['Face1']),reverse=True)):
        d.openTransaction('Native reference');f=extrude(source,['Face2'],'Cut',b,**options)
        expected=f.Shape.Volume;d.abortTransaction();d.recompute()
        d.openTransaction('Subset');cut=cut_all(source,['Face2'],targets=[b],**options)
        near(cut[0].Shape.Volume,expected);assert snapshot(a)==original_a
        d.abortTransaction();d.recompute()
    print('PASS: offset, taper, two sides, symmetric, Through All and To Object match native single-target results')
    d.openTransaction('Saved subset');cut_all(source,['Face2'],targets=[b,tiny],length=5,reverse=True);d.commitTransaction()
    path=os.path.join(tempfile.mkdtemp(prefix='fusionflow-subset-'),'subset.FCStd')
    names=[a.Name,b.Name,miss.Name,tiny.Name];d.saveAs(path);A.closeDocument(d.Name)
    d=A.openDocument(path);d.recompute()
    for name,expected in zip(names,(1000,750,1000,0)):near(d.getObject(name).Shape.Volume,expected)
    assert all(o.TypeId not in ('Part::FeaturePython','PartDesign::FeaturePython') for o in d.Objects)
    A.closeDocument(d.Name)
    d=A.newDocument('StackedCut');d.UndoMode=1
    bodies=[box(d,(0,0,z))[0] for z in (0,20,40)]
    s=d.addObject('Sketcher::SketchObject','Profile')
    points=[(0,0),(5,0),(5,10),(0,10),(0,0)]
    for p,q in zip(points,points[1:]):s.addGeometry(Part.LineSegment(A.Vector(*p,0),A.Vector(*q,0)),False)
    d.recompute();d.openTransaction('Through selected')
    cuts=cut_all(s,[1],targets=[bodies[0],bodies[2]],extent='All')
    assert len(cuts)==2
    for b,volume in zip(bodies,(500,1000,500)):near(b.Shape.Volume,volume)
    d.abortTransaction();d.recompute();d.openTransaction('Default all')
    assert len(cut_all(s,[1],extent='All'))==3
    d.abortTransaction();A.closeDocument(d.Name)
    print('PASS: native FCStd reopen; shared sketch cuts chosen separated bodies; default still includes all')

if __name__=='__main__':run()
