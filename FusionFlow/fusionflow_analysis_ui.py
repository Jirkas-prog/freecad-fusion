"""Fusion-style analysis cards reusing the existing transactional panel."""
import json
import FreeCADGui as Gui
from PySide import QtCore as C, QtWidgets as W
from fusionflow_ui import Panel, PickField, combo, number, selected_name, selection, open_panel
from fusionflow_core import body_of
from fusionflow_analysis import SECTION_DEFAULTS, create_analysis, plane_frame, visible_shapes,is_datum_plane
import fusionflow_analysis_view as graphics

LABELS={'Measure':'Measure','Section':'Section Analysis','Interference':'Interference','CenterOfMass':'Center of Mass',
        'CurvatureComb':'Curvature Comb Analysis','Isocurve':'Isocurve Analysis',
        'CurvatureMap':'Curvature Map Analysis','Draft':'Draft Analysis','Accessibility':'Accessibility Analysis',
        'MinimumRadius':'Minimum Radius Analysis','Zebra':'Zebra Analysis','Environment':'Environment Map Analysis',
        'ComponentColors':'Display Component Colors','MeshGroups':'Display Mesh Face Groups'}


def section_reference(doc,obj,sub):
    if obj is None or obj.Document!=doc:return None
    parts=sub.split('.')
    for token in parts[:-1]:
        child=doc.getObject(token)
        if child:obj=child
    sub=parts[-1]
    if obj.TypeId=='PartDesign::Body' and obj.Tip:obj=obj.Tip
    if is_datum_plane(obj):return obj,['']
    if hasattr(obj,'Shape') and sub.startswith('Face'):return obj,[sub]
    return None


class SectionPanel(Panel):
    def __init__(self, obj=None):
        super().__init__('SECTION ANALYSIS')
        self.edit_name=obj.Name if obj else None
        self.references=list(obj.References) if obj else []
        settings=dict(SECTION_DEFAULTS,**json.loads(obj.Settings)) if obj else dict(SECTION_DEFAULTS)
        if obj:settings['reference_axes']=json.loads(obj.Settings).get('reference_axes',False)
        if not obj:
            for source,sub in selection():
                reference=section_reference(self.doc,source,sub)
                if reference:
                    self.references=[reference];settings['plane']='Selection';break
            # A section must not hide geometry before its reference is picked.
            if not self.references:settings['plane']='Selection'
        self.plane=self.row('Plane',combo([(s,s) for s in ('XY','XZ','YZ','Selection')]))
        selected_name(self.plane,settings['plane'])
        self.picking=not obj and not self.references
        self.pick=PickField(self.pick_reference,self.clear_reference)
        self.fields.addRow('Reference',self.pick)
        self.reference_label=W.QLabel();self.reference_label.setWordWrap(True);self.fields.addRow(self.reference_label)
        self.pick_hint=W.QLabel('Vyber rovinnou stěnu nebo konstrukční rovinu kliknutím v modelu či browseru.')
        self.pick_hint.setWordWrap(True);self.fields.addRow(self.pick_hint)
        self.offset=self.row('Distance',number(settings['offset']))
        self.angle_x=self.row('Angle X',number(settings['angle_x'],True))
        self.angle_y=self.row('Angle Y',number(settings['angle_y'],True))
        for field,key in ((self.angle_x,'angle_x'),(self.angle_y,'angle_y')):field.setRange(-360,360);field.setValue(settings[key])
        self.reference_axes=self.row('Angle axes',W.QCheckBox('Follow plane axes'))
        self.reference_axes.setChecked(settings['reference_axes'])
        self.reference_axes.setToolTip('Úhly X/Y se vztahují k osám vybrané roviny. Vypnutí zachová orientaci používanou staršími řezy.')
        self.flip=self.row('Flip',W.QCheckBox('Reverse side'));self.flip.setChecked(settings['flip'])
        self.caps=self.row('Section',W.QCheckBox('Show caps'));self.caps.setChecked(settings['caps'])
        self.hatch=self.row('',W.QCheckBox('Hatch'));self.hatch.setChecked(settings['hatch'])
        self.result_label=W.QLabel();self.result_label.setWordWrap(True);self.fields.addRow(self.result_label)
        from fusionflow_dragger import SectionHandle
        self.handles=SectionHandle(self)
        self.plane.currentIndexChanged.connect(self.plane_changed)
        Gui.Selection.addObserver(self)
        self.schedule()

    def preview(self):
        if self.closed:return
        selected=self.plane.currentData()=='Selection'
        self.fields.setRowVisible(self.reference_axes,selected)
        self.reference_label.setText(', '.join(o.Label+(' · '+', '.join(s for s in subs if s) if any(subs) else '') for o,subs in self.references))
        self.reference_label.setVisible(selected and bool(self.references))
        super().preview()
        if not self.result:
            self.result_label.clear()
            if selected:self.picking=True
        self.pick.update_count(len(self.references) if selected else 0,self.reference_label.text() if selected else '')
        self.pick.button.setChecked(self.picking);self.pick_hint.setVisible(self.picking)
        self.handles.sync();self.update_layout()

    def plane_changed(self,*_):
        self.picking=self.plane.currentData()=='Selection' and not self.references
        self.schedule()

    def pick_reference(self):
        self.picking=True;Gui.Selection.clearSelection()
        self.pick.button.setChecked(True);self.pick_hint.show();self.update_layout()

    def clear_reference(self):
        self.references=[];Gui.Selection.clearSelection();selected_name(self.plane,'Selection')
        self.offset.setValue(0);self.angle_x.setValue(0);self.angle_y.setValue(0)
        self.picking=True;self.schedule()

    def set_reference(self,reference):
        self.references=[reference];selected_name(self.plane,'Selection')
        self.offset.setValue(0);self.reference_axes.setChecked(True);self.picking=False;self.schedule()

    def addSelection(self,doc,name,sub,position):
        if self.closed or self.busy or not self.picking or doc!=self.doc.Name:return
        reference=section_reference(self.doc,self.doc.getObject(name),sub)
        if reference:self.set_reference(reference)

    def use_selection(self):
        for obj,sub in reversed(selection()):
            reference=section_reference(self.doc,obj,sub)
            if reference:self.set_reference(reference);return
        self.pick_reference()

    def settings(self):
        return dict(plane=self.plane.currentData(),offset=self.offset.value(),
                      angle_x=self.angle_x.value(),angle_y=self.angle_y.value(),
                      flip=self.flip.isChecked(),caps=self.caps.isChecked(),hatch=self.hatch.isChecked(),
                      reference_axes=self.reference_axes.isChecked())

    def build(self):
        settings=self.settings()
        references=self.references if settings['plane']=='Selection' else []
        plane_frame(settings,references)
        obj=self.doc.getObject(self.edit_name) if self.edit_name else create_analysis(self.doc,'Section',settings,references)
        if not self.edit_name:obj.Label='Section Analysis'
        obj.Settings=json.dumps(settings);obj.References=references
        obj.ViewObject.Visibility=True
        self.doc.recompute();graphics.manager.dirty=True;graphics.manager.update()
        if obj.Result.startswith('Analýza:'):raise ValueError(obj.Result)
        self.result_label.setText(obj.Result)
        return obj

    def rollback(self):
        super().rollback()
        if graphics.manager:graphics.manager.dirty=True;graphics.manager.update()

    def finish(self):
        Gui.Selection.removeObserver(self)
        self.handles.close()
        super().finish()
        graphics.manager.dirty=True;graphics.manager.update()


def open_analysis(kind='Section', obj=None):
    graphics.install()
    if kind=='Measure':
        from fusionflow_measure_ui import MeasurePanel
        open_panel(lambda:MeasurePanel(obj))
    else:open_panel(lambda:SectionPanel(obj) if kind=='Section' else AnalysisPanel(kind,obj))


class AnalysisPanel(Panel):
    def __init__(self, kind, obj=None):
        from fusionflow_analysis_math import DEFAULTS
        super().__init__(LABELS[kind].upper())
        self.kind=kind;self.edit_name=obj.Name if obj else None
        self.references=list(obj.References) if obj else self.selection_references()
        if not self.references:self.references=[(o,['']) for o in (self.doc.Objects if kind=='MeshGroups' else visible_shapes(self.doc)) if kind!='MeshGroups' or hasattr(o,'Mesh') and o.Visibility]
        settings=dict(DEFAULTS,**json.loads(obj.Settings)) if obj else dict(DEFAULTS)
        if kind=='Accessibility' and not obj:settings['quality']=4
        if kind=='MeshGroups' and not obj:settings['limit']=.01
        select=W.QPushButton('Use selection');select.clicked.connect(self.use_selection)
        self.fields.addRow('Objects',select)
        self.reference_label=W.QLabel();self.reference_label.setWordWrap(True);self.fields.addRow(self.reference_label)
        self.direction=self.row('Direction',combo([(label,axis) for label,axis in [('+X',[1,0,0]),('-X',[-1,0,0]),('+Y',[0,1,0]),('-Y',[0,-1,0]),('+Z',[0,0,1]),('-Z',[0,0,-1])]]))
        selected_name(self.direction,settings['direction'])
        self.quality=self.row('Quality',combo([('Coarse · 4',4),('Medium · 12',12),('Fine · 24',24)]));selected_name(self.quality,settings['quality'])
        self.count=self.row('Count',W.QSpinBox());self.count.setRange(2,60);self.count.setValue(settings['count'])
        self.scale=self.row('Scale',number(settings['scale']));self.scale.setSuffix('');self.scale.setMinimum(.001)
        self.limit=self.row('Angle' if kind=='Draft' else 'Tolerance' if kind=='MeshGroups' else 'Radius limit',number(settings['limit'],kind=='Draft'));self.limit.setMinimum(.001)
        self.curvature=self.row('Curvature',combo([(s,s) for s in ('Gaussian','Minimum','Maximum')]));selected_name(self.curvature,settings['curvature'])
        self.iso=self.row('Direction',combo([(s,s) for s in ('UV','U','V')]));selected_name(self.iso,settings['iso'])
        self.density=self.row('Density',number(settings['density']));self.density.setSuffix(' kg/m³');self.density.setMinimum(0)
        self.density.setToolTip('0: pouze objemový centroid. Kladná hustota se použije stejně na všechna tělesa.')
        self.stripes=self.row('Stripes',W.QSpinBox());self.stripes.setRange(2,60);self.stripes.setValue(settings['stripes'])
        self.rotation=self.row('Rotation',number(settings['rotation'],True))
        self.rotation.setRange(-360,360);self.rotation.setValue(settings['rotation'])
        conditions={self.direction:kind in ('Draft','Accessibility'),self.quality:kind in ('CurvatureMap','Draft','Accessibility','MinimumRadius','Zebra','Environment'),
                    self.count:kind in ('CurvatureComb','Isocurve'),self.scale:kind in ('CurvatureComb','CurvatureMap'),
                    self.limit:kind in ('Draft','MinimumRadius','MeshGroups'),self.curvature:kind=='CurvatureMap',self.iso:kind=='Isocurve',
                    self.density:kind=='CenterOfMass',self.stripes:kind=='Zebra',self.rotation:kind in ('Zebra','Environment')}
        for field,visible in conditions.items():self.fields.setRowVisible(field,visible)
        if kind in ('CurvatureMap','Draft'):
            legend=W.QWidget();legend.setFixedHeight(12)
            legend.setStyleSheet('border:1px solid #7c8898;background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #3359d9,stop:.25 #38bacf,stop:.5 #5cc46b,stop:.75 #f5cc3d,stop:1 #eb3b36);')
            self.fields.addRow(legend)
            label=W.QLabel('− limit                 0                 + limit' if kind=='Draft' else '−1/Scale               0               +1/Scale')
            label.setAlignment(C.Qt.AlignCenter);self.fields.addRow(label)
        self.output=W.QPlainTextEdit();self.output.setReadOnly(True);self.output.setMinimumHeight(100);self.output.setMaximumHeight(150)
        self.fields.addRow(self.output)
        copy=W.QPushButton('Copy results');copy.clicked.connect(lambda:W.QApplication.clipboard().setText(self.output.toPlainText()));self.fields.addRow(copy)
        self.schedule()

    def selection_references(self):
        references=[];seen=set()
        for obj,sub in selection():
            if getattr(obj,'AnalysisType','') or not hasattr(obj,'Mesh' if self.kind=='MeshGroups' else 'Shape'):continue
            if self.kind not in ('Measure','CurvatureComb','Isocurve'):
                owner=body_of(obj);obj=owner if owner and owner.TypeId=='PartDesign::Body' else obj;sub=''
            identity=(obj.Name,sub)
            if identity not in seen:references.append((obj,[sub]));seen.add(identity)
        return references

    def use_selection(self):
        refs=self.selection_references()
        if refs:self.references=refs;self.schedule()
        else:self.message.setText('Vyber geometrii v modelu nebo browseru; Ctrl přidá další výběr.');self.message.show()

    def build(self):
        settings=dict(direction=self.direction.currentData(),quality=self.quality.currentData(),count=self.count.value(),
                      scale=self.scale.value(),limit=self.limit.value(),curvature=self.curvature.currentData(),iso=self.iso.currentData(),
                      density=self.density.value(),stripes=self.stripes.value(),rotation=self.rotation.value())
        self.reference_label.setText(', '.join(o.Label+(' · '+', '.join(s for s in subs if s) if any(subs) else '') for o,subs in self.references))
        obj=self.doc.getObject(self.edit_name) if self.edit_name else create_analysis(self.doc,self.kind,settings,self.references)
        obj.Label=LABELS[self.kind] if not self.edit_name else obj.Label
        obj.Settings=json.dumps(settings);obj.References=self.references;obj.ViewObject.Visibility=True
        self.doc.recompute();graphics.manager.dirty=True;graphics.manager.update()
        if obj.Result.startswith('Analýza:'):raise ValueError(obj.Result)
        self.output.setPlainText(obj.Result)
        return obj

    def rollback(self):
        super().rollback()
        if graphics.manager:graphics.manager.dirty=True;graphics.manager.update()

    def finish(self):
        super().finish();graphics.manager.dirty=True;graphics.manager.update()


def install():
    from fusionflow_ui import Command
    import fusionflow_icons as icons
    graphics.install()
    for kind,label in LABELS.items():
        picture=icons.ANALYSIS_ICONS[kind];icons.COMMANDS['FusionFlow_'+kind]=picture
        Gui.addCommand('FusionFlow_'+kind,Command(label,lambda k=kind:open_analysis(k),picture,label))
