# -*- coding: utf-8 -*-
#
# Copyright © 2024 Chunqi SHI.
# Licensed under the terms of the GPL-3.0 License
#
# Copyright © 2020 Spyder Project Contributors.
# Licensed under the terms of the GPL-3.0 License
#
"""
Script to create a Windows installer using pynsist.

Based on the pynsist
https://pynsist.readthedocs.io/en/latest/

Based on the spyder's installer.py script
https://github.com/spyder-ide/spyder/blob/5.x/installers/Windows/installer.py

Reference:
https://github.com/takluyver/pynsist/blob/master/examples/pyqt5/installer.cfg

"""
import importlib
# from pip._vendor import tomli
import importlib.util as iutil
import os
import re
import shelve
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass, fields, field
from pathlib import Path
from pprint import pformat

import requests
from bibiflags import BibiFlags
from loguru import logger

# from bibiflags. import BibiFlags

# URL to download assets that the installer needs and that will be put on
# the assets directory when building the installer

# ASSETS_URL = os.environ.get(
#     'ASSETS_URL',
#     'https://github.com/spyder-ide/windows-installer-assets/'
#     'releases/latest/download/assets.zip')
#
# ASSETS_URL = os.environ.get(
#     'ASSETS_URL',
#     'https://github.com/spyder-ide/windows-installer-assets/'
#     'releases/latest/download/assets.zip')

# The pynsist configuration file template that will be used. Of note,
# with regards to pynsist dependency collection and preparation:
# - {pypi_wheels} will be downloaded by pynsist from PyPI.
# - {packages} will be copied by pynsist from the current Python env.
#
#

PYPI_SERVER_LOCAL_CACHE = 'pypi_server.local_cache.shelve'

PYNSIST_CFG_TEMPLATE = """
# see: https://pynsist.readthedocs.io/en/latest/cfgfile.html
[Application]
name={name}
version={version}
entry_point={entrypoint}
icon={icon_file}
publisher={publisher}
license_file={license_file}

[Python]
version={python_version}
bitness={bitness}
format=bundled

[Include]
pypi_wheels=
    {pypi_wheels}
extra_wheel_sources=
    {extra_wheel_sources}
packages=
    {packages}
files={package_dist_info} > $INSTDIR/pkgs
    {package_exe}
    
[Build]
installer_name={installer_name}
nsi_template={template}
"""
try:
    SRC_HOME = Path(__file__).parent.parent
except NameError:
    SRC_HOME = Path('.').parent.parent

ASSETS_HOME = SRC_HOME / 'assets'


@dataclass
class BibiinstallConfigs:
    # '''
    # PROJECTS
    # '''
    PACKAGE_NAME: str = ''
    PYTHON_VERSION: str = ''
    BITNESS: int = 64
    ICON_PATH: str = ''
    ENTRYPOINT: str = ''
    LICENSE_TXT_PATH: str = 'license.txt'

    # '''
    # PACKAGES
    # '''
    EXTRA_REQUIREMENTS_TXT_PATH: str = ''
    EXTRA_PACKAGES: list = field(default_factory=list)
    EDITABLE_PACKAGES: list = field(default_factory=list)
    UNWANTED_PACKAGES: list = field(default_factory=list)

    # '''
    # FILES
    # '''
    FILE_CONFIGS: list = field(default_factory=list)
    ASSETS_PATH: str = ''

    @staticmethod
    def verify(configs: dict):
        variable_names = [fld.name for fld in fields(BibiinstallConfigs)]
        unsetting_variables = []
        for variable in variable_names:
            value = configs.get(variable, "")
            if isinstance(value, str):
                value = value.strip()
                if not value or len(value) == 0:
                    unsetting_variables.append(variable)
            if isinstance(value, list):
                if not value or len(value) == 0:
                    unsetting_variables.append(variable)

        logger.info(f'NOT SETTING: {pformat(unsetting_variables)}')

    @staticmethod
    def from_configs(configs: dict):
        return from_dict_to_dataclass(BibiinstallConfigs, configs)


def from_dict_to_dataclass(cls, data: dict):
    import inspect
    return cls(
        **{
            key: (data[key] if val.default == val.empty else data.get(key, val.default))
            for key, val in inspect.signature(cls).parameters.items()
        }
    )


def subprocess_run(args):
    """
    Wrapper-function around subprocess.run.

    When the sub-process exits with a non-zero return code,
    prints out a message and exits with the same code.
    """
    logger.info(f'$ {" ".join([str(x) for x in args])}')
    cp = subprocess.run(args, capture_output=True, text=True)
    logger.info(cp.stdout)
    try:
        cp.check_returncode()
    except subprocess.CalledProcessError as exc:
        logger.warning(exc)
        logger.debug(cp.stderr)
        sys.exit(cp.returncode)


def create_python_env(target_directory, python_version: str, environment_name: str = None):
    micromamba_path = ASSETS_HOME / 'Windows' / 'micromamba'
    logger.debug(f"micromamba_path = [{micromamba_path}]")
    micromamba_exes = list(micromamba_path.glob('*.exe'))
    if len(micromamba_exes) < 1:
        logger.warning(f'NO micromamba.exe under [{micromamba_path}]')
    micromamba_exe = sorted(micromamba_exes, key=lambda file: Path(file).lstat().st_mtime, reverse=True)[0].resolve()
    logger.debug(micromamba_exe)
    python = '.'.join(python_version.split('.')[:2])

    logger.info(f'micromamba [{micromamba_exe}]')
    conda_path = Path(target_directory) / f'conda_python_{python}'
    if environment_name is None:
        environment_name = f'python_{python}'

    python_exe = conda_path / 'envs' / environment_name / 'python.exe'
    if not python_exe.exists():
        subprocess_run([
            micromamba_exe, 'create', '--yes', '-n', environment_name, f'python={python}',
            '-c', 'conda-forge', '--root-prefix', conda_path
        ])
    return python_exe.resolve()


def create_packaging_venv(
        target_directory, python_version, venv_name,
        conda_path=None):
    """
    Create a Python virtual environment in the target_directory.

    Returns the path to the newly created environment's Python executable.
    """
    fullpath = os.path.join(target_directory, venv_name)
    if conda_path and Path(conda_path).exists():
        logger.info(f'USE Conda: {conda_path}')
        command = [conda_path, "create",
                   "-p", os.path.normpath(fullpath),
                   "python={}".format(python_version), "-y"]
        env_path = os.path.join(fullpath, "python.exe")
    else:
        python_exe = create_python_env(target_directory, python_version)
        # logger.info(f'USE Python: {sys.executable}')
        # command = [sys.executable, "-m", "venv", fullpath]
        logger.info(f'USE Python: {python_exe}')
        command = [python_exe, "-m", "venv", fullpath]
        env_path = os.path.join(fullpath, "Scripts", "python.exe")
    logger.info(command)
    subprocess_run(command)
    logger.info(f'VENV Python: {env_path}')
    return env_path


def pip_freeze(python, encoding):
    """
    Return the "pip freeze --all" output as a list of strings.
    """
    logger.info("Getting frozen requirements.")
    output = subprocess.check_output([python, "-m", "pip", "freeze", "--all"])
    text = output.decode(encoding)
    return text.splitlines()


def about_dict(repo_root, package):
    """
    Return the package about dict.

    keys are the __variables__ in <package>/__init__.py.
    """
    package_init = os.path.join(repo_root, package, "__init__.py")
    spec = iutil.spec_from_file_location("package", package_init)
    package = iutil.module_from_spec(spec)
    spec.loader.exec_module(package)

    return package.__dict__


def get_cached_package(name, pypi_server, root=None):
    import yarg
    root = Path('.')
    if root is None:
        root = Path(__file__).parent

    shelve_file = root / PYPI_SERVER_LOCAL_CACHE
    with shelve.open(str(shelve_file.resolve())) as shelve_cache:
        if name in shelve_cache:
            logger.info(f'Cached [{name}]')
            return shelve_cache[name]
        if pypi_server is None:
            yarg_package = yarg.get(name.lower())
        else:
            yarg_package = yarg.get(name.lower(), pypi_server=pypi_server)
        shelve_cache[name] = yarg_package
        return yarg_package


def pip_wheels_in(work_dir, python, requirements, skip_packages):
    '''
    https://packaging.pypa.io/en/stable/utils.html
    https://pip.pypa.io/en/stable/cli/pip_download/

    '''
    from packaging.utils import parse_wheel_filename, canonicalize_name, canonicalize_version
    pip_download = (Path(work_dir) / f"pip_download_only_binaries").resolve()
    logger.info(f'make pip download dir: [{pip_download}]')
    pip_download.mkdir(parents=True, exist_ok=True)
    package_names = []
    for requirement in requirements:
        name, _, version = requirement.partition("==")
        # Needed to detect the package being installed from source
        # <package> @ <path to package>==<version>
        name = name.split('@')[0].strip()
        package_names.append(f"{canonicalize_name(name)}=={canonicalize_version(version, strip_trailing_zero=False)}")
        if name in skip_packages:
            logger.info(f"- {requirement} skipped")
        else:
            subprocess_run([python, "-m", "pip", "download", "--only-binary", ":all:", "--dest",
                            pip_download, requirement])
    whl_files = pip_download.glob("*.whl")

    canonicalize_wheels = []
    for whl_file in whl_files:
        name, ver, build, tags = parse_wheel_filename(whl_file.name)
        logger.info(f"{name} {ver} {build} {tags} [{whl_file}]")
        canonicalize_wheels.append(f"{name}=={canonicalize_version(ver, strip_trailing_zero=False)}")
    wheels = []
    for i, package_name in enumerate(package_names):
        if package_name in canonicalize_wheels:
            wheels.append(requirements[i])
        else:
            logger.warning(f'{requirements[i]} {package_name}')
    return wheels, pip_download


def pypi_wheels_in(requirements, skip_packages, pypi_server=None):
    """
    Return a list of the entries in requirements (distributed as wheels).

    Where requirements is a list of strings formatted like "name==version".

    pypi_server can use mirrors, such as https://pypi.tuna.tsinghua.edu.cn/pypi/
    """
    logger.info("Checking for wheel availability at PyPI.")
    wheels = []
    for requirement in requirements:
        name, _, version = requirement.partition("==")
        # Needed to detect the package being installed from source
        # <package> @ <path to package>==<version>
        name = name.split('@')[0].strip()
        if name in skip_packages:
            logger.info(f"- {requirement} skipped")
        else:
            yarg_package = get_cached_package(name, pypi_server)
            logger.info(yarg_package)
            releases = yarg_package.release(version)
            logger.info(releases)
            if not releases:
                raise RuntimeError(
                    "ABORTING: Did not find {!r} at PyPI. "
                    "(bad meta-data?)".format(
                        requirement
                    )
                )
            if any(r.package_type == "wheel" for r in releases):
                wheels.append(requirement)
                feedback = "ok"
            else:
                feedback = "missing"
            logger.info(f"- {requirement} {feedback}")
    return wheels


def parse_package_name(requirement):
    """
    Return the name component of a `name==version` formatted requirement.
    """
    requirement_name = requirement.partition("==")[0].split("@")[0].strip()
    return requirement_name


def packages_from(requirements, wheels, skip_packages, add_packages):
    """
    Return a list of the entries in requirements that aren't found in wheels.

    Both assumed to be lists/iterables of strings formatted like
    "name==version".
    """
    requirements = [parse_package_name(p) for p in requirements]
    wheels = [parse_package_name(p) for p in wheels]
    skip_packages = [parse_package_name(p) for p in skip_packages]
    add_packages = [parse_package_name(p) for p in add_packages]
    packages = set(requirements) - set(wheels) - set(skip_packages)
    packages = packages | set(add_packages)
    return list(packages)


def update_application_nsi(template_nsi_file, application_nsi_file,
                           app_name: str, window_title: str = None, app_name_lower: str = None):
    def substitute(template_path: str, key_val_maps: dict):
        from string import Template
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
    return Path(application_nsi_file).resolve()


def create_pynsist_cfg(
        work_dir,
        python,
        python_version,
        bitness,
        package_name,
        package_version,
        package_author,
        package_dist_info,
        entrypoint,
        package,
        unwanted_packages,
        skip_packages,
        add_packages,
        icon_file,
        license_file,
        pynsist_config_file,
        encoding="latin1",
        extras=None,
        suffix=None,
        nsi_template_path=None,
        pypi_server=None
):
    """
    Create a pynsist configuration file from the PYNSIST_CFG_TEMPLATE.

    Determines dependencies by running pip freeze,
    which are then split between those distributed as PyPI wheels and
    others. Returns the name of the resulting installer executable, as
    set into the pynsist configuration file.
    """

    requirements = [
        # Those from pip freeze except the package itself and packages local
        # installed (by passing a directory path or with the editable flag).
        # To add such packages the ADD_PACKAGES should include the import names
        # of the packages.
        line
        for line in pip_freeze(python, encoding=encoding)
        if parse_package_name(line) != package and \
           parse_package_name(line) not in unwanted_packages and \
           '-e git' not in line
    ]
    skip_wheels = [package] + skip_packages
    # wheels = pypi_wheels_in(requirements, skip_wheels, pypi_server)
    wheels, pip_download = pip_wheels_in(work_dir, python, requirements, skip_packages)
    more_skip_packages = [package] + skip_packages
    packages = packages_from(requirements, wheels, more_skip_packages, add_packages)
    logger.info(f'requirements={requirements}')
    logger.info(f'skip_packages={skip_packages}')
    logger.info(f'skip_wheels={skip_wheels}')
    logger.info(f'wheels={wheels}')
    logger.info(f'more_skip_packages={more_skip_packages}')
    logger.info(f'add_packages={add_packages}')
    logger.info(f'packages={packages}')

    if suffix:
        installer_name = "{}_{}bit_{}.exe"
    else:
        installer_name = "{}_{}bit{}.exe"

    if not suffix:
        suffix = ""

    # fill extra_wheel_sources
    # SEE: https://pynsist.readthedocs.io/en/latest/
    extra_wheel_sources = [str(pip_download)]

    installer_exe = installer_name.format(package_name, bitness, suffix)
    changed_icon_exe = change_exe_icon(work_dir, package_name, icon_file)

    pynsist_cfg_payload = PYNSIST_CFG_TEMPLATE.format(
        name=package_name,
        version=package_version,
        entrypoint=entrypoint,
        icon_file=icon_file,
        license_file=license_file,
        python_version=python_version,
        publisher=package_author,
        bitness=bitness,
        pypi_wheels="\n    ".join(wheels),
        extra_wheel_sources="\n    ".join(extra_wheel_sources),
        packages="\n    ".join(packages),
        installer_name=installer_exe,
        template=nsi_template_path,
        package_dist_info=package_dist_info,
        package_exe=str(changed_icon_exe)
    )

    logger.info(f"pynsist_cfg_payload:\n{pynsist_cfg_payload}")
    with open(pynsist_config_file, "wt", encoding=encoding) as f:
        f.write(pynsist_cfg_payload)
    logger.info(f"Wrote pynsist configuration file [{pynsist_config_file}]")
    logger.info("Contents:")
    logger.info(pformat(pynsist_cfg_payload))
    logger.info("End of pynsist configuration file.")
    return installer_exe


def download_file(url, target_directory):
    """
        download the URL to the target_directory and return the filename.
    """
    local_filename = os.path.join(target_directory, url.split("/")[-1])
    import requests
    r = requests.get(url, stream=True)
    with open(local_filename, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)
    return local_filename


def unzip_file(filename, target_directory):
    """
        given a filename, unzip it into the given target_directory.
    """
    with zipfile.ZipFile(filename) as z:
        z.extractall(target_directory)


def make_work_dir(root: str = None):
    if root is None:
        root = '.'
    import datetime
    work_dir = Path(root) / f"bibiinstaller-pynsist-{datetime.datetime.now().strftime('%Y%m%d')}"
    logger.info(f'make work dir under: [{root}]')
    work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir.resolve()


def copy_assets(assets_dir, work_dir):
    # NOTE: SHOULD BE TEMPORAL (until jedi has the fix available).
    # See the 'files' section on the pynsist template config too.
    logger.info("Copying patched CompiledSubprocess __main__.py for jedi")
    shutil.copy(
        "installers/Windows/assets/jedi/__main__.py",
        os.path.join(work_dir, "__main__.py"))

    logger.info("Copying patched __init__.py for Pylint")
    shutil.copy(
        "installers/Windows/assets/pylint/__init__.py",
        os.path.join(work_dir, "__init__.py"))

    logger.info("Copying required assets for Tkinter to work")
    shutil.copytree(
        "installers/Windows/assets/tkinter/lib",
        os.path.join(work_dir, "lib"),
        dirs_exist_ok=True)
    shutil.copytree(
        "installers/Windows/assets/tkinter/pynsist_pkgs",
        os.path.join(work_dir, "pynsist_pkgs"),
        dirs_exist_ok=True)

    logger.info("Copying NSIS plugins into discoverable path")
    contents = os.listdir(
        "installers/Windows/assets/nsist/plugins/x86-unicode/")
    logger.info('contents', contents)
    # for element in contents:
    #    shutil.copy(
    #        os.path.join(
    #            "installers/Windows/assets/nsist/plugins/x86-unicode/",
    #            element),
    #        os.path.join(
    #            "C:/Program Files (x86)/NSIS/Plugins/x86-unicode/",
    #            element))


def copy_assets():
    # NSIS --> C:/Program Files (x86)/NSIS/
    # pynsist_pkgs --> work_dir/pynsist_pkgs, same directory of pynsist.cfg
    #
    pass


def png_to_icon(png_file, icon_file):
    '''
    pip install pillow.
    '''
    from PIL import Image
    logo = Image.open(png_file)
    logo.save(icon_file, format='ICO')
    logger.info(f"CONVERT [{png_file}] to [{icon_file}]")


def read_setup_py_info(file_path):
    setup_content = Path(file_path).read_text(encoding='utf8')
    pattern = r'(\w+)\s*=\s*(?:\'([^\']*)\'|\"([^\"]*)\")'

    setup_info = {}
    for match in re.finditer(pattern, setup_content):
        key = match.group(1)
        value = match.group(2) or match.group(3)
        setup_info[key] = value

    return setup_info


def read_pyproject_toml_info(file_path):
    import tomli
    with open(file_path, "rb") as f:
        pyproject_info = tomli.load(f)
        return pyproject_info


def read_packages(package_txt_file):
    if package_txt_file and Path(package_txt_file).exists():
        packages = [line.strip().split('#', 1)[0].strip() for line in
                    open(package_txt_file, 'r', encoding='utf').readlines()]
        packages = [package for package in packages if len(package) > 0]
    else:
        logger.warning(f'NOT EXIST: [{package_txt_file}]')
        packages = []
    return packages


def prepare_windows_assets(download_assets: bool, ASSETS_URL: str):
    if download_assets:
        logger.info(f"Setting up assets from {ASSETS_URL}")
        logger.info(f"Downloading assets from {ASSETS_URL}")
        # filename = download_file(ASSETS_URL, 'installers/Windows/assets')

        logger.info("Unzipping assets to [installers/Windows/assets]")
        # unzip_file(filename, 'installers/Windows/assets')
        unzip_file(r'E:\spyder_install\assets.zip', 'installers/Windows/assets')


def run_installer(python_version,
                  bitness,
                  entrypoint,
                  package,
                  icon_path,
                  license_path,
                  pynsist_version=2.8,
                  project_root=None,
                  extra_packages_txtfile=None,
                  editable_package_txtfile=None,
                  unwanted_packages_txtfile=None,
                  skip_packages_txtfile=None,
                  add_packages_txtfile=None,
                  conda_path=None,
                  suffix=None,
                  nsi_template_path=None,
                  pypi_server=None):
    """
    Run the installer generation.

    Given a certain python version, bitness, package repository root directory,
    package name, icon path and license path a pynsist configuration file
    (locking the dependencies set in setup.py) is generated and pynsist runned.
    """
    try:

        work_dir = make_work_dir(project_root)
        logger.info(f"Temporary working directory at [{work_dir}]")

        # TODO: ...
        # copy_assets(assets_dir, work_dir)

        packaging_venv_dir = 'packaging-venv'

        logger.info("Copying template into discoverable path for Pynsist")
        logger.info(f'Pynsist template: [{nsi_template_path}]')
        if nsi_template_path:
            template_basename = os.path.basename(nsi_template_path)
            template_new_path = os.path.normpath(
                os.path.join(
                    work_dir,
                    f"{packaging_venv_dir}/Lib/site-packages/nsist"))
            os.makedirs(template_new_path, exist_ok=True)

            update_application_nsi(
                nsi_template_path,
                os.path.join(template_new_path, template_basename),
                app_name=package
            )
            nsi_template_path = template_basename

        logger.info(f"Creating the package virtual environment. [{Path(work_dir) / packaging_venv_dir}]")
        env_python = create_packaging_venv(
            work_dir, python_version,
            conda_path=conda_path,
            venv_name=packaging_venv_dir)

        logger.info(f"Updating pip in the virtual environment [{env_python}]")
        subprocess_run(
            [env_python, "-m", "pip", "install", "--upgrade", "pip",
             "--no-warn-script-location"]
        )

        logger.info(f"Updating setuptools in the virtual environment [{env_python}]")
        subprocess_run(
            [env_python, "-m", "pip", "install", "--upgrade",
             "--force-reinstall", "setuptools",
             "--no-warn-script-location"]
        )

        logger.info(f"Updating/installing wheel in the virtual environment [{env_python}]")
        subprocess_run(
            [env_python, "-m", "pip", "install", "--upgrade", "wheel",
             "--no-warn-script-location"]
        )

        logger.info(f"Installing package under [{project_root}]")
        subprocess_run([env_python, "-m",
                        "pip", "install", project_root,
                        "--no-warn-script-location"])

        if (Path(project_root) / 'setup.py').exists():
            setup_info = read_setup_py_info(Path(project_root) / 'setup.py')
            logger.debug(setup_info)
            package_name = setup_info['name']
            package_version = setup_info['version']
            package_author = setup_info['author']
        elif (Path(project_root) / 'pyproject.toml').exists():
            pyproject_info = read_pyproject_toml_info(Path(project_root) / 'pyproject.toml')
            logger.debug(pyproject_info)
            package_name = pyproject_info['project']['name']
            package_version = pyproject_info['project']['version']
            package_author = pyproject_info['project']['authors'][0]['name']
        else:
            logger.warning(f"ERROR: {Path(project_root) / 'setup.py'} or {Path(project_root) / 'pyproject.toml'}")
            package_name = package
            package_version = "0.1.0"
            package_author = ""

        package_dist_info = f"{package_name}-{package_version}.dist-info"

        logger.info(f"Copy package .dist-info into the pynsist future build directory [{package_dist_info}]")
        shutil.copytree(
            os.path.join(work_dir, f"{packaging_venv_dir}/Lib/site-packages", package_dist_info),
            os.path.join(work_dir, package_dist_info),
            dirs_exist_ok=True
        )

        logger.info(f"Installing extra packages: [{extra_packages_txtfile}]")
        if extra_packages_txtfile and Path(extra_packages_txtfile).exists():
            subprocess_run([env_python, "-m", "pip", "install", "-r",
                            extra_packages_txtfile, "--no-warn-script-location"])
        else:
            logger.warning(f'NOT EXIST extra packages: [{extra_packages_txtfile}]')

        logger.info(f"Installing packages with the --editable flag: [{editable_package_txtfile}]")
        editable_packages = read_packages(editable_package_txtfile)
        logger.info(f"extra_packages : {pformat(editable_packages)}")
        for e_package in editable_packages:
            subprocess_run([env_python, "-m", "pip", "install", "-e",
                            e_package, "--no-warn-script-location"])

        pynsist_cfg = os.path.join(work_dir, "pynsist.cfg")
        logger.info(f"Creating pynsist configuration file [{pynsist_cfg}]")

        logger.info("Read unwanted_packages, skip_packages, and add_packages")

        logger.info(f"unwanted_packages: [{unwanted_packages_txtfile}]")
        unwanted_packages = read_packages(unwanted_packages_txtfile)

        logger.info(f"skip_packages: [{skip_packages_txtfile}]")
        skip_packages = read_packages(skip_packages_txtfile)

        logger.info(f"add_packages: [{add_packages_txtfile}]")
        add_packages = read_packages(add_packages_txtfile)

        logger.info(f"unwanted_packages = {unwanted_packages}")
        logger.info(f"skip_packages = {skip_packages}")
        logger.info(f"add_packages = {add_packages}")

        python_version_embed = find_python_embed_amd64_versions(python_version)
        logger.info(f"python_version_embed = {python_version_embed}, python_version={python_version}")

        installer_exe = create_pynsist_cfg(
            work_dir, env_python, python_version_embed, bitness,
            package_name, package_version, package_author, package_dist_info,
            entrypoint=entrypoint,
            package=package,
            unwanted_packages=unwanted_packages,
            skip_packages=skip_packages,
            add_packages=add_packages,
            icon_file=icon_path, license_file=license_path, pynsist_config_file=pynsist_cfg,
            extras=extra_packages_txtfile,
            suffix=suffix, nsi_template_path=nsi_template_path, pypi_server=pypi_server)

        logger.info("Installing pynsist.")
        subprocess_run([env_python, "-m", "pip", "install", f"pynsist=={pynsist_version}",
                        "--no-warn-script-location"])

        logger.info("Running pynsist.")
        subprocess_run([env_python, "-m", "nsist", pynsist_cfg])

        destination_dir = os.path.join(project_root, "dist")
        logger.info(f"Copying installer file to [{destination_dir}]")
        os.makedirs(destination_dir, exist_ok=True)
        shutil.copy(
            os.path.join(work_dir, "build", "nsis", installer_exe),
            destination_dir,
        )
        logger.info("Installer created!")
    except PermissionError as pe:
        logger.info(f"PermissionError {pe}")
        pass


def get_absolute_path(root, file):
    if file is not None:
        return (Path(root) / file).resolve()


def url_exist(url):
    try:
        response = requests.head(url)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        return False


def find_python_embed_amd64_versions(python_version):
    pattern = r'(\d+)\.(\d+)\.(\d+)'
    match = re.match(pattern, python_version)
    major_version = int(match.group(1))
    minor_version = int(match.group(2))
    micro_version = int(match.group(3))
    micro_versions = sorted(list(range(20)), key=lambda num: abs(num - micro_version))
    versions = [f"{major_version}.{minor_version}.{micro_version}" for micro_version in micro_versions]
    for version in versions:
        url = f'https://www.python.org/ftp/python/{version}/python-{version}-embed-amd64.zip'
        if url_exist(url):
            return version
    return python_version


def lazy_import(file_path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    loader = importlib.util.LazyLoader(spec.loader)
    spec.loader = loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    loader.exec_module(module)
    return module


def get_config_variables(python_file_path, module_name):
    configs_py = lazy_import(python_file_path, module_name)
    names = [name for name in dir(configs_py) if not name.startswith('__')]
    values = [getattr(configs_py, name) for name in names]
    return dict(zip(names, values))


def change_exe_icon(work_dir, package_name, icon_file):
    '''
    ResourceHacker.exe -open bibiinstaller_app.exe -save app.exe -action addskip -res bibiinstaller.ico -mask ICONGROUP,MAINICON
    '''
    windows_assets_dir = (Path(work_dir) / f"windows_assets").resolve()
    changed_icon_exe = windows_assets_dir / f'{package_name}.exe'
    resource_hacker = ASSETS_HOME / 'Windows' / 'icon_configs' / 'ResourceHacker.exe'
    bibiinstaller_app = ASSETS_HOME / 'Windows' / 'exes' / 'bibiinstaller_app.exe'
    subprocess_run([
        resource_hacker, '-open', bibiinstaller_app, '-save', changed_icon_exe,
        '-action', 'addskip', '-res', icon_file, '-mask', 'ICONGROUP,MAINICON'
    ])

    return changed_icon_exe


def prepare_nsis_plugins(work_dir):
    windows_assets_dir = (Path(work_dir) / f"windows_assets").resolve()
    nsis_dir = ASSETS_HOME / 'Windows' / 'nsis'
    nsis_zip = nsis_dir / 'nsis-3.10-win.zip'
    nsis_plugins_dir = nsis_dir / 'Plugins'
    unzip_file(nsis_zip, windows_assets_dir)
    work_nsis_dir = windows_assets_dir / 'nsis-3.10-win'
    shutil.copytree(nsis_plugins_dir, work_nsis_dir / 'Plugins', dirs_exist_ok=True)
    return nsis_plugins_dir.resolve()


def main():
    config_root = Path(__file__).parent
    import argparse
    parser = argparse.ArgumentParser(
        prog='bibiinstaller',
        description='python installer package named bibi.')
    parser.add_argument('configs.py')
    flags = BibiFlags(app_name='bibiinstaller_windows',
                      argparser=parser,
                      root=str(config_root))
    logger.debug(pformat(flags.parameters, sort_dicts=False))

    configs_py_file = flags.parameters['configs.py']
    configs_py_vars = get_config_variables(configs_py_file, 'configs_py')
    logger.info(pformat(configs_py_vars, sort_dicts=False))

    BibiinstallConfigs.verify(configs_py_vars)
    configs = BibiinstallConfigs.from_configs(configs_py_vars)

    project_root = Path(configs_py_file).parent.resolve()
    project_root = get_absolute_path(Path.cwd(), flags.parameters.get('project_root') or project_root)

    python_version = flags.parameters.get('python_version') or configs.PYTHON_VERSION
    bitness = flags.parameters.get('bitness') or configs.BITNESS
    entrypoint = flags.parameters.get('entrypoint') or configs.ENTRYPOINT
    package = flags.parameters.get('package') or configs.PACKAGE_NAME

    pynsist_version = flags.parameters.get('pynsist_version')
    suffix = flags.parameters.get('suffix')
    pypi_server = flags.parameters.get('pypi_server')

    icon_path = get_absolute_path(project_root,
                                  flags.parameters.get('icon_path') or configs.ICON_PATH)

    if not str(icon_path).lower().endswith('ico'):
        icon_path_convert = str(icon_path) + '.icon'
        png_to_icon(icon_path, icon_path_convert)
        icon_path = Path(icon_path_convert).resolve()

    license_path = get_absolute_path(project_root,
                                     flags.parameters.get('license_txt_path') or configs.LICENSE_TXT_PATH)

    extra_packages_txtfile = get_absolute_path(project_root,
                                               flags.parameters.get('extra_packages'))
    editable_package_txtfile = get_absolute_path(project_root,
                                                 flags.parameters.get('editable_packages'))
    unwanted_packages_txtfile = get_absolute_path(project_root,
                                                  flags.parameters.get('unwanted_packages'))
    skip_packages_txtfile = get_absolute_path(project_root,
                                              flags.parameters.get('skip_packages'))
    add_packages_txtfile = get_absolute_path(project_root,
                                             flags.parameters.get('add_packages'))
    conda_path = get_absolute_path(project_root,
                                   flags.parameters.get('conda_path'))

    nsi_template_path = get_absolute_path(config_root, flags.parameters.get('nsi_template_path'))

    if (not (Path(project_root) / 'setup.py').exists()) and (not (Path(project_root) / 'pyproject.toml').exists()):
        sys.exit(f"Invalid project_root: [{project_root}], NO 'setup.py' or 'pyproject.toml' under it.")

    run_installer(
        python_version=python_version,
        bitness=bitness,
        entrypoint=entrypoint,
        package=package,
        pynsist_version=pynsist_version,

        icon_path=icon_path,
        license_path=license_path,
        project_root=project_root,
        extra_packages_txtfile=extra_packages_txtfile,
        editable_package_txtfile=editable_package_txtfile,
        unwanted_packages_txtfile=unwanted_packages_txtfile,
        skip_packages_txtfile=skip_packages_txtfile,
        add_packages_txtfile=add_packages_txtfile,
        conda_path=conda_path,
        suffix=suffix,
        nsi_template_path=nsi_template_path,
        pypi_server=pypi_server
    )


if __name__ == "__main__":
    main()
