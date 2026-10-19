"""Run from FreeCAD's bundled Python, one process per geometry regression."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root=Path(__file__).resolve().parents[1]
try:
    import FreeCAD
except ImportError:
    raise SystemExit("Run this script with FreeCAD 1.1.3's bin/python.exe.")
failed=[]
with tempfile.TemporaryDirectory(prefix='fusionflow-test-') as profile:
    env=dict(os.environ,FREECAD_USER_HOME=profile)
    for test in sorted((root/'FusionFlow').glob('test_*.py')):
        result=subprocess.run([sys.executable,str(test)],env=env,timeout=120,capture_output=True,text=True,errors='replace')
        print(('PASS' if result.returncode==0 else 'FAIL')+' '+test.name,flush=True)
        if result.returncode:
            failed.append(test.name)
            print(result.stdout+'\n'+result.stderr)
if failed:raise SystemExit('Failed: '+', '.join(failed))
print('All geometry regressions passed. This does not replace GUI testing.')
