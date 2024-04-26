# -*- coding: utf-8 -*-

"""
NOTES
-----


"""

'''
PROJECTS 
'''
PACKAGE_NAME: str = ''
PYTHON_VERSION: str = '3.10.13'
# '''64 | 32'''
BITNESS: int = 64
# '''  *.png | *.ico '''
ICON_PATH: str = ''
# ''' *.*:main '''
ENTRYPOINT: str = ''
LICENSE_TXT_PATH: str = 'LICENSE.txt'


'''
PACKAGES 
'''
# ''' e.g: extra_requirements.txt '''
EXTRA_REQUIREMENTS_TXT_PATH: str = ''
EXTRA_PACKAGES: list = []
SKIP_PYPI_PACKAGES: list = []
EDITABLE_PACKAGES: list = []
UNWANTED_PACKAGES: list = []

'''
FILES 
'''
# ''' e.g: [ 'libs', 'data_dir', ('from_file', '$INSTDIR/to_dir') ] '''
FILE_CONFIGS: list = []
# ''' e.g: [ 'pkgs/PySide/examples',  'data_dir/ignoredfile' ] '''
EXCLUDE_CONFIGS: list = []
# ''' e.g: pynsist_pkgs '''
ASSETS_PATH: str = ''
