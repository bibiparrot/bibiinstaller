from setuptools import Extension, find_packages, setup

'''
https://docs.python.org/3.11/distutils/setupscript.html
https://pythonforthelab.com/blog/how-create-setup-file-your-project/
'''

setup(
    name='bibiinstaller',
    version='0.1.0',
    packages=['bibiinstaller'],
    package_dir={'': 'src'},
    url='',
    license='GPL v3',
    author='Chunqi Shi',
    author_email='chunqishi@gmail.com',
    description='Bibi Installer using pynsist'
)
