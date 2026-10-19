"""Fusion-like navigation settings and keyboard shortcuts, with backup/restore.

Everything the preset changes is backed up the first time it is applied, so
"Restore FreeCAD settings" puts the user's own values back.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import params

VIEW = "User parameter:BaseApp/Preferences/View"

# Fusion default mouse: middle-drag = pan, Shift+middle-drag = orbit,
# wheel = zoom towards the cursor. FreeCAD's "Revit" style uses exactly this
# mapping (src/Gui/Navigation/RevitNavigationStyle.cpp).
VIEW_SETTINGS = {
    "NavigationStyle": ("string", "Gui::RevitNavigationStyle"),
    "ZoomAtCursor": ("bool", True),
}

# Fusion default single-key shortcuts -> closest FreeCAD command.
SHORTCUTS = {
    "L": "Sketcher_CreateLine",          # Line
    "R": "Sketcher_CreateRectangle",     # 2-point rectangle
    "C": "Sketcher_CreateCircle",        # Center diameter circle
    "D": "Sketcher_Dimension",           # Sketch dimension
    "X": "Sketcher_ToggleConstruction",  # Normal / construction
    "T": "Sketcher_Trimming",            # Trim
    "O": "Sketcher_Offset",              # Offset
    "P": "Sketcher_Projection",          # Project / include
    "E": "PartDesign_Pad",               # Extrude
    "H": "PartDesign_Hole",              # Hole
    "F": "PartDesign_Fillet",            # Fillet
    "M": "Std_TransformManip",           # Move / copy
    "I": "Std_Measure",                  # Measure
    "A": "Std_SetAppearance",            # Appearance
}

_GETTERS = {"string": "GetString", "bool": "GetBool", "int": "GetInt", "float": "GetFloat"}
_SETTERS = {"string": "SetString", "bool": "SetBool", "int": "SetInt", "float": "SetFloat"}


def _backup_once():
    b = params.backup_group()
    if b.GetBool("HasBackup", False):
        return
    view = App.ParamGet(VIEW)
    for key, (kind, _value) in VIEW_SETTINGS.items():
        has = key in _keys(view, kind)
        b.SetBool("view.has." + key, has)
        if has:
            getattr(b, _SETTERS[kind])("view." + key, getattr(view, _GETTERS[kind])(key))
    for _key, cmd_name in SHORTCUTS.items():
        _backup_shortcut(b, "shortcut", cmd_name)
    b.SetBool("HasBackup", True)


SHORTCUT_PARAMS = "User parameter:BaseApp/Preferences/Shortcut"


def _backup_shortcut(b, prefix, cmd_name):
    """Remember whether the user had customised this command's shortcut, and to what."""
    if b.GetBool(prefix + ".saved." + cmd_name, False):
        return
    user = App.ParamGet(SHORTCUT_PARAMS)
    custom = cmd_name in user.GetStrings()
    b.SetBool(prefix + ".saved." + cmd_name, True)
    b.SetBool(prefix + ".custom." + cmd_name, custom)
    if custom:
        b.SetString(prefix + "." + cmd_name, user.GetString(cmd_name))


def _restore_shortcut(b, prefix, cmd_name):
    cmd = Gui.Command.get(cmd_name)
    if cmd is None or not b.GetBool(prefix + ".saved." + cmd_name, False):
        return
    if b.GetBool(prefix + ".custom." + cmd_name, False):
        cmd.setShortcut(b.GetString(prefix + "." + cmd_name, ""))
    else:
        cmd.resetShortcut()  # back to FreeCAD's factory default


def _keys(grp, kind):
    lister = {
        "string": grp.GetStrings,
        "bool": grp.GetBools,
        "int": grp.GetInts,
        "float": grp.GetFloats,
    }[kind]
    return lister()


def _load_workbench_commands():
    """Register Sketcher/PartDesign commands so their default shortcuts are known.

    Without this, shortcut conflicts only show up after the workbench is first
    opened, and two commands would end up sharing one key (neither fires).
    """
    for mod in ("SketcherGui", "PartDesignGui", "PartGui"):
        try:
            __import__(mod)
        except Exception:
            pass


def apply_preset():
    """Apply Fusion navigation + shortcuts. Returns a list of human-readable notes."""
    _load_workbench_commands()
    _backup_once()
    notes = []
    view = App.ParamGet(VIEW)
    for key, (kind, value) in VIEW_SETTINGS.items():
        getattr(view, _SETTERS[kind])(key, value)
    for v in _all_views():
        try:
            v.setNavigationType(VIEW_SETTINGS["NavigationStyle"][1])
        except Exception:
            pass
    for key, cmd_name in SHORTCUTS.items():
        cmd = Gui.Command.get(cmd_name)
        if cmd is None:
            notes.append("skipped %s: command %s not available" % (key, cmd_name))
            continue
        # Fusion's key wins; the FreeCAD command that used it is backed up and cleared.
        b = params.backup_group()
        for other in Gui.Command.listByShortcut(key):
            if other == cmd_name:
                continue
            ocmd = Gui.Command.get(other)
            if ocmd is None:
                continue
            _backup_shortcut(b, "displaced", other)
            ocmd.setShortcut("")
            notes.append("%s now runs %s (was %s)" % (key, cmd_name, other))
        cmd.setShortcut(key)
    params.group().SetBool("NaviCubeDrag", True)
    params.group().SetBool("Enabled", True)
    return notes


def restore():
    """Put back the values that were active before the preset was first applied."""
    b = params.backup_group()
    if not b.GetBool("HasBackup", False):
        params.group().SetBool("Enabled", False)
        return ["nothing to restore (preset was never applied)"]
    view = App.ParamGet(VIEW)
    for key, (kind, _value) in VIEW_SETTINGS.items():
        if b.GetBool("view.has." + key, False):
            getattr(view, _SETTERS[kind])(key, getattr(b, _GETTERS[kind])("view." + key))
        else:
            {"string": view.RemString, "bool": view.RemBool, "int": view.RemInt, "float": view.RemFloat}[kind](key)
    style = view.GetString("NavigationStyle", "Gui::CADNavigationStyle")
    for v in _all_views():
        try:
            v.setNavigationType(style)
        except Exception:
            pass
    _load_workbench_commands()
    for _key, cmd_name in SHORTCUTS.items():
        _restore_shortcut(b, "shortcut", cmd_name)
    for name in b.GetBools():
        if name.startswith("displaced.saved."):
            _restore_shortcut(b, "displaced", name[len("displaced.saved."):])
    params.group().SetBool("NaviCubeDrag", False)
    params.group().SetBool("Enabled", False)  # stay off on the next start
    App.ParamGet(params.GROUP).RemGroup("Backup")
    return ["restored previous navigation style and shortcuts"]


def _all_views():
    views = []
    for name in App.listDocuments():
        gdoc = Gui.getDocument(name)
        if gdoc is not None:
            views.extend(gdoc.mdiViewsOfType("Gui::View3DInventor"))
    return views
