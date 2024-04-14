import shutil
import subprocess
import sys
import os

from loguru import logger

path = r'nsis-3.10-win'
os.environ["PATH"] += os.pathsep + path


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


python = r'..\..\examples\pyqt6_setup_py_example\bibiinstaller-pynsist-20240413\packaging-venv\Scripts\python.exe'

subprocess_run([
    python, '-c', 'import shutil; print(shutil.which("makensis"))'
])
