# Verification for FusionFlow 0.20.0

Validated on 2026-10-20 using the official Windows FreeCAD 1.1.3 runtime,
Python 3.11.14 and Qt 6.8.3. These are reproducible checks, not a claim that every
tool and every possible model is covered.

- All **12 geometry regression scripts** passed in separate processes with an isolated profile:
  analysis, construction, core extrusion/booleans, cut history, cut targets,
  automatic extrusion assistance, face extrusion, grids, measurements, offset planes,
  plane sizing and sketch profiles.
- The **GUI smoke test** started the add-on automatically on a fresh profile,
  checked configuration and all **102 public SVG icons**, created a block from a sketch,
  cut a cylindrical hole, validated the solid and confirmed the bottom timeline was visible.
- The generated block is 60 × 40 × 12 mm with a through hole of radius 10 mm.
  Its expected volume is `(60*40 - pi*10*10)*12 = 25030.08881569225 mm³`.
- `preview.png` is an actual capture from that isolated GUI run, with a generated
  model and generic labels. It contains no personal document or profile information.
- Release packaging scans tracked source for private paths, credentials and unintended
  CAD/log/key files. SHA256SUMS identifies the exact downloadable ZIP.

Run `tools/run_tests.py` with FreeCAD's bundled Python and `tools/test_gui.ps1`
with the FreeCAD executable. Test outputs remain in ignored `test-output/` and
are not uploaded. The installer creates local backups; those are never packaged.

Not covered by this release verification: other operating systems, other FreeCAD
versions, every graphics driver, large assemblies, all combinations of invalid
geometry, or complete behavioural parity with Autodesk Fusion.
