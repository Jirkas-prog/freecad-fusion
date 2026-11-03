"""Owned interface messages; never pass document labels or identifiers to tr().

Use FreeCAD's selected language at the start of the session. A complete language
change takes effect on the next normal startup, without rebuilding open task
panels or altering a document. Geometry, units and command data stay unchanged.
"""
import json
from pathlib import Path

_language = None
try:
    _czech = json.loads((Path(__file__).parent / 'locales' / 'cs.json').read_text(encoding='utf-8'))
except (OSError, ValueError):
    _czech = {}
_uppercase = {key.upper(): value.upper() for key, value in _czech.items()}


def language():
    global _language
    if _language is None:
        try:
            import FreeCADGui as Gui
            selected = Gui.getLocale()
        except (ImportError, AttributeError):
            import FreeCAD as App
            selected = App.ParamGet('User parameter:BaseApp/Preferences/General').GetString('Language', 'English')
        code = selected.lower().replace('_', '-').split('-')[0]
        _language = 'cs' if code in ('cs', 'czech', 'čeština', 'cz') else 'en'
    return _language


def tr(message):
    """Translate a fixed interface template before inserting literal values."""
    if language() != 'cs':
        return message
    return _czech.get(message, _uppercase.get(message, message) if message.isupper() else message)


def is_input_hint(message):
    """Preserve the existing distinction between input prompts and preview errors."""
    prefixes = ('Vyber', 'Nejprve', 'Vzdálenost musí') if language() == 'cs' else ('Select ', 'Finish ', 'Fix ', 'Distance must')
    return message.startswith(prefixes)
