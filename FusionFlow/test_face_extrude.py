"""Run with FreeCAD's bundled Python; checks native geometry and persistence."""
import os, sys, tempfile
import FreeCAD as A, Part
sys.path.insert(0, os.path.dirname(__file__))
from fusionflow_core import extrude, cut_all, body_of

def box(doc, base=(0,0,0), size=(10,10,10)):
    b = doc.addObject('PartDesign::Body', 'Body')
    p = b.newObject('PartDesign::AdditiveBox', 'Box')
    p.Length, p.Width, p.Height = size
    p.Placement.Base = A.Vector(*base)
    doc.recompute()
    return b, p

def near(actual, expected):
    assert abs(actual-expected) < 1e-5, (actual, expected)

def run():
    d = A.newDocument('FaceExtrudeTest')
    d.UndoMode = 1
    for i in range(1,7):
        b, p = box(d)
        normal = p.Shape.Faces[i-1].normalAt(0,0)
        q = extrude(b, ['Face%d'%i], 'Join', b, length=2)
        near(q.Shape.Volume, 1200)
        near((q.Shape.Solids[0].CenterOfMass-p.Shape.Solids[0].CenterOfMass).dot(normal), 1)
        b2, p2 = box(d)
        cut = extrude(p2, ['Face%d'%i], 'Cut', b2, length=2, reverse=True)
        near(cut.Shape.Volume, 800)
        new = extrude(p, ['Face%d'%i], length=3)
        near(new.Shape.Volume, 300)
    print('PASS: six face normals, Join, inward Cut and New body')
    b, p = box(d)
    b.Placement = A.Placement(A.Vector(70,20,40), A.Rotation(A.Vector(0,1,0), 90))
    d.recompute()
    q = extrude(p, ['Face6'], length=3, start=2)
    near(q.Shape.BoundBox.XMin, 82)
    near(q.Shape.BoundBox.XMax, 85)
    print('PASS: rotated parent placement and face offset')
    # A selected face with a hole keeps the exact face boundary.
    ring = d.addObject('Part::Feature', 'Ring')
    ring.Shape = Part.makeCylinder(5, 10).cut(Part.makeCylinder(2, 10))
    face = next('Face%d'%i for i,f in enumerate(ring.Shape.Faces,1) if isinstance(f.Surface,Part.Plane) and f.CenterOfMass.z>9)
    q = extrude(ring, [face], length=3)
    near(q.Shape.Volume, ring.Shape.getElement(face).Area*3)
    curved = next('Face%d'%i for i,f in enumerate(ring.Shape.Faces,1) if not isinstance(f.Surface,Part.Plane))
    try:
        extrude(ring, [curved])
        raise AssertionError('Curved face accepted')
    except ValueError:
        pass
    print('PASS: holes preserved; curved face explicitly rejected')
    A.closeDocument(d.Name)
    d = A.newDocument('AllBodiesCutTest'); d.UndoMode=1
    source, p = box(d)
    overlap, p2 = box(d, (0,5,0))
    missed, p3 = box(d, (30,0,0))
    removed, p4 = box(d, (6,1,1), (2,2,2))
    before = {o.Name for o in d.Objects}
    tips = {b.Name:b.Tip.Name for b in (source, overlap, missed, removed)}
    d.openTransaction('Preview all cut')
    cuts = cut_all(source, ['Face2'], length=5, reverse=True)
    assert len(cuts)==3
    near(source.Shape.Volume,500); near(overlap.Shape.Volume,750)
    near(missed.Shape.Volume,1000); near(removed.Shape.Volume,0)
    assert missed.Tip is p3
    assert not any('Invalid' in o.State for o in d.Objects)
    d.abortTransaction(); d.recompute()
    assert {o.Name for o in d.Objects}==before
    assert all(d.getObject(n).Tip.Name==tip for n,tip in tips.items())
    near(source.Shape.Volume,1000); near(overlap.Shape.Volume,1000); near(removed.Shape.Volume,8)
    print('PASS: all intersected bodies, no step for misses, complete removal, Cancel')
    d.openTransaction('Cut all')
    cuts=cut_all(source, ['Face2'], length=5, reverse=True)
    d.commitTransaction()
    saved=[(f.Name,f.Shape.Volume) for f in cuts]
    path=os.path.join(tempfile.mkdtemp(prefix='fusionflow-faces-'),'faces.FCStd')
    d.saveAs(path); A.closeDocument(d.Name)
    d=A.openDocument(path); d.recompute()
    for name,volume in saved:
        near(d.getObject(name).Shape.Volume, volume)
        assert 'Invalid' not in d.getObject(name).State
    # Dependency is the earlier Box face, so an upstream edit still recomputes.
    d.getObject('Box').Width=12; d.recompute()
    assert all('Invalid' not in d.getObject(name).State for name,_ in saved)
    print('PASS: native save/reopen and upstream edit after multi-body cut')
    A.closeDocument(d.Name)
    d=A.newDocument('AllSketchTest')
    from test_core import sketch
    s=sketch(d)
    first=extrude(s,[1,2],length=10)
    second=extrude(s,[1,2],length=6,start=15)
    cuts=cut_all(s,[1],extent='All')
    assert len(cuts)==2
    near(cuts[0].Shape.Volume,s.InternalShape.Faces[1].Area*10)
    near(cuts[1].Shape.Volume,s.InternalShape.Faces[1].Area*6)
    print('PASS: all bodies from a sketch, Through all across separated bodies')
    A.closeDocument(d.Name)

if __name__=='__main__':
    run()
