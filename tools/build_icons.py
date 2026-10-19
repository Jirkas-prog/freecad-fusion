"""Rebuild the redistributable SVG vocabulary. No proprietary assets are used."""
from pathlib import Path
import json
import shutil

ROOT = Path(__file__).resolve().parents[1] / 'FusionFlow' / 'icons'
OUT = ROOT / 'public'
OUT.mkdir(exist_ok=True)
BLUE, INK, WHITE = '#83c9f4', '#c7d3df', '#edf4fa'
shapes = {}

def path(d, **attrs):
    return '<path d="%s" %s/>' % (d, ' '.join('%s="%s"' % (k.replace('_','-'),v) for k,v in attrs.items()))

def circle(x,y,r,**attrs):
    return '<circle cx="%s" cy="%s" r="%s" %s/>' % (x,y,r,' '.join('%s="%s"' % (k.replace('_','-'),v) for k,v in attrs.items()))

cube = path('M12 22 32 10 52 22 32 34Z',fill=WHITE) + path('M12 22v23l20 12V34Z',fill=BLUE) + path('M32 34 52 22v23L32 57Z',fill='#6294ba')
plus = path('M48 7v18m-9-9h18',stroke='#64d68b',stroke_width=4)
shapes['body'] = cube
shapes['new_body'] = cube+plus
shapes['component'] = cube+path('M8 10h13M8 10v13m48 31H43m13 0V41',stroke=BLUE)
shapes['folder'] = path('M6 17h19l6 7h27v29H6Z',fill='#879bb1')+path('M6 29h52',stroke=WHITE)
shapes['eye'] = path('M5 32Q32 5 59 32Q32 59 5 32Z')+circle(32,32,9,fill=INK)
shapes['eye_off'] = shapes['eye']+path('M9 8 55 56',stroke='#303641',stroke_width=7)+path('M9 8 55 56',stroke=INK)
shapes['sketch_feature'] = path('M11 15h37v36H11Z',stroke=BLUE)+circle(11,15,2,fill=WHITE)+circle(48,51,2,fill=WHITE)+path('m28 44 23-23 6 6-23 23-9 3Z',fill='#edbd65')
shapes['axis'] = path('M6 55 55 6',stroke=BLUE,stroke_dasharray='6 5')+circle(18,43,3,fill=WHITE)+circle(43,18,3,fill=WHITE)
shapes['origin'] = path('M16 48h40',stroke='#e57578')+path('M16 48V8',stroke='#77c99a')+path('M16 48 6 58',stroke=BLUE)+circle(16,48,3,fill=WHITE)
shapes['coordinates'] = shapes['origin']+path('M51 43 56 48 51 53M11 13 16 8 21 13')
shapes['point'] = circle(32,32,5,fill=BLUE)+path('M32 8v14m0 20v14M8 32h14m20 0h14')
shapes['polyline'] = path('M6 49 20 17 38 43 57 13',stroke=BLUE)+''.join(circle(x,y,2.5,fill=WHITE) for x,y in [(6,49),(20,17),(38,43),(57,13)])
shapes['center_rectangle'] = path('M9 16h46v32H9Z')+path('m9 16 46 32m0-32L9 48',stroke=BLUE,stroke_dasharray='4 4')+circle(32,32,3,fill=BLUE)
shapes['rectangle3'] = path('M9 27 42 8 57 35 24 54Z')+''.join(circle(x,y,3,fill=BLUE) for x,y in [(9,27),(42,8),(57,35)])
shapes['circle3'] = circle(32,32,23)+''.join(circle(x,y,3,fill=BLUE) for x,y in [(9,32),(32,9),(55,32)])
shapes['arc_center'] = path('M9 32A23 23 0 0 1 55 32',stroke=BLUE)+path('M9 32h46',stroke_dasharray='4 4')+circle(32,32,3,fill=WHITE)
shapes['arc3'] = shapes['arc_center']+circle(9,32,3,fill=BLUE)+circle(55,32,3,fill=BLUE)+circle(32,9,3,fill=BLUE)
shapes['ellipse'] = '<ellipse cx="32" cy="32" rx="26" ry="16" transform="rotate(-25 32 32)"/>'+circle(32,32,2,fill=BLUE)
shapes['polygon'] = path('M17 9h30l14 23-14 23H17L3 32Z')+circle(32,32,2,fill=BLUE)
shapes['slot'] = path('M22 16h20a16 16 0 0 1 0 32H22a16 16 0 0 1 0-32Z')+path('M12 32h40',stroke=BLUE,stroke_dasharray='4 4')
shapes['spline'] = path('M5 51C12 7 23 3 31 30S49 63 59 9',stroke=BLUE)+circle(5,51,3,fill=WHITE)+circle(59,9,3,fill=WHITE)
shapes['extend'] = path('M8 49 36 21',stroke=BLUE)+path('M36 21 53 4',stroke=BLUE,stroke_dasharray='4 4')+path('M10 12h46')
shapes['split'] = path('M8 48 26 30m10-10L54 2',stroke=BLUE)+path('M19 13 48 42')+circle(31,25,5,fill='#303641')
shapes['construction'] = path('M8 49 54 10',stroke='#edbd65',stroke_dasharray='7 5')+circle(8,49,2,fill=BLUE)
shapes['project'] = path('M6 42 28 29 56 42 34 55Z',fill='#556b84')+path('M16 9h29v22H16Z',stroke='#ba99e3')+path('M30 19v26m-5-6 5 6 5-6',stroke=BLUE)
shapes['mirror'] = path('M32 4v56',stroke=BLUE,stroke_dasharray='4 4')+path('M8 44V20l14 24ZM56 44V20L42 44Z',fill='#799fbd')
shapes['scale'] = path('M8 36h20v20H8Z',fill=BLUE)+path('M8 8h48v48H34M31 32 53 11m-13 0h13v13')
shapes['sketch_move'] = path('M22 26h20v20H22Z',stroke=BLUE)+path('M32 4v55M5 33h54m-6-6 6 6-6 6M26 10l6-6 6 6')
shapes['draft'] = path('M15 49 23 12h21l10 37Z',fill=BLUE)+path('M10 55h48M13 12v31',stroke_dasharray='3 3')
shapes['loft'] = path('M10 48 22 15h22l10 33Z',fill='#6294ba')+path('M22 15q11-9 22 0q-11 9-22 0M10 48q22-15 44 0q-22 15-44 0',fill=BLUE)
shapes['sweep'] = path('M8 48C8 18 27 13 48 13v17C31 30 25 30 25 48Z',fill=BLUE)+path('M8 48q9-7 17 0q-8 7-17 0',fill=WHITE)
shapes['helix'] = path('M12 15c0-10 40-10 40 0S12 25 12 32s40 0 40 9S12 51 12 55',stroke=BLUE,stroke_width=5)
shapes['circular_pattern'] = circle(32,32,21,stroke_dasharray='3 5')+''.join(path('M%s %sh9v9h-9Z'%(x,y),fill=BLUE) for x,y in [(27,6),(47,27),(27,47),(6,27)])
shapes['appearance'] = circle(32,32,23,fill='#83c9f4')+path('M32 9A23 23 0 0 1 55 32H32Z',fill='#edbd65')+path('M32 32h23a23 23 0 0 1-23 23Z',fill='#77c99a')
shapes['parameters'] = path('M8 16h48M8 32h48M8 48h48')+''.join(path('M%s %sh6v12h-6Z'%(x,y),fill=BLUE) for x,y in [(18,10),(40,26),(25,42)])
shapes['open'] = path('M6 17h19l7 7h23v29H6Z',fill='#799fbd')+path('M6 53 13 30h46l-8 23Z',fill=BLUE)
shapes['save'] = path('M10 8h35l10 10v38H10Z',fill='#799fbd')+path('M19 8h23v18H19ZM19 39h27v17H19Z',fill=WHITE)
shapes['undo'] = path('M9 24h28q18 0 18 17v8M9 24 23 10M9 24l14 14',stroke=BLUE,stroke_width=4)
shapes['redo'] = '<g transform="translate(64 0) scale(-1 1)">'+shapes['undo']+'</g>'
shapes['view_home'] = path('M6 30 32 8 58 30H49v25H15V30Z',fill='#a9bdce')+path('M26 55V38h12v17',fill='#45556a')
shapes['view_fit'] = path('M7 24V8h16M41 8h16v16M57 40v16H41M23 56H7V40')+circle(32,32,11,stroke=BLUE)
shapes['view_look_at'] = path('M8 28h48v27H8Z',fill='#607d98')+path('M32 4v32m-7-7 7 7 7-7',stroke=BLUE,stroke_width=4)
shapes['view_display'] = path('M6 10h52v35H6ZM32 45v11m-13 0h26')+path('M12 16h40v23H12Z',fill='#607d98')
shapes['view_grid'] = path('M8 8h48v48H8ZM8 24h48M8 40h48M24 8v48M40 8v48',stroke=INK)
for n,d in [('first','M12 15v34M49 15 25 32l24 17Z'),('previous','M45 15 19 32l26 17Z'),('next','M19 15 45 32 19 49Z'),('end','M52 15v34M15 15 39 32 15 49Z')]:
    shapes['history_'+n]=path(d,fill=INK)
shapes['constraint_coincident']=circle(25,32,13)+circle(40,32,13,stroke='#e8898f')
shapes['constraint_parallel']=path('M10 45 39 16M25 49 54 20',stroke='#e8898f')
shapes['constraint_perpendicular']=path('M13 12v39h39M13 38h13v13',stroke='#e8898f')
shapes['constraint_tangent']=circle(28,28,19)+path('M9 47h49',stroke='#e8898f')
shapes['constraint_equal']=path('M12 24h40M12 40h40',stroke='#e8898f',stroke_width=5)
shapes['constraint_symmetry']=path('M32 5v54',stroke_dasharray='4 4')+path('M8 21 22 32 8 43M56 21 42 32 56 43',stroke='#e8898f')
shapes['constraint_fix']=path('M15 29h34v27H15Z',fill='#e8898f')+path('M22 29V17a10 10 0 0 1 20 0v12')+circle(32,40,3,fill='#303641')

manifest={}
for source in (ROOT/'ribbon').glob('*.svg'):
    shutil.copy2(source,OUT/source.name)
for source in ROOT.glob('*.svg'):
    if not (OUT/source.name).exists():shutil.copy2(source,OUT/source.name)
for name,body in shapes.items():
    svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64"><g fill="none" stroke="%s" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">%s</g></svg>\n'%(INK,body)
    (OUT/(name+'.svg')).write_text(svg,encoding='utf-8')
for p in sorted(OUT.glob('*.svg')):
    manifest[p.stem]={size:{'file':p.name} for size in ('16','32')}
(OUT/'manifest.json').write_text(json.dumps({'origin':'Original FusionFlow vector artwork','license':'LGPL-2.1-or-later','icons':manifest},indent=2)+'\n',encoding='utf-8')
print('Built',len(manifest),'original, scalable icons')
