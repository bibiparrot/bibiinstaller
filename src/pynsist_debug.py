import subprocess
import sys
from pprint import pformat

from loguru import logger


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


args = ['C:\\Users\\shi\\bibiinstaller-pynsist-20240410\\packaging-venv\\Scripts\\python.exe',
        '-m', 'nsist', 'C:\\Users\\shi\\bibiinstaller-pynsist-20240410\\pynsist.cfg']
args = [
    'E:\\Pythons\\bibiinstaller\\src\\bibiinstaller\\bibiinstaller-pynsist-20240410\\packaging-venv\\Scripts\\python.exe',
    '-m', 'nsist', 'E:\\Pythons\\bibiinstaller\\src\\bibiinstaller\\bibiinstaller-pynsist-20240410\\pynsist.cfg']

# subprocess.run(args, capture_output=True, text=True)
print(sys.path)
subprocess_run(args)

