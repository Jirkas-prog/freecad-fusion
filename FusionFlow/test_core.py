"""Run with FreeCAD's bundled bin/python.exe; no desktop interaction."""
import math
import os
import tempfile
import sys
import FreeCAD as A
import Part
import Sketcher
sys.path.insert(0, os.path.dirname(__file__))
from fusionflow_core import extrude, combine, body_of


def sketch(doc):
    s = doc.addObject('Sketcher::SketchObject', 'MasterSketch')
    pts = [(0, 0), (40, 0), (40, 30), (0, 30), (0, 0)]
    for a, b in zip(pts, pts[1:]):
        s.addGeometry(Part.LineSegment(A.Vector(*a, 0), A.Vector(*b, 0)), False)
    s.addGeometry(Part.LineSegment(A.Vector(15, 0, 0), A.Vector(15, 30, 0)), False)
    s.MakeInternals = True
    doc.recompute()
    return s


def run():
    d = A.newDocument('FusionFlowTest')
    d.UndoMode = 1
    s = sketch(d)
    assert len(s.InternalShape.Faces) == 2
    area = s.InternalShape.Faces[0].Area
    p = extrude(s, [1], length=10)
    assert abs(p.Shape.Volume - area * 10) < 1e-6
    b = body_of(p)
    q = extrude(s, [2], 'Join', b, length=10)
    assert abs(q.Shape.Volume - 12000) < 1e-6
    cut = extrude(s, [1], 'Cut', b, length=3, start=7)
    assert abs(cut.Shape.Volume - (12000 - area * 3)) < 1e-6
    # One sketch supplies three native operations. Changing the source regenerates.
    s.addConstraint(Sketcher.Constraint('DistanceX', 4, 1, 18))
    d.recompute()
    assert not cut.Shape.isNull() and cut.Shape.isValid()
    assert abs(cut.Shape.Volume - (12000 - s.InternalShape.Faces[0].Area * 3)) < 1e-6
    before = len(d.Objects)
    d.openTransaction('Preview')
    extrude(s, [1], length=6, direction='Symmetric')
    d.abortTransaction()
    assert len(d.Objects) == before
    both = extrude(s, [1, 2], length=4, length2=2, direction='Two sides')
    assert abs(both.Shape.BoundBox.ZMin + 2) < 1e-6
    assert abs(both.Shape.BoundBox.ZMax - 4) < 1e-6
    assert abs(both.Shape.Volume - 7200) < 1e-6
    reversed_pad = extrude(s, [1], length=5, reverse=True, start=9)
    assert abs(reversed_pad.Shape.BoundBox.ZMin - 4) < 1e-6
    assert abs(reversed_pad.Shape.BoundBox.ZMax - 9) < 1e-6
    tool = extrude(s, [1], length=10)
    fused = combine(body_of(both), [body_of(tool)], 'Join')
    assert fused.Shape.isValid()
    assert abs(fused.Shape.Volume - (7200 + s.InternalShape.Faces[0].Area * 6)) < 1e-6
    # Rotation/translation of source and target must preserve correct coordinates.
    sr = d.addObject('Sketcher::SketchObject', 'Rotated')
    sr.addGeometry(Part.Circle(A.Vector(), A.Vector(0, 0, 1), 3), False)
    sr.Placement = A.Placement(A.Vector(70, 0, 5), A.Rotation(A.Vector(0, 1, 0), 90))
    pp = extrude(sr, [1], length=8, start=2)
    assert abs(pp.Shape.BoundBox.XMin - 72) < 1e-6
    assert abs(pp.Shape.BoundBox.XMax - 80) < 1e-6
    # Through all and target face with end offset are real Pocket/Pad extents.
    full = extrude(s, [1, 2], length=12)
    fb = body_of(full)
    face = next('Face%d' % i for i, f in enumerate(full.Shape.Faces, 1) if abs(f.CenterOfMass.z - 12) < 1e-6)
    upto = extrude(s, [1], extent='To object', end_face=(full, [face]), end_offset=-2)
    assert abs(upto.Shape.BoundBox.ZMax - 10) < 1e-6
    through = extrude(s, [1], 'Cut', fb, extent='All')
    assert abs(through.Shape.Volume - s.InternalShape.Faces[1].Area * 12) < 1e-6
    x = extrude(s, [1, 2], length=10)
    intersected = extrude(s, [1], 'Intersect', body_of(x), length=6)
    assert abs(intersected.Shape.Volume - s.InternalShape.Faces[0].Area * 6) < 1e-6
    # Invalid operations must fail visibly, not leave an accepted wrong solid.
    d.openTransaction('Invalid cut')
    try:
        extrude(s, [99], 'Cut', b)
        raise AssertionError('invalid profile accepted')
    except ValueError:
        d.abortTransaction()
    # Save/reopen without Python proxy objects: the addon is not needed to recompute.
    path = os.path.join(tempfile.mkdtemp(prefix='fusionflow-test-'), 'native.FCStd')
    d.recompute()
    d.saveAs(path)
    saved_name = pp.Name
    A.closeDocument(d.Name)
    reopened = A.openDocument(path)
    reopened.recompute()
    assert all(o.TypeId not in ('Part::FeaturePython', 'PartDesign::FeaturePython') for o in reopened.Objects)
    assert reopened.getObject(saved_name).Shape.isValid()
    A.closeDocument(reopened.Name)
    print('PASS: regions, shared sketch, Join, Cut + offset, propagation, cancel, two sides, reverse, Combine, rotated profile, native save/reopen')


if __name__ == '__main__':
    run()
