import os

from setuptools import setup, find_packages


here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.md')) as f:
    README = f.read()

requires = [
    'requests'
]

greenhouse_require = [
    'python-dateutil'
]

pis_require = [
    'pyserial',
    'RPi.gpio'
]


setup(name='sgreen2_greenhouse',
      version='0.0',
      description='sgreen2_greenhouse',
      long_description=README,
      classifiers=[
          "Programming Language :: Python",
      ],
      author='Matthew Kuo',
      author_email='mjk0827@tamu.edu',
      url='',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      extras_require={
          'pis': pis_require,
          'greenhouse': greenhouse_require
      }
      )
