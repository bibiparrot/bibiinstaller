import shutil
import subprocess
import sys
import os
from time import sleep

from loguru import logger

path = r'nsis-3.10-win'
os.environ["PATH"] += os.pathsep + path


def subprocess_run(args, exit=True, timeout=5):
    """
    Wrapper-function around subprocess.run.

    When the sub-process exits with a non-zero return code,
    prints out a message and exits with the same code.
    """
    logger.info(f'$ {" ".join([str(x) for x in args])}')
    cp = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    logger.info(cp.stdout)
    try:
        cp.check_returncode()
    except subprocess.CalledProcessError as exc:
        logger.warning(exc)
        logger.debug(cp.stderr)
        if exit:
            sys.exit(cp.returncode)
    return cp.returncode


def run_entrypoint(python_env, entrypoint):
    entrypoint_package, _, entrypoint_function = entrypoint.partition(':')
    python_command = f'from {entrypoint_package} import {entrypoint_function}; {entrypoint_function}()'
    args = [python_env, '-c', python_command]
    logger.info(f'$ {" ".join([str(x) for x in args])}')
    returncode = subprocess_run(args, exit=False)
    return returncode


def check_entrypoint(python_env, entrypoint: str, max_execution_time: int = 2):
    entrypoint_package, _, entrypoint_function = entrypoint.partition(':')
    python_command = f'from {entrypoint_package} import {entrypoint_function}; {entrypoint_function}()'
    args = [python_env, '-c', python_command]

    logger.info(f'$ {" ".join([str(x) for x in args])}')
    try:
        cp = subprocess.run(args, capture_output=True, text=True, timeout=max_execution_time,
                            creationflags=subprocess.CREATE_NO_WINDOW)
        logger.info(f'returncode = {cp.returncode}, stdout = {cp.stdout}, stderr = {cp.stderr}')
        if cp.returncode != 0:
            sys.exit(F"FAILED,  entrypoint [{entrypoint}] error: {cp.stderr}.")
        else:
            logger.info(f'PASSED, entrypoint [{entrypoint}] output: {cp.stdout}.')
            return True
    except subprocess.TimeoutExpired:
        logger.info(f'PASSED, overtime {max_execution_time}s and killed.')
        return True


python = r'E:/Pythons/bibipdf/.venv/Scripts/python.exe'
entrypoint = 'bibipdf.main:main'

check_entrypoint(python, entrypoint)

# subprocess_run([
#     python, '-c', 'import shutil; print(shutil.which("makensis"))'
# ])
