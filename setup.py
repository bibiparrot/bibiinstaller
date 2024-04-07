from setuptools import Extension, find_packages, setup

'''
https://docs.python.org/3.11/distutils/setupscript.html
https://pythonforthelab.com/blog/how-create-setup-file-your-project/
https://setuptools.pypa.io/en/latest/userguide/entry_point.html
'''

setup(
    name='bibiinstaller',
    version='0.1.0',
    url='',
    license='GPL v3',
    author='Chunqi Shi',
    author_email='chunqishi@gmail.com',
    description='Bibi Installer using pynsist',
    # packages=['bibiinstaller'],
    package_dir={'': 'src'},
    packages=find_packages(
        where='src',  # '.' by default
        include=['bibiinstaller'],  # ['*'] by default
        exclude=['assets'],  # empty by default
    ),
    install_requires=[
        # "loguru>=0.7.2",
        # "OmegaConf>=2.3.0",
        "PyQt6>=6.6.1"
    ],
    entry_points={
        'gui_scripts': [
            'bibiinstaller_demo = bibiinstaller.pyqt6_example_burning_widget:main',
        ]
    },
)
