from PySide import QtCore


def start_fusion_flow():
    import FreeCAD as App
    try:
        preferences = App.ParamGet('User parameter:BaseApp/Preferences/Mod/FusionFlow')
        if not preferences.GetBool('Enabled', True):
            return
        if not preferences.GetBool('Configured', False):
            import fusionflow_setup
            fusionflow_setup.configure()
        import fusionflow_ui
        fusionflow_ui.install()
    except Exception as exc:
        App.Console.PrintError('FusionFlow: %s\n' % exc)


QtCore.QTimer.singleShot(2400, start_fusion_flow)
