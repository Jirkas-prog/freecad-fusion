# freecad-fusion: make FreeCAD feel familiar to Autodesk Fusion users.
# Loaded automatically by FreeCAD from its Mod folder (package.xml declares it
# as a <workbench> entry so that FreeCAD runs this file at every startup).


def _freecad_fusion_start():
    import FreeCAD as App

    try:
        from freecad_fusion import commands, navicube_drag, params, presets

        commands.register()
        navicube_drag.start()
        g = params.group()
        first_run = not g.GetBool("FirstRunDone", False)
        # Fusion mode stays on across restarts until the user picks
        # Tools > Restore my previous FreeCAD settings (which sets Enabled=False).
        if first_run or g.GetBool("Enabled", True):
            notes = presets.apply_preset()
            g.SetBool("FirstRunDone", True)
            if first_run:
                App.Console.PrintMessage(
                    "[freecad-fusion] Fusion navigation and shortcuts enabled. "
                    "Undo any time: Tools > Restore my previous FreeCAD settings\n"
                )
            for n in notes:
                App.Console.PrintMessage("[freecad-fusion] %s\n" % n)
    except Exception as exc:  # never break FreeCAD startup
        App.Console.PrintError("[freecad-fusion] failed to start: %s\n" % exc)


try:
    from PySide import QtCore

    QtCore.QTimer.singleShot(1500, _freecad_fusion_start)
except Exception:
    _freecad_fusion_start()
