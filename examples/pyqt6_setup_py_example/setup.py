from setuptools import Extension, find_packages, setup

'''
https://docs.python.org/3.11/distutils/setupscript.html
https://pythonforthelab.com/blog/how-create-setup-file-your-project/
https://setuptools.pypa.io/en/latest/userguide/entry_point.html
'''

setup(
    name='pyqt6_example',
    version='0.1.0',
    url='',
    license='GPL v3',
    author='Chunqi Shi',
    author_email='chunqishi@gmail.com',
    description='pyqt6 example',
    package_dir={'': 'src'},
    packages=find_packages(
        where='src',  # '.' by default
        include=['pyqt6_example'],  # ['*'] by default
        exclude=[],  # empty by default
    ),
    install_requires=[
        "PyQt6>=6.6.1"
    ],
    entry_points={
        'gui_scripts': [
            'pyqt6_example = pyqt6_example.pyqt6_example_burning_widget:main',
        ]
    },
)
