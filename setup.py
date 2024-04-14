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
    package_dir={'': 'src'},
    packages=find_packages(
        where='src',  # '.' by default
        include=['*'],  # ['*'] by default
        exclude=[],  # empty by default
    ),
    install_requires=[
        "yarg>=0.1.9",
        "loguru>=0.7.2",
        "bibiflags>=0.1.5",
        "packaging>=24.0",
        "tomli>=2.0.1",
        "pillow>=10.3.0",
    ],
    entry_points={
        'console_scripts': [
            'bibiinstaller = bibiinstaller.bibiinstaller_windows:main',
        ]
    },
)
