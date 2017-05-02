#!/usr/bin/env python3

import argparse
import hashlib
import logging
import os
import platform
import shlex
import stat
import subprocess
import sys
import uuid
from collections import namedtuple
from os import environ, path
from os.path import expanduser
from urllib.parse import urlparse

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

home_directory = expanduser("~")


# make pyftpdlib silent
logging.basicConfig(level=logging.ERROR)


if platform.system() == 'Darwin':
    # host ip is always the same but must be set with
    # sudo ifconfig lo0 alias 10.200.10.1/24
    # before this programs works
    HOST_IP = environ.get('HOST_IP', '10.200.10.1')
else:
    HOST_IP = '127.0.0.1' # because of dockers --net=host


def rand():
    return str(uuid.uuid4()).split('-')[-1]

def hashstr(stri):
    return hashlib.sha1(stri).hexdigest()

def create_executable_file(fname, script):
    if os.path.exists(fname):
        raise SystemExit('File {} already exists - deal with this'.format(fname))

    with open(fname, 'w') as f:
        f.write(script)
    st = os.stat(fname)
    os.chmod(fname, st.st_mode | stat.S_IEXEC)

package_managers = {}
class PackageManagerMeta(type):
    def __new__(cls, clsname, superclasses, attributedict):
        cls = type.__new__(cls, clsname, superclasses, attributedict)
        for sp in superclasses:
            package_managers[cls.name] = cls
        return cls

class PackageManager(metaclass=PackageManagerMeta):
    pre_install = None

    def __init__(self, packages):
        self._packages = packages

    def __str__(self):
        cmds = []
        if self.pre_install:
            cmds.append(self.pre_install)
        for p in self._packages:
            cmds.append(self.install.format(p))
        return ' && '.join(cmds)


class Apt(PackageManager):
    name = 'apt'
    pre_install = 'apt-get update'
    install = 'apt-get install -y {}'

class Apk(PackageManager):
    name = 'apk'
    pre_install = 'apk update'
    install = 'apk add {}'

class Yum(PackageManager):
    name = 'yum'
    install = 'yum install -y {}'

class Pip(PackageManager):
    name = 'pip'
    install = 'pip install {}'

class Emerge(PackageManager):
    name = 'emerge'
    install = 'emerge {}'

class DockerBuildable:

    def get_image_name(self):
        h = hashstr('{}-{}'.format(
            self.get_base_image_name(), self.get_build_commands()).encode())
        return 'packy-{}'.format(h)

    def get_base_image_name(self):
        raise NotImplementedError('you lazy person')

    def get_build_commands(self):
        raise NotImplementedError('you lazy person')

    def image_exists(self, ref):
        # return False
        out = subprocess.check_output(
            ["docker", "images", "--quiet", "--filter",
             "reference={ref}".format(ref=ref)])
        return bool(out)
    
    def ensure_builded(self):
        if not self.image_exists(self.get_image_name()):
            self.build()

    def build(self):
        rand_name = rand()
        cmds = self.get_build_commands()
        new_image_name = self.get_image_name()
        # print('Building', cmds)

        exit = subprocess.Popen([
        'docker', 'run', '-ti', '--name', rand_name, self.get_base_image_name(), 'sh', '-cx', cmds]).wait()
        assert exit == 0

        # get cotnainer id
        container_id = subprocess.check_output(
        ['docker', 'ps', '--all', '--quiet', '--filter', 'name={}'.format(rand_name)])

        container_id, = container_id.splitlines()

        # create image out of the container
        from time import sleep
        sleep(0.2) # race condition in docker?
        exit = subprocess.Popen(['docker', 'commit', container_id, new_image_name]).wait()
        assert exit == 0

        # remove the container to save space
        exit = subprocess.Popen(['docker', 'rm', container_id]).wait()
        assert exit == 0



operating_systems = {}
class OSMeta(type):
    def __new__(cls, clsname, superclasses, attributedict):
        cls = type.__new__(cls, clsname, superclasses, attributedict)
        for sp in superclasses:
            operating_systems[cls.name] = cls()
        return cls


class OS(DockerBuildable, metaclass=OSMeta):
    packages = None

    @property
    def name(self):
        return self.__class__.__name__.lower()

    def get_build_commands(self):
        if not self.packages:
            return ''
        return str(self.packages)

    def get_base_image_name(self):
        return self.base_image


class Debian(OS):
    name = 'debian'
    base_image= 'debian'
    packages = Apt(['python-pip', 'curlftpfs'])

class Ubuntu(OS):
    name = 'ubuntu'
    base_image = 'ubuntu'
    packages = Apt(['python-pip', 'curlftpfs'])

class Centos(OS):
    name = 'centos'
    base_image = 'centos'
    packages = Yum(['epel-release', 'python-pip', 'curlftpfs'])

# class Alpine(OS):
#     name = 'alpine'
#     base_image = 'alpine'
#     packages = Apk(['sshfs'])


class Gentoo(OS):
    name = 'gentoo'
    base_image = 'thedcg/gentoo'
    packages = Emerge(['dev-python/pip', 'curlftpfs'])


class PackageImage(DockerBuildable):

    def __init__(self, os_obj, cmds):
        self.os_obj = os_obj
        self.cmds = cmds

    def get_base_image_name(self):
        return self.os_obj.get_image_name()

    def get_build_commands(self):
        return self.cmds

    def build_all(self):
        self.os_obj.build()
        self.build()

    def ensure_builded_all(self):
        self.os_obj.ensure_builded()
        self.ensure_builded()

    def run(self, cmd_with_args, extra_envs={}):

        args = [
            'docker',
            'run',
            '-ti',
            '--net=host', # does not bind the port on mac
            '--privileged',
            '--cap-add=ALL',
            '-v', '/dev:/dev',
            '-v', '/lib/modules:/lib/modules',
            '-v', '/Users/iraehueckcosta/dopkg/run.sh:/run.sh',
            '-e', 'HOST_PWD={}'.format(os.getcwd()),
            '-e', 'HOST_HOME={}'.format(environ['HOME']),
            '--rm',
            self.get_image_name(),
            'bash', '/run.sh',
        ] + list(cmd_with_args)

        for env, env_val in dict(environ, **extra_envs).items():
            if env not in ['HOME', 'PWD']:
                args.insert(2, '-e')
                args.insert(3, '{}={}'.format(env, shlex.quote(env_val)))  # SECURITY: is shlex.quote safe?

        return subprocess.Popen(args)



def main():
    HELP = 'my help'
    PROG = 'packy'
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description='Run programm from any Linux',
        prog=PROG,
        epilog=HELP)

    parser.add_argument(
        "exec", type=str, nargs='*', default=['bash'], help='What to execute in container')
    for pm in package_managers:
        parser.add_argument(
            "--{}".format(pm), type=str, nargs="+", help='install with {}'.format(pm))

    
    for os in operating_systems:
        parser.add_argument('--{}'.format(os), dest='os', action='append_const', const=os)

    parser.add_argument("--rebuild", default=False, action='store_true')
    parser.add_argument("--install", default=False)


    args = parser.parse_args(sys.argv[1:])

    if not args.os:
        parser.error('specify at least on operating system')
    elif len(args.os) > 1:
        parser.error('specify only one operating system')

    # if args.install is False:
    #     install = False
    # elif not len(args.install):
    #     # default value
    #     install = '/usr/local/bin/{}'.format(args.exec[0])
    # elif len(args.install) == 1:
    #     install = args.install[0]
    # else:
    #     parser.error('--install needs one or no argument')

    build_cmds = []
    for pm, pm_obj in package_managers.items():
        packages = getattr(args, pm)
        if packages:
            build_cmds.append(str(pm_obj(packages)))
    build_cmds = ' && '.join(build_cmds)
    
    pi = PackageImage(operating_systems[args.os[0]], build_cmds)
    if not args.rebuild:
        pi.ensure_builded_all()
    else:
        pi.build_all()

    if not args.install:

        # start a FTP Server
        ftp_password = rand()
        authorizer = DummyAuthorizer()
        authorizer.add_user("user", ftp_password, home_directory, perm="elradfmw")
        handler = FTPHandler
        handler.authorizer = authorizer
        server = FTPServer((HOST_IP, 0), handler)
        used_port = server.socket.getsockname()[1]
        proc = pi.run(
            args.exec,
            extra_envs={
                'HOST_FTP_PORT': str(used_port),
                'HOST_IP': HOST_IP,
                'HOST_FTP_PASSWORD': ftp_password,
            })

        # mainloop
        while True:
            server.serve_forever(blocking=False, timeout=0.05)
            exit = proc.poll()
            if exit is not None:
                server.close_all()
                sys.exit(exit)

    else:
        install_to = args.install
        argv = sys.argv[1:]
        install_index =  argv.index('--install')
        argv.pop(install_index)
        argv.pop(install_index)
        run_script = '#!/bin/sh\n{} {} "$@"\n'.format(
            path.abspath(__file__), ' '.join(argv))
        create_executable_file(install_to, run_script)
        print('Installed to {}'.format(install_to))
    # print(args)


if __name__ == '__main__':
    main()
