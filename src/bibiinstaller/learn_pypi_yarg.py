from pathlib import Path
from pprint import pprint

import yarg
from yarg import HTTPError, json2package

pypi_server = 'https://pypi.python.org/pypi/'
# pypi_server = 'https://pypi.tuna.tsinghua.edu.cn/pypi/'
# pypi_server = 'http://mirrors.cloud.tencent.com/pypi/'
# name = 'yarg'
# version = '0.1.9'
name = 'requests_download'
version = '0.1.2'
import requests


# from .exceptions import HTTPError
# from .package import json2package

def get(package_name, pypi_server="https://pypi.python.org/pypi/"):
    """
    Constructs a request to the PyPI server and returns a
    :class:`yarg.package.Package`.

    :param package_name: case sensitive name of the package on the PyPI server.
    :param pypi_server: (option) URL to the PyPI server.

        >>> import yarg
        >>> package = yarg.get('yarg')
        <Package yarg>
    """
    if not pypi_server.endswith("/"):
        pypi_server = pypi_server + "/"
    # response = requests.get("{0}{1}/json".format(pypi_server,
    #                                              package_name))
    response = requests.get("{0}json/{1}".format(pypi_server,
                                                 package_name))
    if response.status_code >= 300:
        raise HTTPError(status_code=response.status_code,
                        reason=response.reason)
    if hasattr(response.content, 'decode'):
        return json2package(response.content.decode())
    else:
        return json2package(response.content)


package = yarg.get(name.lower(), pypi_server=pypi_server)
# package = get(name, pypi_server=pypi_server)
pprint(package)
# package = yarg.get(name)
releases = package.release(version)
pprint(releases)

# def read_packages(package_txt_file):
#     if Path(package_txt_file).exists():
#         packages = [line.strip().split('#', 1)[0].strip() for line in
#                     open(package_txt_file, 'r', encoding='utf').readlines()]
#         packages = [package for package in packages if len(package) > 0]
#     else:
#         packages = []
#     return packages
#
#
# print(read_packages('package_configs/add_packages.txt'))
# print(read_packages('package_configs/editable_packages.txt'))
# print(read_packages('package_configs/extra_packages.txt'))
# print(read_packages('package_configs/skip_packages.txt'))
# print(read_packages('package_configs/unwanted_packages.txt'))

