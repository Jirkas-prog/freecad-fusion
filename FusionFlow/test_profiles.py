"""Compare live-preview regions to native sketch InternalShape; bundled python.exe."""
import math
import FreeCAD as A, Part, Sketcher
from fusionflow_profiles import ProfileBuilder


def rectangle(s, x, y, w, h):
    pts=[(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)]
    s.addGeometry([Part.LineSegment(A.Vector(*p,0),A.Vector(*q,0)) for p,q in zip(pts,pts[1:])],False)


def compare(builder, s, count):
    builder.update(s)
    assert A.ActiveDocument == s.Document
    assert len(builder.shape.Faces)==count,(s.Name,len(builder.shape.Faces),count)
    s.MakeInternals=True;s.Document.recompute()
    expected=sorted(f.Area for f in s.InternalShape.Faces)
    actual=sorted(f.Area for f in builder.shape.Faces)
    assert len(actual)==len(expected),(actual,expected)
    assert all(abs(a-b)<1e-7 for a,b in zip(actual,expected)),(actual,expected)
    assert all(f.isValid() for f in builder.shape.Faces)


def run():
    d=A.newDocument('ProfileTest');d.UndoMode=1
    builder=ProfileBuilder()
    try:
        s=d.addObject('Sketcher::SketchObject','Regions');rectangle(s,0,0,40,30)
        s.addGeometry(Part.LineSegment(A.Vector(15,0,0),A.Vector(15,30,0)),False)
        s.addGeometry(Part.Circle(A.Vector(30,15,0),A.Vector(0,0,1),4),False)
        compare(builder,s,3)
        assert not builder.update(s),'Unchanged geometry should be cached'
        s.addGeometry(Part.LineSegment(A.Vector(0,10,0),A.Vector(40,10,0)),True)
        compare(builder,s,3)
        # Opening the outer boundary keeps only the genuinely closed inner circle.
        s.delGeometry(0);compare(builder,s,1)
        s.addGeometry(Part.LineSegment(A.Vector(0,0,0),A.Vector(40,0,0)),False)
        compare(builder,s,3)
        s.addConstraint(Sketcher.Constraint('Diameter',4,8))
        s.setDatum(0,A.Units.Quantity('12 mm'));compare(builder,s,3)
        assert abs(min(f.Area for f in builder.shape.Faces)-36*math.pi)<1e-7
        # Crossing curves, nested loops, and a disconnected open tail.
        circles=d.addObject('Sketcher::SketchObject','CrossingCircles')
        for x in (0,8):circles.addGeometry(Part.Circle(A.Vector(x,0,0),A.Vector(0,0,1),8),False)
        compare(builder,circles,3)
        nested=d.addObject('Sketcher::SketchObject','Nested')
        for radius in (10,6,2):nested.addGeometry(Part.Circle(A.Vector(),A.Vector(0,0,1),radius),False)
        nested.addGeometry(Part.LineSegment(A.Vector(20,0,0),A.Vector(25,0,0)),False)
        compare(builder,nested,3)
        spline=d.addObject('Sketcher::SketchObject','Spline')
        curve=Part.BSplineCurve();curve.interpolate([A.Vector(0,0,0),A.Vector(10,0,0),A.Vector(5,10,0)],PeriodicFlag=True)
        spline.addGeometry(curve,False);compare(builder,spline,1)
        # Projections count only when FreeCAD marks them defining geometry.
        external=d.addObject('Sketcher::SketchObject','Projected')
        external.addExternal(nested.Name,'Edge1',False);d.recompute();compare(builder,external,0)
        external.delExternal(0);external.addExternal(nested.Name,'Edge1',True);d.recompute()
        compare(builder,external,1)
        # Preview reads do not recompute or change the user's source or Undo stack.
        before=(s.GeometryCount,s.ConstraintCount,s.DoF,s.Shape.exportBrepToString(),d.UndoCount)
        builder.update(s)
        assert before==(s.GeometryCount,s.ConstraintCount,s.DoF,s.Shape.exportBrepToString(),d.UndoCount)
        name=builder.document.Name;builder.close();assert name not in A.listDocuments()
        print('PASS: native regions, construction, openings, dimensions, crossings, nested loops, spline, projections, cache and cleanup')
    finally:
        builder.close();A.closeDocument(d.Name)


if __name__=='__main__':run()
