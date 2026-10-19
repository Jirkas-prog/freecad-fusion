"""Real OCC geometry, native dependencies and persisted group editing."""
import os
import tempfile
import sys
import FreeCAD as A
import Part
sys.path.insert(0, os.path.dirname(__file__))
from fusionflow_core import cut_all, body_of, extrude
from fusionflow_cut_history import read_group, edit_cut
from test_face_extrude import box, near


def run():
    d = A.newDocument('CutHistory'); d.UndoMode = 1
    a, source = box(d)
    b, base_b = box(d, (0, 5, 0))
    c, base_c = box(d, (0, -5, 0))
    miss, _ = box(d, (30, 0, 0))
    d.openTransaction('Create shared cut')
    cuts = cut_all(source, ['Face2'], [a, b], length=5, reverse=True)
    d.commitTransaction()
    f = cuts[0]; ids = [o.Name for o in cuts]
    assert read_group(f)['selected'] == [a.Name, b.Name]
    # Add later features in both an already cut and an excluded body.
    def later(body, y):
        p = body.newObject('PartDesign::AdditiveBox', 'Later')
        p.Length, p.Width, p.Height = 2, 2, 20
        p.Placement.Base = A.Vector(0, y, 0)
        d.recompute()
        return p
    tail_b, tail_c = later(b, 5), later(c, -5)
    assert tail_b.BaseFeature == cuts[1] and tail_c.BaseFeature == base_c
    baseline = [(o.Name, o.Shape.Volume) for o in (a, b, c, miss)]
    names_before = {o.Name for o in d.Objects}
    d.openTransaction('Edit shared cut')
    results = edit_cut(f, [a.Name, c.Name], length=3)
    assert {body_of(o) for o in results} == {a, c}
    assert d.getObject(ids[1]).Suppressed and tail_b.BaseFeature.Name == ids[1]
    assert b.Tip == tail_b and c.Tip == tail_c
    near(a.Shape.Volume, 700); near(b.Shape.Volume, 1040); near(c.Shape.Volume, 890)
    assert tail_c.BaseFeature.Name == read_group(f)['members'][c.Name]
    assert all('Invalid' not in o.State for o in d.Objects)
    d.abortTransaction(); d.recompute()
    assert {o.Name for o in d.Objects} == names_before
    for name, volume in baseline: near(d.getObject(name).Shape.Volume, volume)
    assert not d.getObject(ids[1]).Suppressed and tail_c.BaseFeature == base_c
    print('PASS: in-place group edit, native suppression, insertion before later feature, Cancel restores identities/links')
    d.openTransaction('Edit shared cut')
    edit_cut(f, [a.Name, c.Name], length=3); d.commitTransaction()
    after = [(o.Name, o.Shape.Volume) for o in (a, b, c, miss)]
    d.undo(); d.recompute()
    for name, volume in baseline: near(d.getObject(name).Shape.Volume, volume)
    d.redo(); d.recompute()
    for name, volume in after: near(d.getObject(name).Shape.Volume, volume)
    d.openTransaction('Re-enable')
    edit_cut(f, [a.Name, b.Name, c.Name], length=4); d.commitTransaction()
    assert d.getObject(ids[1]) == cuts[1] and not cuts[1].Suppressed
    near(b.Shape.Volume, 840); near(c.Shape.Volume, 840)
    print('PASS: one Undo/Redo and re-enable same original Pocket')
    # A missing intersection creates no step in a previously excluded body.
    d.openTransaction('Miss')
    names = {o.Name for o in d.Objects}
    edit_cut(f, [a.Name, miss.Name], length=2)
    assert {o.Name for o in d.Objects} == names
    assert miss.Name not in read_group(f)['members']
    d.abortTransaction(); d.recompute()
    for selection in ([], [miss.Name]):
        d.openTransaction('Invalid edit')
        try:
            edit_cut(f, selection)
            raise AssertionError('Invalid target selection accepted')
        except ValueError: pass
        A.closeActiveTransaction(True); d.recompute()
    # Explicit native changes must not be overwritten by saved group settings.
    d.openTransaction('Native edit'); f.Length = 7; d.recompute()
    try:
        read_group(f)
        raise AssertionError('Native edit overwritten')
    except ValueError as error: assert 'mimo společný editor' in str(error)
    d.abortTransaction(); d.recompute()
    read_group(f)
    path = os.path.join(tempfile.mkdtemp(prefix='fusionflow-history-'), 'edit.FCStd')
    feature_name, source_name, c_name = f.Name, source.Name, c.Name
    d.saveAs(path); A.closeDocument(d.Name)
    d = A.openDocument(path); f = d.getObject(feature_name)
    assert read_group(f)
    assert not any('FeaturePython' in o.TypeId for o in d.Objects)
    d.openTransaction('After reopen')
    edit_cut(f, read_group(f)['selected'], length=2); d.commitTransaction()
    near(d.getObject(c_name).Shape.Volume, 940)
    # Native dependencies continue working without calling the group editor.
    d.getObject(source_name).Height = 12; d.recompute()
    assert not any('Invalid' in o.State for o in d.Objects)
    assert read_group(f)
    A.closeDocument(d.Name)
    print('PASS: misses/None rejected, native edit protected, saved membership reopens, upstream native recompute')
    d = A.newDocument('ProtectLaterChamfer'); d.UndoMode = 1
    b, source = box(d)
    f = cut_all(source, ['Face2'], [b], length=5, reverse=True)[0]
    ch = b.newObject('PartDesign::Chamfer', 'LaterChamfer')
    ch.Base = (f, ['Edge%d' % i for i in range(1, 13)])
    ch.Size = 1; d.recompute()
    original = ch.Shape.Volume
    d.openTransaction('Bad historical dimension')
    try:
        edit_cut(f, [b.Name], length=9.5)
        raise AssertionError('Broken later chamfer accepted')
    except ValueError as error: assert 'LaterChamfer' in str(error)
    A.closeActiveTransaction(True); d.recompute()
    near(ch.Shape.Volume, original)
    assert b.Tip == ch and ch.Base[0] == f and 'Invalid' not in ch.State
    A.closeDocument(d.Name)
    print('PASS: invalid downstream Chamfer rejected atomically and restored')
    d = A.newDocument('EditDirections'); d.UndoMode = 1
    a, source = box(d); b, _ = box(d, (0, 5, 0))
    for options in (dict(length=3, length2=4, direction='Two sides'),
                    dict(length=6, direction='Symmetric'),
                    dict(length=4, start=-1, taper=6, reverse=True),
                    dict(extent='All', reverse=True),
                    dict(extent='To object', end_face=(source, ['Face1']), reverse=True)):
        d.openTransaction('Native reference')
        expected = extrude(source, ['Face2'], 'Cut', b, **options).Shape.Volume
        A.closeActiveTransaction(True); d.recompute()
        d.openTransaction('Create then edit')
        f = cut_all(source, ['Face2'], [b], length=5, reverse=True,
                    start=options.get('start', 0), end_face=options.get('end_face'))[0]
        edit_cut(f, [b.Name], **dict(dict(length=10, length2=10, reverse=False), **options))
        near(b.Shape.Volume, expected)
        A.closeActiveTransaction(True); d.recompute()
    sketch = a.newObject('Sketcher::SketchObject', 'SharedSketch')
    sketch.Placement.Base = A.Vector(0, 0, 10)
    points = [(0, 0), (10, 0), (10, 8), (0, 8), (0, 0)]
    for p, q in zip(points, points[1:]):
        sketch.addGeometry(Part.LineSegment(A.Vector(*p, 0), A.Vector(*q, 0)), False)
    d.recompute()
    f = cut_all(sketch, [1], [a, b], length=5, reverse=True)[0]
    assert f.Profile[0] == sketch
    d.openTransaction('Edit shared sketch cut')
    edit_cut(f, [a.Name, b.Name], length=2)
    near(a.Shape.Volume, 840); near(b.Shape.Volume, 940)
    assert read_group(f)['regions'] == [1]
    A.closeActiveTransaction(True); A.closeDocument(d.Name)
    print('PASS: shared sketch/direct profile, offset, taper, Two Sides, Symmetric, All and To Object edit match native geometry')
    d = A.newDocument('RestoreCompletelyCutBody'); d.UndoMode = 1
    a, source = box(d); tiny, _ = box(d, (6, 1, 1), (2, 2, 2))
    f = cut_all(source, ['Face2'], [a, tiny], length=5, reverse=True)[0]
    member_name = read_group(f)['members'][tiny.Name]
    near(tiny.Shape.Volume, 0)
    d.openTransaction('Restore body')
    edit_cut(f, [a.Name]); near(tiny.Shape.Volume, 8)
    edit_cut(f, [a.Name, tiny.Name]); near(tiny.Shape.Volume, 0)
    edit_cut(f, [a.Name, tiny.Name], length=2); near(tiny.Shape.Volume, 8)
    assert read_group(f)['members'][tiny.Name] == member_name
    A.closeActiveTransaction(True); A.closeDocument(d.Name)
    print('PASS: completely removed body remains selectable, restores and re-cuts with same Pocket')


if __name__ == '__main__': run()
