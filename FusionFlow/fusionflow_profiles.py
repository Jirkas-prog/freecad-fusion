"""Live sketch-profile shading, calculated by FreeCAD's own internal-face builder."""
import FreeCAD as App
import Part
import Sketcher


def profile_geometry(sketch):
    """Resolved curves in sketch coordinates; construction/reference curves are excluded."""
    curves = [g for i, g in enumerate(sketch.Geometry)
              if not sketch.getConstruction(i) and not isinstance(g, Part.Point)]
    curves.extend(g for g in sketch.ExternalGeo[2:]
                  if not isinstance(g, Part.Point)
                  and Sketcher.ExternalGeometryFacade(g).testFlag('Defining'))
    return curves


class ProfileBuilder:
    def __init__(self):
        self.document = None
        self.sketch = None
        self.signature = None
        self.shape = Part.Shape()

    def update(self, source):
        curves = profile_geometry(source)
        signature = tuple(g.Content for g in curves)
        if signature == self.signature:
            return False
        if self.document is None:
            # Native hidden temporary documents have no 3D tab and are never saved.
            # This keeps preview recomputes away from the user's feature tree and Undo.
            self.document = App.newDocument('FusionFlow_ProfilePreview', 'Profile preview', True, True)
            self.sketch = self.document.addObject('Sketcher::SketchObject', 'Profiles')
            self.sketch.MakeInternals = True
        self.sketch.deleteAllGeometry()
        if curves:
            self.sketch.addGeometry(curves, False)
            # Projected defining curves still carry Sketcher's construction bit.
            # They are ordinary resolved boundaries in this detached preview sketch.
            for i in range(self.sketch.GeometryCount):
                if self.sketch.getConstruction(i):
                    self.sketch.setConstruction(i, False)
        self.document.recompute()
        self.shape = self.sketch.InternalShape.copy()
        self.signature = signature
        return True

    def close(self):
        if self.document and App.getDocument(self.document.Name) == self.document:
            App.closeDocument(self.document.Name)
        self.document = self.sketch = None


class SketchProfiles:
    def __init__(self, sketch):
        import FreeCADGui as Gui
        from pivy import coin
        self.sketch = sketch
        self.builder = ProfileBuilder()
        self.scene = Gui.activeDocument().activeView().getSceneGraph()
        self.scene.ref()
        self.closed = False
        self.dirty = True
        self.placement = None
        self.count = 0
        self.error = ''
        self.root = coin.SoSwitch()
        self.root.setName('FusionFlowSketchProfiles')
        bounds = coin.SoType.fromName('SoSkipBoundingGroup').createInstance()
        bounds.getField('mode').setValue('EXCLUDE_BBOX')
        self.root.addChild(bounds)
        group = coin.SoSeparator();bounds.addChild(group)
        pick = coin.SoPickStyle();pick.style = coin.SoPickStyle.UNPICKABLE
        light = coin.SoLightModel();light.model = coin.SoLightModel.BASE_COLOR
        depth = coin.SoDepthBuffer();depth.test = False;depth.write = False
        material = coin.SoMaterial();material.diffuseColor = (.28,.48,.59);material.transparency = .82
        hints = coin.SoShapeHints();hints.vertexOrdering = coin.SoShapeHints.COUNTERCLOCKWISE
        self.coords = coin.SoCoordinate3()
        self.faces = coin.SoIndexedFaceSet()
        for node in (pick,light,depth,material,hints,self.coords,self.faces):
            group.addChild(node)
        self.scene.addChild(self.root)
        self.viewport = Gui.activeDocument().activeView().graphicsView()
        self.viewport.destroyed.connect(self.close)
        App.addDocumentObserver(self)

    def slotChangedObject(self, obj, prop):
        # Rebuild on edits, not on camera motion or each timer tick. Placement may
        # belong to a parent Body/Part or to an edited link's parent document.
        if prop == 'Placement' or (obj == self.sketch and prop in
                ('Geometry','ExternalGeo','Constraints','AttachmentOffset','AttachmentSupport')):
            self.dirty = True

    def update(self, visible=True):
        import FreeCADGui as Gui
        from pivy import coin
        if self.closed:
            return
        self.root.whichChild = coin.SO_SWITCH_NONE
        if not visible:
            return
        if not self.dirty:
            self.root.whichChild = coin.SO_SWITCH_ALL if not self.error else coin.SO_SWITCH_NONE
            return
        self.dirty = False
        try:
            if self.sketch.ConflictingConstraints or self.sketch.MalformedConstraints or self.sketch.DoF < 0:
                raise ValueError('Nejprve opravte konfliktní vazby skici.')
            changed = self.builder.update(self.sketch)
            placement = App.Placement(Gui.editDocument().EditingTransform)
            if changed or self.placement is None or not placement.isSame(self.placement,1e-9):
                points, indices = [], []
                for face in self.builder.shape.Faces:
                    # Tessellation is only a display approximation; profile boundaries
                    # and the later Extrude still use the exact native CAD geometry.
                    tolerance = max(.001,min(.08,face.BoundBox.DiagonalLength/800))
                    vertices, triangles = face.tessellate(tolerance)
                    base = len(points)
                    points.extend(tuple(placement.multVec(p)) for p in vertices)
                    for triangle in triangles:
                        indices.extend(base+i for i in triangle)
                        indices.append(-1)
                self.faces.coordIndex.setNum(0)
                self.coords.point.setNum(0)
                if points:
                    self.coords.point.setValues(points)
                    self.faces.coordIndex.setValues(indices)
                self.placement = placement
            self.count = len(self.builder.shape.Faces)
            self.error = ''
            self.root.whichChild = coin.SO_SWITCH_ALL
        except Exception as exc:
            # An open/invalid edit must never keep displaying an obsolete closed area.
            self.faces.coordIndex.setNum(0)
            self.placement = None
            self.count = 0
            self.error = str(exc)

    def close(self, *_):
        if self.closed:
            return
        self.closed = True
        from shiboken6 import isValid
        if isValid(self.viewport):
            self.viewport.destroyed.disconnect(self.close)
        App.removeDocumentObserver(self)
        if self.scene.findChild(self.root) >= 0:
            self.scene.removeChild(self.root)
        self.scene.unref()
        self.builder.close()
