"""Live measurement selection and grouped, individually copyable results."""
import json
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore as C, QtWidgets as W
from fusionflow_ui import Panel, PREF, combo, selected_name, selection
from fusionflow_analysis import create_analysis
from fusionflow_analysis_math import calculate, measure_value
import fusionflow_analysis_view as graphics


class MeasurePanel(Panel):
    def __init__(self,obj=None):
        super().__init__('MEASURE')
        self.edit_name=obj.Name if obj else None
        self.selection_error=''
        self.data=None
        settings=json.loads(obj.Settings) if obj else {}
        loaded=[(source,[sub]) for source,subs in obj.References for sub in subs or ['']] if obj else []
        # Keep older saved measurements with more than two sources editable.
        numbers=settings.get('selection_numbers',list(range(1,len(loaded)+1)))
        if len(numbers)!=len(loaded) or len(set(numbers))!=len(numbers) or any(not isinstance(n,int) or not 1<=n<=12 for n in numbers):numbers=list(range(1,len(loaded)+1))
        self.slots=[None]*max([2]+numbers)
        for n,entry in zip(numbers,loaded):self.slots[n-1]=entry
        self.pick_index=next((i for i,entry in enumerate(self.slots) if entry is None),0)
        prefs=App.ParamGet(PREF)
        self.precision=self.row('Precision',combo([(str(i)+' decimals',i) for i in range(10)]))
        selected_name(self.precision,settings.get('precision',prefs.GetInt('MeasurePrecision',3)))
        self.secondary=self.row('Secondary units',combo([(s,s) for s in ('None','cm','m','in','ft')]))
        selected_name(self.secondary,settings.get('secondary',prefs.GetString('MeasureSecondary','None')))
        self.delta=self.row('XYZ Delta',combo([(s,s) for s in ('None','Global','Selection 1','Selection 2')]))
        selected_name(self.delta,settings.get('delta','None'))
        self.delta.setToolTip('Rozdíl nejbližších bodů (2 − 1). Selection 1/2 používá osy tělesa či nadřazené komponenty; bez rodiče osy objektu.')
        self.refs=W.QListWidget();self.refs.setFixedHeight(28*len(self.slots)+4)
        self.refs.itemClicked.connect(lambda item:self.choose(self.refs.row(item)))
        self.refs.currentRowChanged.connect(self.choose)
        self.fields.addRow(self.refs)
        self.hint=W.QLabel();self.hint.setWordWrap(True);self.fields.addRow(self.hint)
        buttons=W.QWidget();layout=W.QHBoxLayout(buttons);layout.setContentsMargins(0,0,0,0);layout.setSpacing(4)
        for label,callback in (('Use selection',self.use_selection),('Clear Selection',self.clear)):
            button=W.QPushButton(label);button.clicked.connect(callback);layout.addWidget(button)
        self.fields.addRow(buttons)
        self.results=W.QTreeWidget();self.results.setColumnCount(2);self.results.setHeaderHidden(True)
        self.results.setRootIsDecorated(True);self.results.setIndentation(12)
        self.results.setHorizontalScrollBarPolicy(C.Qt.ScrollBarAlwaysOff)
        self.results.setStyleSheet('QTreeWidget {border:0;} QTreeWidget::item {min-height:23px;} QTreeWidget::item:selected {background:#4c657c;}')
        self.results.header().setSectionResizeMode(0,W.QHeaderView.ResizeToContents)
        self.results.header().setSectionResizeMode(1,W.QHeaderView.Stretch)
        self.results.itemClicked.connect(self.copy_value)
        self.fields.addRow(self.results)
        self.copy=W.QPushButton('Copy all results');self.copy.clicked.connect(self.copy_all);self.fields.addRow(self.copy)
        self.ok.setText('OK' if obj else 'Save')
        self.ok.setToolTip('Uložit asociativní měření do Analysis. Close pouze zavře dočasné měření.')
        cancel=next(b for b in self.form.findChildren(W.QPushButton) if b.text()=='Cancel')
        cancel.setText('Cancel' if obj else 'Close')
        self.refresh_refs()
        if not obj:self.use_selection()
        Gui.Selection.addObserver(self)
        self.schedule()

    @property
    def references(self):return [entry for entry in self.slots if entry is not None]

    def candidate(self,obj,sub):
        if obj is None or obj.Document!=self.doc:return None
        parts=sub.split('.')
        for token in parts[:-1]:
            child=self.doc.getObject(token)
            if child:obj=child
        sub=parts[-1]
        if obj.TypeId=='PartDesign::Body' and obj.Tip:obj=obj.Tip
        if not hasattr(obj,'Shape') or obj.Shape.isNull() or getattr(obj,'AnalysisType',''):return None
        return obj,[sub]

    def use_selection(self):
        refs=[]
        for obj,sub in selection():
            entry=self.candidate(obj,sub)
            if entry and entry not in refs:refs.append(entry)
        if not refs:return
        if len(refs)>len(self.slots):self.selection_error='Vyber nejvýše %d prvky. Clear Selection zahájí nové měření.'%len(self.slots)
        else:
            self.selection_error='';self.slots=refs+[None]*(len(self.slots)-len(refs))
            self.pick_index=min(len(refs),len(self.slots)-1)
        self.refresh_refs();self.schedule()

    def addSelection(self,doc,name,sub,position):
        if self.closed or self.busy or doc!=self.doc.Name:return
        entry=self.candidate(self.doc.getObject(name),sub)
        if not entry:return
        self.selection_error=''
        if entry in self.slots:self.pick_index=self.slots.index(entry)
        else:
            self.slots[self.pick_index]=entry
            self.pick_index=next((i for i,item in enumerate(self.slots) if item is None),self.pick_index)
        self.refresh_refs();self.schedule()

    def choose(self,row):
        if row<0:return
        self.pick_index=row;Gui.Selection.clearSelection();self.update_hint()

    def update_hint(self):
        self.hint.setText('Kliknutím v modelu %s Selection %d. Jiný prvek změníš výběrem jeho řádku.'%('nahradíš' if self.slots[self.pick_index] else 'doplníš',self.pick_index+1))

    def refresh_refs(self):
        blocker=C.QSignalBlocker(self.refs);self.refs.clear()
        for i,entry in enumerate(self.slots):
            value=entry[0].Label+(' · '+entry[1][0] if entry[1][0] else '') if entry else 'Select…'
            item=W.QListWidgetItem('Selection %d — %s'%(i+1,value));item.setToolTip(item.text());self.refs.addItem(item)
        self.refs.setCurrentRow(self.pick_index);del blocker;self.update_hint()

    def clear(self):
        self.slots=[None]*len(self.slots);self.pick_index=0;self.selection_error=''
        Gui.Selection.clearSelection();self.refresh_refs();self.schedule()

    def settings(self):
        return dict(precision=self.precision.currentData(),secondary=self.secondary.currentData(),delta=self.delta.currentData(),
                    selection_numbers=[i+1 for i,entry in enumerate(self.slots) if entry is not None])

    def preview(self):
        if self.closed:return
        collapsed={self.results.topLevelItem(i).text(0) for i in range(self.results.topLevelItemCount()) if not self.results.topLevelItem(i).isExpanded()}
        self.data=None
        super().preview()
        self.results.clear()
        if self.result and self.data:
            # Native single-click selection normally replaces the previous
            # highlight. Keep both measurement references visible without Ctrl.
            self.busy=True
            try:
                Gui.Selection.clearSelection()
                for source,subs in self.references:
                    for sub in subs:Gui.Selection.addSelection(source,sub)
            finally:self.busy=False
            for title,rows in self.data['groups']:
                group=W.QTreeWidgetItem(self.results,[title]);group.setFirstColumnSpanned(True)
                for label,value,unit in rows:
                    text=measure_value(value,unit,self.settings());item=W.QTreeWidgetItem(group,[label,text])
                    item.setData(1,C.Qt.UserRole,text);item.setToolTip(1,'Kliknutím zkopíruješ: '+text)
                    item.setTextAlignment(1,C.Qt.AlignRight|C.Qt.AlignVCenter)
                group.setExpanded(title not in collapsed)
        elif self.selection_error:self.message.show()
        self.results.setVisible(bool(self.result));self.copy.setEnabled(bool(self.result))
        self.results.setFixedHeight(min(330,max(80,25*sum(1+(g.childCount() if g.isExpanded() else 0) for g in (self.results.topLevelItem(i) for i in range(self.results.topLevelItemCount()))))))
        self.update_layout()

    def build(self):
        if self.selection_error:raise ValueError(self.selection_error)
        settings=self.settings();self.data=calculate('Measure',self.references,settings)
        obj=self.doc.getObject(self.edit_name) if self.edit_name else create_analysis(self.doc,'Measure',settings,self.references)
        if not self.edit_name:obj.Label='Measure'
        obj.Settings=json.dumps(settings);obj.References=self.references
        obj.ViewObject.Visibility=True
        self.doc.recompute();graphics.manager.dirty=True;graphics.manager.update()
        if obj.Result.startswith('Analýza:'):raise ValueError(obj.Result)
        return obj

    def copy_value(self,item,column):
        text=item.data(1,C.Qt.UserRole)
        if column==1 and text:W.QApplication.clipboard().setText(text)

    def copy_all(self):
        if self.result:W.QApplication.clipboard().setText(self.result.Result)

    def rollback(self):
        super().rollback()
        if graphics.manager:graphics.manager.dirty=True;graphics.manager.update()

    def finish(self):
        prefs=App.ParamGet(PREF);prefs.SetInt('MeasurePrecision',self.precision.currentData());prefs.SetString('MeasureSecondary',self.secondary.currentData())
        Gui.Selection.removeObserver(self)
        super().finish();graphics.manager.dirty=True;graphics.manager.update()
