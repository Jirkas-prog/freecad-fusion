"""Compact in-canvas input linked to the existing modelling card's fields."""
from PySide import QtCore as C, QtWidgets as W
from pivy import coin


class HandleInput(W.QFrame):
    def __init__(self, handles):
        super().__init__(handles.view.graphicsView().viewport())
        from fusionflow_ui import number
        self.handles = handles
        self.panel = handles.panel
        self.disposed = False
        self.side, self.angle = 0, False
        self.field = None
        self.setObjectName('FusionHandleInput')
        self.setAttribute(C.Qt.WA_StyledBackground)
        self.setStyleSheet('''
            #FusionHandleInput {background:#354252;border:1px solid #657a90;}
            #FusionHandleInput QDoubleSpinBox {background:#253342;color:#eef5fb;
                border:0;padding:3px 5px;font:12px "Segoe UI";selection-background-color:#376b90;}
            #FusionHandleInput QToolButton {background:#354252;color:#dbeaf7;border:0;width:24px;}
            #FusionHandleInput QToolButton:hover {background:#49647f;}
            #FusionHandleInput QMenu {background:#354252;color:#eef5fb;}
            #FusionHandleInput QMenu::item:selected {background:#49647f;}
        ''')
        layout = W.QHBoxLayout(self); layout.setContentsMargins(2,2,2,2); layout.setSpacing(1)
        self.mode = W.QToolButton()
        self.mode.setPopupMode(W.QToolButton.InstantPopup)
        self.menu = W.QMenu(self.mode); self.menu.aboutToShow.connect(self.build_menu)
        self.mode.setMenu(self.menu); layout.addWidget(self.mode)
        self.value = number(); self.value.setFixedWidth(117)
        self.value.valueChanged.connect(self.apply_value)
        self.value.installEventFilter(self)
        self.value.lineEdit().installEventFilter(self)
        layout.addWidget(self.value)
        self.connections = []
        for _,_,_,field in handles.input_options(all_fields=True):
            callback = lambda value, source=field:self.source_changed(source,value)
            field.valueChanged.connect(callback); self.connections.append((field,callback))
        self.setFixedSize(self.sizeHint())
        self.hide()
        self.activate(0,False)

    def options(self):
        return self.handles.input_options()

    def activate(self, side, angle, focus=False):
        if self.disposed:return
        # Symmetric handles share the first side's corresponding parameter.
        options=self.options()
        fallback=next((item for item in options if item[1]==angle),options[0])
        option=next((item for item in options if item[:2]==(side,angle)),fallback)
        self.side,self.angle,label,self.field = option
        blocker = C.QSignalBlocker(self.value)
        self.value.setRange(self.field.minimum(),self.field.maximum())
        self.value.setDecimals(self.field.decimals()); self.value.setSuffix(self.field.suffix())
        self.value.setLocale(self.field.locale()); self.value.setSingleStep(self.field.singleStep())
        self.value.setValue(self.field.value())
        self.value.setStyleSheet('')
        del blocker
        self.mode.setText('∠' if self.angle else '↔')
        self.mode.setAccessibleName('Vybrat rozměr: '+label)
        self.mode.setToolTip(label+' · vybrat jiný rozměr')
        self.value.setAccessibleName(label)
        self.help_text=label+'\nEnter: náhled · Ctrl+Enter: OK · Esc: Cancel · Tab: další rozměr'
        self.value.setToolTip(self.help_text)
        self.place()
        if focus:self.focus_value()

    def focus_value(self):
        if not self.disposed and self.isVisible():
            self.value.setFocus(C.Qt.OtherFocusReason); self.value.selectAll()

    def build_menu(self):
        self.menu.clear()
        for side,angle,label,field in self.options():
            action = self.menu.addAction(label)
            action.setCheckable(True); action.setChecked(field is self.field)
            action.triggered.connect(lambda checked=False,s=side,a=angle:self.activate(s,a,True))

    def source_changed(self, source, value):
        if not self.disposed and source is self.field:
            blocker=C.QSignalBlocker(self.value); self.value.setValue(value); del blocker

    def apply_value(self, value):
        if not self.disposed and self.field is not None:
            self.field.setValue(value)

    def commit(self):
        if not self.value.hasAcceptableInput():
            self.value.setToolTip('Neúplné nebo neplatné číslo. Doplň hodnotu; Esc zruší operaci.')
            self.value.setStyleSheet('border:1px solid #e3a468;')
            self.value.setFocus(C.Qt.OtherFocusReason)
            return False
        self.value.interpretText()
        self.value.setStyleSheet('')
        self.value.setToolTip(self.help_text)
        self.apply_value(self.value.value())
        self.panel.timer.stop(); self.panel.preview()
        return True

    def eventFilter(self, watched, event):
        keys=(C.Qt.Key_Return,C.Qt.Key_Enter,C.Qt.Key_Tab,C.Qt.Key_Backtab,C.Qt.Key_Escape)
        if event.type()==C.QEvent.ShortcutOverride and event.key() in keys:
            event.accept(); return True
        if event.type()==C.QEvent.KeyPress and event.key() in keys:
            key=event.key()
            if key==C.Qt.Key_Escape:self.panel.reject()
            elif key in (C.Qt.Key_Tab,C.Qt.Key_Backtab):
                if not self.commit():return True
                options=self.options(); current=next(i for i,item in enumerate(options) if item[3] is self.field)
                step=-1 if key==C.Qt.Key_Backtab or event.modifiers() & C.Qt.ShiftModifier else 1
                side,angle,_,_=options[(current+step)%len(options)]
                self.activate(side,angle,True)
            else:
                if not self.commit():return True
                if event.modifiers() & C.Qt.ControlModifier:self.panel.accept()
                else:self.value.selectAll()
            event.accept(); return True
        return super().eventFilter(watched,event)

    def refresh(self):
        if self.disposed:return
        if not any(field is self.field for _,_,_,field in self.options()):self.activate(0,self.angle)
        self.place()

    def place(self):
        if self.disposed:return
        h=self.handles
        if h.root.whichChild.getValue()==coin.SO_SWITCH_NONE:
            self.hide(); return
        anchor=h.input_anchor(self.side)
        size=h.view.getSize(); volume=h.camera.getViewVolume(size[0]/max(1,size[1]))
        if size[0]<size[1]:volume.scale(size[1]/max(1,size[0]))
        screen=volume.projectToScreen(anchor); parent=self.parentWidget()
        point=C.QPoint(round(screen[0]*parent.width()),round((1-screen[1])*parent.height()))
        x,y=point.x()+30,point.y()+12
        # Keep the input out from under the existing operation card.
        card=C.QRect(parent.mapFromGlobal(self.panel.form.mapToGlobal(C.QPoint())),self.panel.form.size())
        if C.QRect(x,y,self.width(),self.height()).intersects(card):x=point.x()-self.width()-30
        x=max(8,min(x,parent.width()-self.width()-8)); y=max(8,min(y,parent.height()-self.height()-8))
        self.move(x,y); self.show(); self.raise_()

    def dispose(self):
        if self.disposed:return
        self.disposed=True
        self.value.blockSignals(True)
        for field,callback in self.connections:field.valueChanged.disconnect(callback)
        self.connections.clear()
        self.value.removeEventFilter(self); self.value.lineEdit().removeEventFilter(self)
        self.hide(); self.deleteLater()
