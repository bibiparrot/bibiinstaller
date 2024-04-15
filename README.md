BibiInstaller
===



## Getting Started
Only for windows environment $package_installer.exe package.

### Requirements and Installation
- Python version >= 3.10
- Pip 

```bash
pip install bibiinstaller
```

Install from source via:

```bash
pip install git+https://github.com/bibiparrot/bibiinstaller.git
```


Or clone the repository and install with the following commands:

```bash
git clone git@github.com:bibiparrot/bibiinstaller.git
cd bibiinstaller
pip install -e .
```



### Usages

configs.py Example

```

'''
PROJECTS 
'''
PACKAGE_NAME: str = 'pyqt6_setup_py_example'
PYTHON_VERSION: str = '3.9.19'
BITNESS: int = 64
ICON_PATH: str = 'pyqt6_example.png'
ENTRYPOINT: str = 'pyqt6_example.pyqt6_example_burning_widget:main'
LICENSE_TXT_PATH: str = 'license.txt'


'''
PACKAGES 
'''
EXTRA_PACKAGES: list = []
EDITABLE_PACKAGES: list = []
UNWANTED_PACKAGES: list = []

EXTRA_REQUIREMENTS_TXT_PATH: str = ''
LOCAL_WHEEL_PATH: str = ''
'''
FILES 
'''
FILE_CONFIGS: list = []
ASSETS_PATH: str = ''

```



### Parse all Arguments from YAML
```
$/env/Scripts/bibiinstaller --help
$/env/Scripts/bibiinstaller configs.py
```



### Examples
- setup.py example, see : [examples/pyqt6_setup_py_example](examples/pyqt6_setup_py_example)
- pyproject.toml example, see : [examples/pyqt6_pyproject_toml_example](examples/pyqt6_pyproject_toml_example)




## Related Information

### Important Dependencies
- pynsist - https://pynsist.readthedocs.io/
- ResourceHacker - https://www.angusj.com/resourcehacker/
- micromamba - https://mamba.readthedocs.io/

# Comparisons

## Python Packages

### Alternatives
- PyInstaller - https://pyinstaller.org/
  * Pros: faster, compiled, smaller; better documents;
  * Cons: OpenCV, Windows msvcrt problems
- pynist - https://pynsist.readthedocs.io/
  * Pros: python embedding, wheel & pip.
  * Cons: larger, slow.
- cx_Freeze
  * Pros: faster, compiled, smaller.
  * Cons: OpenCV, Windows msvcrt problems
- py2exe - https://www.py2exe.org/
  * Pros: faster, compiled, smaller.
  * Cons: compile very hard.
- Conda constructor
  * Pros: python embedding, conda & mamba.
  * Cons: larger, slow.
- Nuitka
  * Pros: faster, compiled, smaller.
  * Cons: compile very hard.

## EXE Packages

### Alternatives
- Wix - https://wixtoolset.org/
- MSIX 
- Nsis  - https://nsis.sourceforge.io/Main_Page
- Advanced Installer
- InstallShield
- Wise (officially retired)

