from pathlib import Path
from string import Template
import difflib


def substitute(template_path: str, key_val_maps: dict):
    class CustomTemplate(Template):
        delimiter = '@'

    template = CustomTemplate(Path(template_path).read_text(encoding='UTF8'))
    return template.substitute(key_val_maps)


key_val_maps = dict(APP_NAME='Spyder', WINDOW_TITLE='Spyder', APP_NAME_LOWER='spyder')

installer = substitute('bibiinstaller.nsi', key_val_maps)
Path('application.nsi').write_text(installer, newline='\n')

assert installer == Path('spyder.nsi').read_text(encoding='UTF8')
