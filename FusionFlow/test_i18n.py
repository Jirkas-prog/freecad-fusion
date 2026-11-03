"""Message completeness and language fallback in an isolated FreeCAD process."""
import ast
import importlib
import re
from pathlib import Path
import FreeCAD as App
import fusionflow_i18n as messages

root=Path(__file__).parent
catalog=messages._czech
tokens=re.compile(r'%(?!%)(?:\([^)]+\))?[-+# 0]*\d*(?:\.\d+)?[diouxXeEfFgGcrsa]')
for english,czech in catalog.items():
    assert tokens.findall(english)==tokens.findall(czech),(english,czech)
for path in root.glob('*.py'):
    if path.name.startswith('test_'):continue
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='tr' and node.args and isinstance(node.args[0],ast.Constant):
            key=node.args[0].value
            assert key in catalog or key in messages._uppercase,(path.name,node.lineno,key)
# Ribbon captions are variable-fed, while command IDs stay canonical.
for node in ast.walk(ast.parse((root/'fusionflow_ribbon.py').read_text(encoding='utf-8'))):
    if isinstance(node,ast.Call) and node.args and isinstance(node.args[0],ast.Constant):
        name=node.func.attr if isinstance(node.func,ast.Attribute) else node.func.id if isinstance(node.func,ast.Name) else ''
        if name in ('group','item'):
            label=node.args[0].value
            assert label in catalog or label in messages._uppercase,label
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Attribute) and t.attr=='tab_names' for t in node.targets):
        for label in ast.literal_eval(node.value):assert label in messages._uppercase,label
preferences=App.ParamGet('User parameter:BaseApp/Preferences/General')
for selected,expected in [('Czech','cs'),('cs-CZ','cs'),('English','en'),('de','en')]:
    preferences.SetString('Language',selected)
    importlib.reload(messages)
    assert messages.language()==expected
    assert messages.tr('Cancel')==('Zrušit' if expected=='cs' else 'Cancel')
    assert messages.tr('Missing diagnostic from an extension')=='Missing diagnostic from an extension'
    assert messages.is_input_hint(messages.tr('Select a body or geometry to analyse.'))
    assert not messages.is_input_hint('Unexpected geometry failure')
    for error in ('Selected faces must lie in the same plane and point in the same direction.', 'Measurements are limited to 12 references to keep results readable.', 'Centre-of-mass analysis requires solid bodies.'):
        assert not messages.is_input_hint(messages.tr(error)),error
    # A changed preference must not partially relabel an open CAD operation.
    preferences.SetString('Language','English' if expected=='cs' else 'Czech')
    assert messages.language()==expected
print('Catalog, placeholders, fallback and session language passed')
