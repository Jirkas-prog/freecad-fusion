# Verification

## FusionFlow 0.21.0 — 2026-11-03

Validated with FreeCAD 1.1.3, Python 3.11.14 and Qt 6.8.3 on Windows.

- All 12 existing geometry regression scripts and the new catalog/language regression pass in isolated processes. The latter checks fixed messages, variable ribbon captions, formatting placeholders, fallback and session language.
- The application starts on a fresh profile; the original generated-model smoke test passes.
- Seven GUI scenarios pass separately in English and Czech: ribbon/workbench switching; literal document and object labels; extrusion with unchanged enum data, geometry, Undo and Redo; all 20 construction cards and cancellation; measurement and numeric clipboard values; analysis and section cards; native sketch editing and the sketch palette.
- Test labels deliberately match interface words (`Cut`, `Select`, `Profile Plane`). They remain literal in both languages. No real user model is opened or changed.
- Release packaging scans tracked source; the ZIP includes the Czech catalog and its published SHA-256 checksum.

Run the language scenarios with `tools/test_gui.ps1 -FreeCAD <path-to-FreeCAD.exe> -Suite language -Language en` and again with `-Language cs`. The runner creates a separate disposable profile and configures its language before startup.

## Original FusionFlow 0.20.0 verification

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
