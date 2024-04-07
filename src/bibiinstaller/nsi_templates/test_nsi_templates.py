from pathlib import Path
from string import Template
import difflib


def update_application_nsi(template_nsi_file, application_nsi_file,
                           app_name: str, window_title: str = None, app_name_lower: str = None):
    def substitute(template_path: str, key_val_maps: dict):
        class CustomTemplate(Template):
            delimiter = '@'

        template = CustomTemplate(Path(template_path).read_text(encoding='UTF8'))
        return template.substitute(key_val_maps)

    if window_title is None:
        window_title = app_name
    if app_name_lower is None:
        app_name_lower = app_name.lower()
    key_val_maps = dict(APP_NAME=app_name, WINDOW_TITLE=window_title, APP_NAME_LOWER=app_name_lower)
    installer = substitute(template_nsi_file, key_val_maps)
    Path(application_nsi_file).write_text(installer, encoding='utf8', newline='\n')
    return Path(application_nsi_file).absolute()


def substitute(template_path: str, key_val_maps: dict):
    class CustomTemplate(Template):
        delimiter = '@'

    template = CustomTemplate(Path(template_path).read_text(encoding='UTF8'))
    return template.substitute(key_val_maps)


key_val_maps = dict(APP_NAME='Spyder', WINDOW_TITLE='Spyder', APP_NAME_LOWER='spyder')

installer = substitute('bibiinstaller.nsi', key_val_maps)
Path('application.nsi').write_text(installer, newline='\n')

assert installer == Path('spyder.nsi').read_text(encoding='UTF8')
