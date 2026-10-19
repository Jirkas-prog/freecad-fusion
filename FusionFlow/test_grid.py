"""Run with FreeCAD's bundled Python; no GUI or user documents required."""
import sys
from pathlib import Path
import FreeCAD
from pivy import coin
sys.path.insert(0,str(Path(__file__).parent))
from fusionflow_view import grid_geometry,nice_spacing


def run():
    coin.SoDB.init()
    camera=coin.SoOrthographicCamera();camera.position=(0,0,100);camera.focalDistance=100
    assert [nice_spacing(v) for v in (.15,.3,.9,3,8,13)]==[.2,.5,1,5,10,20]
    for extent in (.001,1,100,1e6):
        camera.height=extent
        points,colors,spacing,plane=grid_geometry(camera,(1000,700))
        assert plane==2 and points and len(points)==len(colors)<4500
        assert all(p[2]==0 for p in points)
        assert all(0<=c<=1 for rgb in colors for c in rgb)
        assert spacing>=extent/700*90
        for point in points:
            assert all(abs(c)<1e10 for c in point)
        assert grid_geometry(camera,(1000,700),adaptive=False,major=7)[2]==7
    camera.height=100
    camera.orientation.setValue(coin.SbVec3f(1,0,0),1.5707963267948966)
    points,_,_,plane=grid_geometry(camera,(1000,700))
    assert plane==1 and points and all(p[1]==0 for p in points)
    assert not grid_geometry(camera,(1000,700),'XY')[0],'Edge-on locked plane should be hidden'
    camera.orientation.setValue(coin.SbVec3f(0,1,0),1.5707963267948966)
    points,_,_,plane=grid_geometry(camera,(1000,700))
    assert plane==0 and points and all(p[0]==0 for p in points)
    perspective=coin.SoPerspectiveCamera();perspective.position=(40,40,30);perspective.pointAt(coin.SbVec3f(0,0,0));perspective.focalDistance=64
    points,_,_,plane=grid_geometry(perspective,(400,900))
    assert points and plane==2 and len(points)<4500
    print('PASS: adaptive/fixed spacing, zoom extremes, plane alignment, horizon bound, perspective and narrow views')


if __name__=='__main__':run()
