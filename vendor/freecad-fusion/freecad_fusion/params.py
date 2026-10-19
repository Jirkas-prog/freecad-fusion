"""Shared parameter helpers. All add-on state lives in one FreeCAD parameter group."""

import FreeCAD as App

GROUP = "User parameter:BaseApp/Preferences/Mod/FreecadFusion"


def group():
    return App.ParamGet(GROUP)


def backup_group():
    return App.ParamGet(GROUP + "/Backup")
