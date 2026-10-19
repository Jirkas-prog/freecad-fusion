"""FreeCAD commands for the Tools menu: apply / restore the preset, toggle NaviCube drag."""

import os

import FreeCAD as App
import FreeCADGui as Gui

from . import navicube_drag, params, presets

ICON = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Resources", "icons", "fusion.svg")


def _report(title, notes):
    App.Console.PrintMessage("[freecad-fusion] %s\n" % title)
    for n in notes:
        App.Console.PrintMessage("  - %s\n" % n)


class ApplyPreset:
    def GetResources(self):
        return {
            "MenuText": "Apply Fusion navigation && shortcuts",
            "ToolTip": "Shift+middle-drag orbit, middle-drag pan, zoom at cursor, "
            "Fusion single-key shortcuts and drag-to-orbit NaviCube",
            "Pixmap": ICON,
        }

    def Activated(self):
        _report("Fusion preset applied", presets.apply_preset())

    def IsActive(self):
        return True


class RestoreSettings:
    def GetResources(self):
        return {
            "MenuText": "Restore my previous FreeCAD settings",
            "ToolTip": "Undo everything the Fusion preset changed",
        }

    def Activated(self):
        _report("Settings restored", presets.restore())

    def IsActive(self):
        return params.backup_group().GetBool("HasBackup", False)


class ToggleNaviCubeDrag:
    def GetResources(self):
        return {
            "MenuText": "Drag NaviCube to orbit",
            "ToolTip": "Click and drag the navigation cube to rotate the view, like Fusion's ViewCube",
            "Checkable": navicube_drag.enabled(),
        }

    def Activated(self, checked=None):
        state = bool(checked) if checked is not None else not navicube_drag.enabled()
        params.group().SetBool("NaviCubeDrag", state)

    def IsActive(self):
        return True


COMMANDS = {
    "FusionMode_ApplyPreset": ApplyPreset(),
    "FusionMode_Restore": RestoreSettings(),
    "FusionMode_ToggleNaviCubeDrag": ToggleNaviCubeDrag(),
}


class _Manipulator:
    """Adds the commands to the Tools menu of every workbench."""

    def modifyMenuBar(self):  # noqa: N802 (FreeCAD API)
        return [
            {"insert": name, "menuItem": "Std_DlgParameter"}
            for name in COMMANDS
        ]


def register():
    for name, cmd in COMMANDS.items():
        Gui.addCommand(name, cmd)
    Gui.addWorkbenchManipulator(_Manipulator())
