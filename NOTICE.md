# Attribution and redistribution

FusionFlow is an independent FreeCAD add-on. It is not affiliated with Autodesk or
the FreeCAD project. Autodesk Fusion is mentioned only to describe familiar
interaction patterns. Report FusionFlow problems in this repository.

| Component | License | Source / notes |
| --- | --- | --- |
| FusionFlow Python code and original SVG artwork | LGPL-2.1-or-later | This repository; copyright FusionFlow contributors |
| `vendor/freecad-fusion` | MIT | [arxdsilva/freecad-fusion](https://github.com/arxdsilva/freecad-fusion), based on 0.1.1. Copyright Arthur Rodrigues Xavier da Silva. Local modifications add unlimited cursor-anchored NaviCube rotation. See its LICENSE. |
| `vendor/OpenTheme` | LGPL-2.1-or-later | [obelisk79/OpenTheme](https://github.com/obelisk79/OpenTheme), package version 2025.05.20. See its LICENSE and source files. |
| FreeCAD, Qt, Open CASCADE, Coin3D, Python | Supplied by your FreeCAD installation | Not bundled in this add-on download. See [FreeCAD](https://github.com/FreeCAD/FreeCAD). |

The public icon pack contains original scalable SVG drawings. It contains no
artwork extracted from Autodesk products. Rebuild it with `python tools/build_icons.py`.
Third-party copyright notices are retained in the corresponding source files.

The installer is maintained here; the upstream navigation add-on's installation
scripts are deliberately excluded from the distribution. Installation does not
contact a server. User documents, settings, recovery files and development logs
are not part of this repository or its release archive.
