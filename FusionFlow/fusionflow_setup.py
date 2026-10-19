"""Apply the user's requested light, Fusion-style setup once, through FreeCAD's API."""
from pathlib import Path
import xml.etree.ElementTree as ET
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets


def configure():
    theme = Path(App.getUserAppDataDir()) / 'Mod/OpenTheme/OpenDark'
    if not theme.is_dir():
        raise RuntimeError('Chybí nainstalovaný OpenTheme / OpenDark.')
    # Read the existing theme preference pack. Do not replace user.cfg while FreeCAD runs.
    root = ET.parse(theme / 'OpenDark.cfg').find('./FCParamGroup')
    def apply(node, path):
        for el in node:
            key = el.attrib['Name']
            if el.tag == 'FCParamGroup':
                apply(el, path + '/' + key)
            else:
                group = App.ParamGet('User parameter:' + path.lstrip('/'))
                value = el.attrib.get('Value', el.text or '')
                method, conv = {'FCText': ('SetString', str), 'FCBool': ('SetBool', lambda v: bool(int(v))),
                                'FCInt': ('SetInt', int), 'FCUInt': ('SetUnsigned', int),
                                'FCFloat': ('SetFloat', float)}[el.tag]
                getattr(group, method)(key, conv(value))
    apply(root, '')
    main = App.ParamGet('User parameter:BaseApp/Preferences/MainWindow')
    main.SetString('Theme', 'OpenDark')
    main.SetString('StyleSheet', 'OpenDark.qss')
    main.SetBool('OverlayActive', False)
    general = App.ParamGet('User parameter:BaseApp/Preferences/General')
    general.SetString('AutoloadModule', 'PartDesignWorkbench')
    general.SetBool('ShowTaskWatcher', False)
    general.SetInt('ToolbarIconSize', 24)
    sketch = App.ParamGet('User parameter:BaseApp/Preferences/Mod/Sketcher')
    sketch.SetBool('MakeInternals', True)
    sketch.SetBool('LeaveSketchWithEscape', False)
    view = App.ParamGet('User parameter:BaseApp/Preferences/View')
    view.SetBool('Simple', True)
    view.SetBool('Gradient', False)
    view.SetBool('RadialGradient', False)
    view.SetUnsigned('BackgroundColor', 0x303641FF)
    view.SetUnsigned('DefaultShapeColor', 0xBFC8D2FF)
    view.SetUnsigned('DefaultShapeLineColor', 0x424B56FF)
    view.SetUnsigned('SelectionColor', 0x3997E8FF)
    view.SetUnsigned('HighlightColor', 0x87BDE8FF)
    view.SetFloat('PickRadius', 5.0)
    App.ParamGet('User parameter:BaseApp/Preferences/NaviCube').SetInt('CubeSize', 132)
    App.ParamGet('User parameter:BaseApp/Preferences/Mod/FusionFlow').SetBool('Enabled', True)
    App.ParamGet('User parameter:BaseApp/Preferences/Mod/FusionFlow').SetBool('Configured', True)
    # Theme changes take effect on the next normal FreeCAD startup. Do not
    # replace QApplication's QStyle live: this Windows build can corrupt its
    # Python interpreter when doing so from the embedded console.
    if Gui.activeWorkbench().name() != 'PartDesignWorkbench':
        Gui.activateWorkbench('PartDesignWorkbench')
    App.saveParameter()


def activate():
    import sys
    mod = Path(App.getUserAppDataDir()) / 'Mod'
    for path in [mod / 'freecad-fusion', mod / 'FusionFlow']:
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from freecad_fusion import commands, navicube_drag
    if 'FusionMode_ApplyPreset' not in Gui.listCommands():
        commands.register()
    if navicube_drag._filter is None:
        navicube_drag.start()
    configure()
    import fusionflow_ui
    fusionflow_ui.install()
    main = Gui.getMainWindow()
    for dock in main.findChildren(QtWidgets.QDockWidget):
        if dock.objectName() in ('Python console', 'Report view'):
            dock.hide()
    App.saveParameter()
    App.Console.PrintMessage('Nastavení FusionFlow bylo použito a uloženo.\n')
