# -*- coding: utf-8 -*-
#
# Copyright © 2024 Chunqi SHI.
# Licensed under the terms of the GPL-3.0 License
#
# Copyright © 2020 Spyder Project Contributors.
# Licensed under the terms of the GPL-3.0 License
#
# Copyright © 2018 Nicholas H.Tollervey.
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Script to create a Windows installer using pynsist.


Based on the spyder's installer.py script
https://github.com/spyder-ide/spyder/blob/5.x/installers/Windows/installer.py

Based on the Mu's win_installer.py script
https://github.com/mu-editor/mu/blob/master/win_installer.py
"""

import argparse
import importlib.util as iutil
import os
import shelve
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile
from pprint import pformat

import yarg

from bibiflags import BibiFlags
from loguru import logger

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

PYPI_SERVER_LOCAL_CACHE = 'pypi_server.local_cache.shelve'

PYNSIST_CFG_TEMPLATE = """
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
# extra_wheel_sources=C:\\Users\\shi\\AppData\\Local\\pynsist\\pypi
pypi_wheels=
    {pypi_wheels}
packages=
    {packages}
files={package_dist_info} > $INSTDIR/pkgs
[Build]
installer_name={installer_name}
nsi_template={template}
"""


def subprocess_run(args):
    """
    Wrapper-function around subprocess.run.

    When the sub-process exits with a non-zero return code,
    prints out a message and exits with the same code.
    """
    cp = subprocess.run(args)
    try:
        cp.check_returncode()
    except subprocess.CalledProcessError as exc:
        logger.warning(exc)
        sys.exit(cp.returncode)


def create_packaging_env(
        target_directory, python_version, venv_name="packaging-env",
        conda_path=None):
    """
    Create a Python virtual environment in the target_directory.

    Returns the path to the newly created environment's Python executable.
    """
    fullpath = os.path.join(target_directory, venv_name)
    if conda_path and Path(conda_path).exists():
        logger.info(f'USE Conda: {conda_path}')
        command = [
            conda_path, "create",
            "-p", os.path.normpath(fullpath),
            "python={}".format(python_version),
            "-y"]
        env_path = os.path.join(fullpath, "python.exe")
    else:
        logger.info(f'USE Python: {sys.executable}')
        command = [sys.executable, "-m", "venv", fullpath]
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


def get_cached_package(name, pypi_server):
    shelve_file = Path(__file__).parent / PYPI_SERVER_LOCAL_CACHE
    with shelve.open(str(shelve_file.absolute())) as shelve_cache:
        if name in shelve_cache:
            logger.info(f'Cached [{name}]')
            return shelve_cache[name]
        if pypi_server is None:
            yarg_package = yarg.get(name.lower())
        else:
            yarg_package = yarg.get(name.lower(), pypi_server=pypi_server)
        shelve_cache[name] = yarg_package
        return yarg_package


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
            releases = yarg_package.release(version)
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
    packages = set(requirements) - set(wheels) - set(skip_packages)
    packages = packages | set(add_packages)
    return [parse_package_name(p) for p in packages]


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
    return Path(application_nsi_file).absolute()


def create_pynsist_cfg(
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
        template=None,
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
    wheels = pypi_wheels_in(requirements, skip_wheels, pypi_server)
    skip_packages = [package]
    packages = packages_from(requirements, wheels, skip_packages, add_packages)

    if suffix:
        installer_name = "{}_{}bit_{}.exe"
    else:
        installer_name = "{}_{}bit{}.exe"

    if not suffix:
        suffix = ""

    installer_exe = installer_name.format(package_name, bitness, suffix)

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
        packages="\n    ".join(packages),
        installer_name=installer_exe,
        template=template,
        package_dist_info=package_dist_info
    )
    with open(pynsist_config_file, "wt", encoding=encoding) as f:
        f.write(pynsist_cfg_payload)
    logger.info(f"Wrote pynsist configuration file [{pynsist_config_file}]")
    logger.info("Contents:")
    logger.info(pformat(pynsist_cfg_payload))
    logger.info("End of pynsist configuration file.")
    return installer_exe


def download_file(url, target_directory):
    """
    Download the URL to the target_directory and return the filename.
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
    Given a filename, unzip it into the given target_directory.
    """
    with zipfile.ZipFile(filename) as z:
        z.extractall(target_directory)


def make_work_dir():
    import datetime
    work_dir = Path(f"installer-bibiocr-pynsist-{datetime.datetime.now().strftime('%Y%m%d')}")
    work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir.absolute()


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

    logger.info("Copying micromamba assets")
    shutil.copy(
        "installers/Windows/assets/micromamba/micromamba.exe",
        os.path.join(work_dir, "micromamba.exe"))

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


def read_setup_info(file_path):
    setup_content = Path(file_path).read_text(encoding='utf8')
    pattern = r'(\w+)\s*=\s*(?:\'([^\']*)\'|\"([^\"]*)\")'

    setup_info = {}
    for match in re.finditer(pattern, setup_content):
        key = match.group(1)
        value = match.group(2) or match.group(3)
        setup_info[key] = value

    return setup_info


def read_packages(package_txt_file):
    if Path(package_txt_file).exists():
        packages = [line.strip().split('#', 1)[0].strip() for line in
                    open(package_txt_file, 'r', encoding='utf').readlines()]
        packages = [package for package in packages if len(package) > 0]
    else:
        logger.warning(f'NOT EXIST: [{package_txt_file}]')
        packages = []
    return packages


def run(python_version,
        bitness,
        setup_py_repo_root,
        entrypoint,
        package,
        icon_path,
        license_path,
        pynsist_version=2.7,
        extra_packages_txtfile=None,
        editable_package_txtfile=None,
        unwanted_packages_txtfile=None,
        skip_packages_txtfile=None,
        add_packages_txtfile=None,
        conda_path=None,
        suffix=None,
        nsi_template=None,
        pypi_server=None,
        download_assets=False):
    """
    Run the installer generation.

    Given a certain python version, bitness, package repository root directory,
    package name, icon path and license path a pynsist configuration file
    (locking the dependencies set in setup.py) is generated and pynsist runned.
    """
    try:
        if download_assets:
            logger.info(f"Setting up assets from {ASSETS_URL}")
            logger.info(f"Downloading assets from {ASSETS_URL}")
            # filename = download_file(ASSETS_URL, 'installers/Windows/assets')

            logger.info("Unzipping assets to [installers/Windows/assets]")
            # unzip_file(filename, 'installers/Windows/assets')
            unzip_file(r'E:\spyder_install\assets.zip', 'installers/Windows/assets')

        work_dir = make_work_dir()
        logger.info(f"Temporary working directory at [{work_dir}]")

        # TODO: ...
        # copy_assets(assets_dir, work_dir)

        packaging_venv_dir = 'packaging-env'

        logger.info("Copying template into discoverable path for Pynsist")
        logger.info(f'Pynsist template: [{nsi_template}]')
        if nsi_template:
            template_basename = os.path.basename(nsi_template)
            template_new_path = os.path.normpath(
                os.path.join(
                    work_dir,
                    f"{packaging_venv_dir}/Lib/site-packages/nsist"))
            os.makedirs(template_new_path, exist_ok=True)
            # shutil.copy(
            #     nsi_template,
            #     os.path.join(template_new_path, template_basename))
            update_application_nsi(
                nsi_template,
                os.path.join(template_new_path, template_basename),
                app_name=package
            )
            nsi_template = template_basename

        logger.info("Creating the package virtual environment.")
        env_python = create_packaging_env(
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

        logger.info(f"Installing package with [{env_python}]")
        subprocess_run([env_python, "-m",
                        "pip", "install", setup_py_repo_root,
                        "--no-warn-script-location"])

        logger.info("Copy package .dist-info into the pynsist future build directory")
        setup_info = read_setup_info(Path(setup_py_repo_root) / 'setup.py')
        package_name = setup_info['name']
        package_version = setup_info['version']
        package_author = setup_info['author']
        package_dist_info = f"{package_name}-{package_version}.dist-info"

        shutil.copytree(
            os.path.join(work_dir, f"{packaging_venv_dir}/Lib/site-packages", package_dist_info),
            os.path.join(work_dir, package_dist_info),
            dirs_exist_ok=True
        )

        logger.info("Installing extra packages.")
        if Path(extra_packages_txtfile).exists():
            subprocess_run([env_python, "-m", "pip", "install", "-r",
                            extra_packages_txtfile, "--no-warn-script-location"])
        else:
            logger.warning(f'NOT EXIST: [{extra_packages_txtfile}]')

        logger.info("Installing packages with the --editable flag")
        editable_packages = read_packages(editable_package_txtfile)
        logger.info(f"extra_packages : {pformat(editable_packages)}")
        for e_package in editable_packages:
            subprocess_run([env_python, "-m", "pip", "install", "-e",
                            e_package, "--no-warn-script-location"])

        pynsist_cfg = os.path.join(work_dir, "pynsist.cfg")
        logger.info(f"Creating pynsist configuration file [{pynsist_cfg}]")

        logger.info("Read unwanted_packages, skip_packages, and add_packages")

        unwanted_packages = read_packages(unwanted_packages_txtfile)
        skip_packages = read_packages(skip_packages_txtfile)
        add_packages = read_packages(add_packages_txtfile)

        installer_exe = create_pynsist_cfg(
            env_python, python_version, bitness,
            package_name, package_version, package_author, package_dist_info,
            entrypoint=entrypoint, package=package,
            unwanted_packages=unwanted_packages,
            skip_packages=skip_packages,
            add_packages=add_packages,
            icon_file=icon_path, license_file=license_path, pynsist_config_file=pynsist_cfg,
            extras=extra_packages_txtfile,
            suffix=suffix, template=nsi_template, pypi_server=pypi_server)

        logger.info("Installing pynsist.")
        subprocess_run([env_python, "-m", "pip", "install", f"pynsist=={pynsist_version}",
                        "--no-warn-script-location"])

        logger.info("Running pynsist.")
        subprocess_run([env_python, "-m", "nsist", pynsist_cfg])

        destination_dir = os.path.join(setup_py_repo_root, "dist")
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


if __name__ == "__main__":
    flags = BibiFlags()
    logger.info(pformat(flags.parameters))

    from operator import attrgetter, itemgetter

    (python_version, pynsist_version, bitness, setup_py_path,
     entrypoint, package, icon_path,
     license_path, extra_packages, editable_packages, unwanted_packages, skip_packages, add_packages,
     conda_path, suffix, template, pypi_server) = itemgetter(
        'python_version', 'pynsist_version', 'bitness', 'setup_py_path',
        'entrypoint', 'package', 'icon_path',
        'license_path', 'extra_packages', 'editable_packages', 'unwanted_packages', 'skip_packages', 'add_packages',
        'conda_path', 'suffix', 'template', 'pypi_server'
    )(flags.parameters)

    if not setup_py_path.endswith("setup.py"):
        sys.exit("Invalid path to setup.py:", setup_py_path)

    setup_py_repo_root = os.path.abspath(os.path.dirname(setup_py_path))
    icon_file = os.path.abspath(icon_path)
    license_file = os.path.abspath(license_path)
    if extra_packages:
        extra_packages = os.path.abspath(extra_packages)
    if template:
        template = os.path.abspath(template)
    #
    run(python_version, bitness, setup_py_repo_root, entrypoint,
        package, icon_file, license_file,
        pynsist_version=pynsist_version,
        extra_packages_txtfile=extra_packages,
        editable_package_txtfile=editable_packages,
        unwanted_packages_txtfile=unwanted_packages,
        skip_packages_txtfile=skip_packages,
        add_packages_txtfile=add_packages,
        conda_path=conda_path,
        suffix=suffix,
        nsi_template=template,
        pypi_server=pypi_server)
