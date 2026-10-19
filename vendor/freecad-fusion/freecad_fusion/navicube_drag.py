"""Click-and-drag on the NaviCube orbits the view, like Fusion's ViewCube.

FreeCAD's own NaviCube only reacts to clicks (and dragging it moves the widget,
see FreeCAD issue #6306). This module installs a Qt event filter on every 3D
view viewport:

* press + drag inside the cube  -> unlimited turntable orbit (yaw around Z,
  pitch around the camera's right axis), with the cursor anchored at the press;
* press + release without moving -> the original click is replayed to the
  NaviCube, so clicking faces/edges/corners and the arrow buttons still works.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

from . import params

DRAG_THRESHOLD = 4  # px of movement before a press becomes a drag


def _sensitivity():
    return params.group().GetFloat("NaviCubeDragDegPerPx", 0.5)


def _invert():
    return params.group().GetBool("NaviCubeDragInvert", False)


def enabled():
    return params.group().GetBool("NaviCubeDrag", True)


def _cube_rect(widget):
    """Draggable area: the centre of the NaviCube (arrows at the edges keep clicking)."""
    p = App.ParamGet("User parameter:BaseApp/Preferences/NaviCube")
    size = p.GetInt("CubeSize", 0) or 132
    corner = p.GetInt("CornerNaviCube", 1)  # 0 TL, 1 TR, 2 BL, 3 BR
    ox, oy = p.GetInt("OffsetX", 0), p.GetInt("OffsetY", 0)
    w, h = widget.width(), widget.height()
    x = w - size - ox if corner in (1, 3) else ox
    y = oy if corner in (0, 1) else h - size - oy
    m = size * 0.2
    return QtCore.QRectF(x + m, y + m, size - 2 * m, size - 2 * m)


def _view_for(widget):
    w = widget
    while w is not None and not isinstance(w, QtWidgets.QMdiSubWindow):
        w = w.parent()
    if w is not None:
        area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
        if area is not None and area.activeSubWindow() is not w:
            area.setActiveSubWindow(w)
    try:
        return Gui.activeView()
    except Exception:
        return None


def orbit(view, dx, dy):
    """Turntable orbit around the camera focal point."""
    from pivy import coin

    k = _sensitivity() * (-1.0 if _invert() else 1.0)
    cam = view.getCameraNode()
    rot = cam.orientation.getValue()
    fd = cam.focalDistance.getValue()
    pos = cam.position.getValue()
    focal = pos + rot.multVec(coin.SbVec3f(0, 0, -1)) * fd
    right = rot.multVec(coin.SbVec3f(1, 0, 0))
    yaw = coin.SbRotation(coin.SbVec3f(0, 0, 1), math.radians(-dx * k))
    pitch = coin.SbRotation(right, math.radians(-dy * k))
    new = rot * pitch * yaw
    cam.orientation.setValue(new)
    cam.position.setValue(focal - new.multVec(coin.SbVec3f(0, 0, -1)) * fd)


class _Filter(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.press = None
        self.owner = None
        self.dragging = False
        self.bypass = False
        self.view = None
        QtWidgets.QApplication.instance().applicationStateChanged.connect(self.application_state_changed)

    def cancel(self):
        owner, self.owner = self.owner, None
        self.press = self.view = None
        self.dragging = False
        if owner is not None and QtWidgets.QWidget.mouseGrabber() is owner:
            owner.releaseMouse()  # also restores the cursor supplied to grabMouse

    def application_state_changed(self, state):
        if state != QtCore.Qt.ApplicationActive:
            self.cancel()

    def viewport_destroyed(self, identity):
        if self.owner is not None and id(self.owner) == identity:
            self.cancel()
        _installed.discard(identity)

    def eventFilter(self, obj, ev):  # noqa: N802 (Qt API)
        if self.bypass:
            return False
        if not enabled():
            self.cancel()
            return False
        t = ev.type()
        if obj is self.owner:
            if t in (QtCore.QEvent.Hide, QtCore.QEvent.Close, QtCore.QEvent.FocusOut,
                     QtCore.QEvent.WindowDeactivate, QtCore.QEvent.UngrabMouse):
                self.cancel()
                return False
            if t in (QtCore.QEvent.ShortcutOverride, QtCore.QEvent.KeyPress) and ev.key() == QtCore.Qt.Key_Escape:
                ev.accept()
                if t == QtCore.QEvent.KeyPress:self.cancel()
                return True
        if t == QtCore.QEvent.MouseButtonPress and ev.button() == QtCore.Qt.LeftButton:
            if _cube_rect(obj).contains(ev.position()):
                self.cancel()
                self.owner = obj
                self.press = (ev.position(), ev.globalPosition(), ev.modifiers())
                return True
        elif t == QtCore.QEvent.MouseMove and self.press is not None and obj is self.owner:
            if not ev.buttons() & QtCore.Qt.LeftButton:
                self.cancel()
                return True
            if not self.dragging:
                if (ev.globalPosition() - self.press[1]).manhattanLength() < DRAG_THRESHOLD:
                    return True
                self.view = _view_for(obj)
                if self.view is None:
                    self.cancel()
                    return True
                self.dragging = True
                obj.setFocus(QtCore.Qt.MouseFocusReason)
                obj.grabMouse(QtGui.QCursor(QtCore.Qt.ClosedHandCursor))
            # Read the current OS position, not a possibly queued pre-warp
            # event. Our own recenter events then have a zero delta and cannot
            # undo the orbit or count the same physical movement twice.
            anchor = self.press[1].toPoint()
            delta = QtGui.QCursor.pos() - anchor
            if not delta.isNull():
                try:
                    orbit(self.view, delta.x(), delta.y())
                    QtGui.QCursor.setPos(anchor)
                except Exception as error:
                    self.cancel()
                    App.Console.PrintWarning('[freecad-fusion] Orbit stopped: %s\n' % error)
            return True
        elif (
            t == QtCore.QEvent.MouseButtonRelease
            and self.press is not None
            and obj is self.owner
            and ev.button() == QtCore.Qt.LeftButton
        ):
            press, dragged = self.press, self.dragging
            self.cancel()
            if dragged:
                if QtGui.QCursor.pos() != press[1].toPoint():
                    QtGui.QCursor.setPos(press[1].toPoint())
                return True
            # No drag: replay the original click so the NaviCube handles it.
            self.bypass = True
            try:
                for et, btns in (
                    (QtCore.QEvent.MouseButtonPress, QtCore.Qt.LeftButton),
                    (QtCore.QEvent.MouseButtonRelease, QtCore.Qt.NoButton),
                ):
                    QtWidgets.QApplication.sendEvent(
                        obj,
                        QtGui.QMouseEvent(et, press[0], press[1], QtCore.Qt.LeftButton, btns, press[2]),
                    )
            finally:
                self.bypass = False
            return True
        return False


_filter = None
_installed = set()


def _viewports():
    mw = Gui.getMainWindow()
    return [
        w
        for w in mw.findChildren(QtWidgets.QWidget)
        if w.metaObject().className() == "QOpenGLWidget"
        and w.parent() is not None
        and w.parent().metaObject().className() == "Gui::View3DInventorViewer"
    ]


def install_all(*_):
    global _filter
    if _filter is None:
        _filter = _Filter()
    for w in _viewports():
        if id(w) not in _installed:
            w.installEventFilter(_filter)
            _installed.add(id(w))
            w.destroyed.connect(lambda *_a, i=id(w): _filter.viewport_destroyed(i) if _filter else _installed.discard(i))


def start():
    install_all()
    area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
    if area is not None:
        area.subWindowActivated.connect(lambda *_: QtCore.QTimer.singleShot(0, install_all))
