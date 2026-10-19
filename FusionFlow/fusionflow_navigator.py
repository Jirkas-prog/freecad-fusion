"""Document navigation without changing the saved model."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore as C, QtWidgets as W
import fusionflow_inspect as inspect
import fusionflow_icons as icons


def show():
    doc=App.ActiveDocument
    if not doc:return
    dialog=W.QDialog(Gui.getMainWindow());dialog.setWindowTitle('NAVIGATOR');dialog.resize(480,470)
    layout=W.QVBoxLayout(dialog);search=W.QLineEdit();search.setPlaceholderText('Search objects…');layout.addWidget(search)
    tree=W.QTreeWidget();tree.setHeaderLabels(['Object','Type']);layout.addWidget(tree)
    for obj in doc.Objects:
        row=W.QTreeWidgetItem(tree,[obj.Label,obj.TypeId]);row.setData(0,C.Qt.UserRole,inspect.key(obj))
        row.setIcon(0,icons.feature_icon(obj));row.setToolTip(0,inspect.tooltip(obj))
    def filter_rows(text):
        for i in range(tree.topLevelItemCount()):
            row=tree.topLevelItem(i);row.setHidden(text.casefold() not in (row.text(0)+' '+row.text(1)).casefold())
    search.textChanged.connect(filter_rows)
    def selected():
        row=tree.currentItem();return row.data(0,C.Qt.UserRole) if row else None
    buttons=W.QHBoxLayout();layout.addLayout(buttons)
    for title,callback in [('Find in model',lambda:inspect.reveal(selected()) if selected() else None),
                           ('Edit',lambda:inspect.edit_diagnostic(selected()) if selected() else None),
                           ('Close',dialog.close)]:
        button=W.QPushButton(title);button.clicked.connect(callback);buttons.addWidget(button)
    tree.itemDoubleClicked.connect(lambda *_:inspect.reveal(selected()))
    dialog.setAttribute(C.Qt.WA_DeleteOnClose);dialog.show()


def history():
    import fusionflow_ui as ui
    if ui._timeline:ui._timeline.show();ui._timeline.refresh()


def sustainability():
    W.QMessageBox.information(Gui.getMainWindow(),'Sustainability Insights',
        'Tento nástroj Fusion využívá údaje o materiálu, výrobě a emisní databázi. '
        'V místní instalaci tyto podklady nemáme, proto zde uhlíkovou stopu neodhadujeme. '
        'Objem a hmotnost při zadané hustotě získáš přes Inspect → Center of Mass.')


def install():
    from fusionflow_ui import Command
    for name,label,callback in [('Navigator','Navigator',show),('History','History',history),('Sustainability','Sustainability Insights · information',sustainability)]:
        picture='history' if name=='History' else 'select' if name=='Navigator' else 'inspect'
        icons.COMMANDS['FusionFlow_'+name]=picture
        Gui.addCommand('FusionFlow_'+name,Command(label,callback,picture,label))
