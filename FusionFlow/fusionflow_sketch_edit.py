"""Compact presentation of Sketcher's native, transactional dimension editor."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore as C, QtGui as G, QtWidgets as W
from shiboken6 import isValid


class DimensionEditor(C.QObject):
    def __init__(self):
        super().__init__(Gui.getMainWindow())
        W.QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event):
        if (event.type()==C.QEvent.Polish and isinstance(obj,W.QDialog)
                and obj.objectName() in ('SketcherGui::InsertDatum','SketcherGui__InsertDatum')
                and not obj.property('FusionDatumStyled')):
            self.style(obj)
        return False

    def style(self, dialog):
        # Retain the native input, expression binding, signals and transaction.
        field=dialog.findChild(W.QAbstractSpinBox,'labelEdit')
        buttons=dialog.findChild(W.QDialogButtonBox,'buttonBox')
        name=dialog.findChild(W.QLineEdit,'name')
        reference=dialog.findChild(W.QCheckBox,'cbDriving')
        caption=dialog.findChild(W.QLabel,'label')
        name_caption=dialog.findChild(W.QLabel,'label_2')
        if not all((field,buttons,name,reference,caption,name_caption)):return
        # Double-click already owns a transaction. The native Edit Value command
        # can also open this dialog without one; give that route the same Undo.
        editing=Gui.editDocument()
        selected=Gui.Selection.getSelection()
        document=editing.Document if editing else selected[0].Document if selected else App.ActiveDocument
        if document and not document.HasPendingTransaction:
            document.openTransaction('Modify sketch dimension')
        dialog.setProperty('FusionDatumStyled',True)
        dialog.setWindowFlag(C.Qt.FramelessWindowHint,True)
        dialog.setObjectName('FusionDatumEditor')
        dialog.setStyleSheet('''
          #FusionDatumEditor {background:#394352;border:1px solid #71859c;}
          #FusionDatumEditor QWidget {color:#e4eaf2;font:12px "Segoe UI";}
          #FusionDatumEditor QAbstractSpinBox, #FusionDatumEditor QLineEdit {
            background:#263341;color:#f1f5fa;border:1px solid #7195b3;padding:3px;}
          #FusionDatumEditor QPushButton, #FusionDatumEditor QToolButton {
            background:#46566a;border:1px solid #71859c;padding:2px;min-width:23px;min-height:23px;}
          #FusionDatumEditor QPushButton:hover, #FusionDatumEditor QToolButton:hover {background:#52748e;}
        ''')
        outer=dialog.layout()
        while outer.count():
            item=outer.takeAt(0)
            if item.layout():item.layout().deleteLater()
        outer.setContentsMargins(6,6,6,6);outer.setSpacing(5)
        row=W.QWidget(dialog);line=W.QHBoxLayout(row)
        line.setContentsMargins(0,0,0,0);line.setSpacing(4)
        field.setMinimumWidth(155);field.setButtonSymbols(W.QAbstractSpinBox.NoButtons)
        field.setToolTip(caption.text().rstrip(':')+' · Enter: potvrdit · Esc: zrušit')
        line.addWidget(field,1)
        for role,text,tip in ((W.QDialogButtonBox.Ok,'✓','Potvrdit · Enter'),
                              (W.QDialogButtonBox.Cancel,'×','Zrušit · Esc')):
            button=buttons.button(role);button.setText(text);button.setToolTip(tip)
            button.setFixedSize(27,27)
        line.addWidget(buttons)
        more=W.QToolButton();more.setObjectName('FusionDatumMore')
        more.setText('⋯');more.setCheckable(True);more.setToolTip('Název parametru a referenční kóta')
        line.addWidget(more);outer.addWidget(row)
        details=W.QWidget(dialog);details.setObjectName('FusionDatumDetails')
        grid=W.QGridLayout(details);grid.setContentsMargins(0,0,0,0)
        grid.addWidget(name_caption,0,0);grid.addWidget(name,0,1)
        grid.addWidget(reference,1,0,1,2);outer.addWidget(details)
        caption.hide();details.hide()
        more.toggled.connect(lambda on:self.expand(dialog,details,on))
        outer.setSizeConstraint(W.QLayout.SetFixedSize)
        C.QTimer.singleShot(0,lambda:self.place(dialog,field))

    def expand(self, dialog, details, on):
        details.setVisible(on)
        dialog.adjustSize()
        self.place(dialog)

    def place(self, dialog, field=None):
        if not isValid(dialog):return
        dialog.adjustSize()
        doc=Gui.activeDocument()
        view=doc.activeView() if doc else None
        area=view.graphicsView() if view and hasattr(view,'graphicsView') else Gui.getMainWindow()
        bounds=C.QRect(area.mapToGlobal(C.QPoint()),area.size()).adjusted(8,8,-8,-8)
        point=G.QCursor.pos()+C.QPoint(12,12)
        dialog.move(max(bounds.left(),min(point.x(),bounds.right()-dialog.width())),
                    max(bounds.top(),min(point.y(),bounds.bottom()-dialog.height())))
        if field and isValid(field):
            field.setFocus()
            edit=field.findChild(W.QLineEdit)
            if edit:edit.selectAll()

    def close(self):
        W.QApplication.instance().removeEventFilter(self)
        self.deleteLater()
