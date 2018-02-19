from setuptools import setup, find_packages
from setuptools.command.install import install
from subprocess import check_output
from codecs import open
from os import path
import os

VERSION_MAJOR = "0"
VERSION_PSEUDO_MINOR = "8"
VERSION_DEFAULT_MICRO = "0"

here = path.abspath(path.dirname(__file__))

if os.environ.get('TRAVIS'):
    version_micro = os.environ['TRAVIS_BUILD_NUMBER']
else:
    version_micro = VERSION_DEFAULT_MICRO

bin_files= set([
        path.join('bin', i)
        for i in os.listdir(path.join(here, 'bin'))
        if not '.' in i])

# be sure about the access rights since this is security sensitive
for file in bin_files:
    os.chmod(file, 0o755)

# only automatically setuid when plash-pun is better reviewed
## This will implicitly change the access rights to setuid in dev
#os.chmod('bin/plash-pun', 0o4755)

setup(
    name='plash',
    version='{}.{}{}'.format(VERSION_MAJOR, VERSION_PSEUDO_MINOR, version_micro),
    description='Container build tool',
    url='https://github.com/ihucos/plash',
    packages=['plashlib'],
    data_files=[("/usr/local/bin", bin_files)],
)
