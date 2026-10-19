"""Construction cards with explicit references and native Undo previews."""
import FreeCAD as A
import FreeCADGui as Gui
from PySide import QtCore as C, QtWidgets as W
from pivy import coin
from fusionflow_ui import Panel,combo,number,selection,selected_name,open_panel
from fusionflow_construct import LABELS,DEFAULTS,reference_roles,create

HINTS={
 'OffsetPlane':'Distance: rovinná stěna / rovina nebo XY/XZ/YZ. To object: rovina a cílový vrchol / bod; Offset přidá další odsazení.',
 'AnglePlane':'Přímá hrana nebo osa, kolem které se rovina otáčí.',
 'TangentPlane':'Válcová nebo kuželová stěna + volitelný bod. Bez bodu určuje polohu Angle.',
 'Midplane':'Dvě rovinné stěny / roviny. Reverse přepne úhlovou půlící rovinu.',
 'PerpendicularPlane':'Stěna / rovina + volitelný bod. U/V určuje směr u rovinné stěny; na zakřivené stěně vznikne tečná rovina v bodě.',
 'TwoEdgesPlane':'Dvě přímé koplanární hrany / osy.',
 'ThreePointsPlane':'Tři nekolineární vrcholy / konstrukční body.',
 'PathPlane':'Jedna hrana cesty; Proportional měří podíl skutečné délky. To object vyžaduje druhou referenci: bod.',
 'CylinderAxis':'Válcová, kuželová nebo toroidální stěna.',
 'NormalAxis':'Stěna + volitelný vrchol / bod, který se promítne na její povrch.',
 'TwoPlanesAxis':'Dvě nerovnoběžné rovinné stěny / roviny.',
 'TwoPointsAxis':'Dva různé vrcholy / konstrukční body.',
 'EdgeAxis':'Přímá hrana nebo osa.',
 'VertexPoint':'Vrchol / konstrukční bod.',
 'TwoEdgesPoint':'Dvě protínající se přímé hrany; uvažuje i jejich prodloužení.',
 'ThreePlanesPoint':'Tři roviny s jediným společným průsečíkem.',
 'CenterPoint':'Kruhová hrana, kulová nebo toroidální stěna.',
 'EdgePlanePoint':'Hrana a rovinná stěna / rovina. Musí mít jediný průsečík.',
 'PathPoint':'Jedna hrana cesty; podle délky nebo s druhou referencí: bodem.',
 'UCS':'Rovinná stěna / rovina, nebo základní XY/XZ/YZ. Posuny jsou v místních osách.'}


class ConstructPanel(Panel):
    def __init__(self,kind,obj=None):
        super().__init__(LABELS[kind].upper())
        self.kind=kind;self.edit_name=obj.Name if obj else None
        self.pick_root=self.pick_guard=None
        self.required,self.roles=reference_roles(kind,{name:getattr(obj,name,value) if obj else value for name,value in DEFAULTS.items()})
        loaded=[(source,[sub]) for source,subs in obj.References for sub in subs or ['']] if obj else []
        self.slots=loaded+[None]*max(0,len(self.roles)-len(loaded))
        self.pick_index=next((i for i,entry in enumerate(self.slots) if entry is None),0)
        self.selection_error=''
        self.hint=W.QLabel(HINTS[kind]);self.hint.setWordWrap(True);self.fields.addRow(self.hint)
        self.refs=W.QListWidget();self.refs.setFixedHeight(28*len(self.slots)+4)
        self.refs.currentRowChanged.connect(self.choose_reference);self.fields.addRow('References',self.refs)
        self.refs.itemClicked.connect(lambda item:self.choose_reference(self.refs.row(item)))
        self.pick_status=W.QLabel();self.pick_status.setWordWrap(True);self.fields.addRow(self.pick_status)
        buttons=W.QWidget();layout=W.QHBoxLayout(buttons);layout.setContentsMargins(0,0,0,0)
        for title,callback in [('Use selection',self.use_selection),('Remove',self.remove),('Clear',self.clear)]:
            b=W.QPushButton(title);b.clicked.connect(callback);layout.addWidget(b)
        self.fields.addRow(buttons)
        self.widgets={}
        for name,default in DEFAULTS.items():
            value=getattr(obj,name,default) if obj else default
            if name=='SizeMode' and obj:value=getattr(obj,name,'Manual')
            if hasattr(value,'Value'):value=value.Value
            if name in ('BasePlane','OffsetMode','PathMode','Direction','SizeMode'):
                values={'BasePlane':['XY','XZ','YZ'],'OffsetMode':['Distance','To object'],'PathMode':['Proportional','Distance','To object'],'Direction':['U','V'],'SizeMode':['Automatic','Manual']}[name]
                widget=combo([(s,s) for s in values]);selected_name(widget,value)
            elif name=='Reverse':widget=W.QCheckBox('Other bisector / reverse path');widget.setChecked(value)
            else:
                widget=number(value,name=='Angle')
                if name=='Angle':widget.setRange(-360,360);widget.setValue(value)
                if name=='Fraction':widget.setSuffix('');widget.setRange(-100,100);widget.setSingleStep(.1)
                if name=='Size':widget.setRange(.01,100000)
            labels={'BasePlane':'Base plane','OffsetMode':'Extent','PathMode':'Position','Direction':'Plane direction','Fraction':'Fraction','Size':'Display size','SizeMode':'Resize'}
            self.widgets[name]=self.row(labels.get(name,name),widget)
        self.widgets['OffsetMode'].currentIndexChanged.connect(self.offset_mode_changed)
        sketch=W.QPushButton('Create Sketch');sketch.clicked.connect(self.create_sketch)
        self.fields.addRow(sketch);sketch.setVisible(kind.endswith('Plane') or kind=='Midplane')
        self.sketch_button=sketch
        self.handles=None
        if kind in ('OffsetPlane','PerpendicularPlane','NormalAxis'):
            from fusionflow_dragger import ConstructionOffsetHandle
            self.handles=ConstructionOffsetHandle(self)
        elif kind=='AnglePlane':
            from fusionflow_dragger import ConstructionAngleHandle
            self.handles=ConstructionAngleHandle(self)
        if not obj:self.use_selection()
        self.refresh_refs();Gui.Selection.addObserver(self);self.schedule()

    @property
    def references(self):
        return [entry for entry in self.slots if entry is not None]

    def offset_mode_changed(self,*_):
        if self.kind!='OffsetPlane':return
        self.required,self.roles=reference_roles(self.kind,self.options())
        self.slots=self.slots[:len(self.roles)]+[None]*max(0,len(self.roles)-len(self.slots))
        self.pick_index=next((i for i,entry in enumerate(self.slots) if entry is None),0)
        self.selection_error='';Gui.Selection.clearSelection();self.refresh_refs();self.schedule()

    def candidate(self,obj,sub):
        if obj is None or obj.Document!=self.doc:return None
        parts=sub.split('.')
        for token in parts[:-1]:
            child=self.doc.getObject(token)
            if child:obj=child
        sub=parts[-1]
        if obj.TypeId=='PartDesign::Body' and obj.Tip:obj=obj.Tip
        # Native datum points report the display name "Point", not a BRep
        # sub-element. Use the whole vertex for live and preselected picks.
        if obj.TypeId=='PartDesign::Point' and sub=='Point':sub=''
        if obj.Name==self.edit_name or obj==self.result or not hasattr(obj,'Shape'):return None
        if self.edit_name and self.doc.getObject(self.edit_name) in obj.OutListRecursive:return None
        return obj,[sub]

    def candidates(self):
        result=[]
        for obj,sub in selection():
            entry=self.candidate(obj,sub)
            if entry and entry not in result:result.append(entry)
        return result

    def use_selection(self):
        refs=self.candidates()
        if not refs:return
        if len(refs)>len(self.roles):
            self.selection_error='Vyber nejvýše %d referencí pro %s.'%(len(self.roles),LABELS[self.kind])
        else:
            self.selection_error=''
            self.slots=refs+[None]*(len(self.roles)-len(refs))
            self.pick_index=min(len(refs),len(self.roles)-1)
        self.refresh_refs();self.schedule()

    def addSelection(self,doc,name,sub,position):
        if self.closed or self.busy or doc!=self.doc.Name:return
        # Consume only this click, never the entire accumulated native selection.
        entry=self.candidate(self.doc.getObject(name),sub)
        if not entry:return
        self.selection_error=''
        if entry in self.slots:self.pick_index=self.slots.index(entry)
        else:
            self.slots[self.pick_index]=entry
            self.pick_index=next((i for i,item in enumerate(self.slots) if item is None),self.pick_index)
        self.refresh_refs();self.schedule()

    def choose_reference(self,row):
        if row<0:return
        self.pick_index=row
        Gui.Selection.clearSelection()
        self.update_pick_status()

    def update_pick_status(self):
        role=self.roles[self.pick_index] if self.pick_index<len(self.roles) else 'Extra reference'
        action='Nahradit' if self.slots[self.pick_index] else 'Vybrat'
        self.pick_status.setText('%s %s: klikni v modelu. Jinou referenci změníš výběrem jejího řádku.'%(action,role))

    def remove(self):
        row=self.refs.currentRow()
        if row<0:return
        if row>=len(self.roles):self.slots.pop(row);self.pick_index=len(self.roles)-1
        else:self.slots[row]=None;self.pick_index=row
        self.selection_error='';Gui.Selection.clearSelection();self.refresh_refs();self.schedule()

    def clear(self):
        self.slots=[None]*len(self.roles);self.pick_index=0;self.selection_error=''
        Gui.Selection.clearSelection();self.refresh_refs();self.schedule()

    def refresh_refs(self):
        self.refs.setFixedHeight(28*len(self.slots)+4)
        blocker=C.QSignalBlocker(self.refs);self.refs.clear()
        for i,entry in enumerate(self.slots):
            role=self.roles[i] if i<len(self.roles) else 'Extra reference'
            if entry:
                obj,subs=entry;value=obj.Label+(' · '+', '.join(s for s in subs if s) if any(subs) else '')
            else:value='Select…'
            item=W.QListWidgetItem(role+' — '+value);item.setToolTip(item.text());item.setSizeHint(C.QSize(0,26))
            self.refs.addItem(item)
        self.refs.setCurrentRow(self.pick_index);del blocker
        self.update_pick_status()

    def options(self):
        return {name:widget.currentData() if isinstance(widget,W.QComboBox) else widget.isChecked() if isinstance(widget,W.QCheckBox) else widget.value() for name,widget in self.widgets.items()}

    def preview(self):
        if self.closed:return
        s=self.options();path=self.kind in ('PathPlane','PathPoint')
        plane=self.kind.endswith('Plane') or self.kind=='Midplane'
        to_object=self.kind=='OffsetPlane' and s['OffsetMode']=='To object'
        visible={'BasePlane':self.kind in ('OffsetPlane','UCS') and not self.references and not to_object,
                 'OffsetMode':self.kind=='OffsetPlane',
                 'Distance':self.kind in ('OffsetPlane','PerpendicularPlane','NormalAxis','UCS') or path and s['PathMode']!='Proportional',
                 'Angle':self.kind in ('AnglePlane','UCS') or self.kind=='TangentPlane' and self.slots[1] is None,
                 'Fraction':path and s['PathMode']=='Proportional','PathMode':path,
                 'Direction':self.kind=='PerpendicularPlane','SizeMode':plane,
                 'Size':not self.kind.endswith('Point') and (not plane or s['SizeMode']=='Manual'),
                 'Reverse':path or self.kind=='Midplane','X':self.kind=='UCS','Y':self.kind=='UCS','Z':self.kind=='UCS'}
        for name,widget in self.widgets.items():self.fields.setRowVisible(widget,visible[name])
        if self.kind=='OffsetPlane':
            self.fields.labelForField(self.widgets['Distance']).setText('Offset' if to_object else 'Distance')
            self.handles.offset_label='Offset' if to_object else 'Distance'
        super().preview();self.sketch_button.setEnabled(bool(self.result))
        if self.selection_error:self.message.show()
        self.restore_picking()
        shown=self.result or (self.doc.getObject(self.edit_name) if self.edit_name else None)
        if shown:
            # Native datum planes ignore ViewObject.Selectable during ray
            # picking. A temporary Coin guard lets clicks reach the model,
            # without modifying or serializing any of the user's view settings.
            self.pick_root=shown.ViewObject.RootNode
            self.pick_guard=coin.SoPickStyle();self.pick_guard.style=coin.SoPickStyle.UNPICKABLE
            self.pick_guard.setOverride(True);self.pick_root.insertChild(self.pick_guard,0)
        if self.handles:self.handles.sync()

    def restore_picking(self):
        if self.pick_root is not None and self.pick_root.findChild(self.pick_guard)>=0:
            self.pick_root.removeChild(self.pick_guard)
        self.pick_root=self.pick_guard=None

    def rollback(self):
        self.restore_picking()
        super().rollback()

    def build(self):
        if self.selection_error:raise ValueError(self.selection_error)
        required,_=reference_roles(self.kind,self.options())
        # Preserve roles when, for example, Plane is picked before Edge.
        needed=required if required else 1 if any(self.slots) else 0
        for index in range(needed):
            if self.slots[index] is None:raise ValueError('Vyber referenci: '+self.roles[index]+'.')
        return create(self.doc,self.kind,self.references,self.options(),self.doc.getObject(self.edit_name) if self.edit_name else None)

    def create_sketch(self):
        if not self.accept():return
        obj=self.result
        doc=obj.Document;active=Gui.activeDocument();body=active.activeView().getActiveObject('pdbody')
        doc.openTransaction('Create Sketch on construction plane')
        try:
            if not body or body.TypeId!='PartDesign::Body':body=doc.addObject('PartDesign::Body','Body')
            support=obj;subs=[''] if obj.TypeId=='PartDesign::Plane' else ['Face1']
            owner=obj.getParentGeoFeatureGroup()
            if owner!=body:
                support=body.newObject('PartDesign::SubShapeBinder','SketchPlane')
                support.Label='Sketch plane reference'
                support.Support=[(owner,[obj.Name+'.'+subs[0]])] if owner and owner.TypeId=='PartDesign::Body' else [(obj,subs)]
                support.Relative=True;doc.recompute();support.Visibility=False
                subs=['Face1']
            sketch=body.newObject('Sketcher::SketchObject','Sketch')
            sketch.AttachmentSupport=[(support,subs)]
            sketch.MapMode='ObjectXY' if support==obj and obj.TypeId=='PartDesign::Plane' else 'FlatFace'
            doc.recompute()
            if 'Invalid' in sketch.State:raise ValueError(sketch.getStatusString())
            doc.commitTransaction()
        except Exception as error:
            doc.abortTransaction();W.QMessageBox.warning(Gui.getMainWindow(),'Create Sketch',str(error));return
        active.activeView().setActiveObject('pdbody',body);Gui.Selection.clearSelection()
        C.QTimer.singleShot(0,lambda:active.setEdit(sketch.Name))

    def finish(self):
        self.restore_picking()
        if self.handles:self.handles.close()
        Gui.Selection.removeObserver(self);super().finish()


def open_construct(kind,obj=None):open_panel(lambda:ConstructPanel(kind,obj))


def install():
    from fusionflow_ui import Command
    import fusionflow_icons as icons
    for kind,label in LABELS.items():
        picture='axis' if kind.endswith('Axis') else 'point' if kind.endswith('Point') else 'coordinates' if kind=='UCS' else 'construct'
        icons.COMMANDS['FusionFlow_'+kind]=picture
        Gui.addCommand('FusionFlow_'+kind,Command(label,lambda k=kind:open_construct(k),picture,HINTS[kind]))
