# import where needed to make startup faster
import os
import sys
from contextlib import contextmanager
from os.path import join

ERROR_COLOR = 1
INFO_COLOR = 4

BASE_DIR = os.environ.get('PLASH_DATA', '/var/lib/plash')
TMP_DIR = join(BASE_DIR, 'tmp')
BUILDS_DIR = join(BASE_DIR, 'builds')
LINKS_DIR = join(BASE_DIR, 'links')


def hashstr(stri):
    import hashlib
    return hashlib.sha1(stri).hexdigest()


@contextmanager
def catch_and_die(exceptions, debug=None, ignore=None):
    try:
        yield
    except tuple(exceptions) as exc:
        if ignore and isinstance(exc, ignore):
            raise
        program = os.path.basename(sys.argv[0])
        msg = str(exc)
        if msg.startswith('<') and msg.endswith('>'):
            msg = msg[1:-1]
        if debug:
            msg = '{debug}: {message}'.format(debug=debug, message=msg)
        die('at ' + program + ': ' + msg)


def deescalate_sudo():
    import pwd
    import grp
    uid = os.environ.get('SUDO_UID')
    gid = os.environ.get('SUDO_GID')
    if uid and gid:
        uid = int(uid)
        gid = int(gid)
        # username = pwd.getpwuid(uid).pw_name
        # groups = [g.gr_gid for g in grp.getgrall() if username in g.gr_mem]
        os.setgroups([])  # for now loose supplementary groups
        os.setregid(int(gid), int(gid))
        os.setreuid(int(uid), int(uid))


def color(stri, color, isatty_fd_check=2):
    if os.isatty(isatty_fd_check):
        return "\033[38;05;{}m".format(int(color)) + stri + "\033[0;0m"
    return stri

def die(msg, exit=1):
    print(color('plash: error: ', ERROR_COLOR) + msg, file=sys.stderr)
    sys.exit(exit)


def info(msg):
    print(color(msg, INFO_COLOR), file=sys.stderr)

def call_plash_nodepath(container):
    from subprocess import CalledProcessError, check_output
    try:
        return check_output(['plash-nodepath',
                                  container]).decode().strip('\n')
    except CalledProcessError as exc:
        if exc.returncode == 3:
            sys.exit(exc.returncode)
        with catch_and_die([CalledProcessError]):
            raise

def die_with_usage():
    printed_usage = False
    with open(sys.argv[0]) as f:
        for line in f.readlines():
            if line.startswith('# usage:'):
                print(line[2:], end='')
                printed_usage = True
    assert printed_usage, 'could not find usage comment'
    sys.exit(2)

def handle_help_flag():
    if len(sys.argv) >= 2 and sys.argv[1] in ('--help', '-h'):
        with open(sys.argv[0]) as f:
            do_print = False
            for line in f.readlines():
                if line.startswith('# usage:'):
                    do_print = True
                elif line and not line.startswith('#'):
                    break
                if do_print:
                    print(line[2:], end='')
        sys.exit(0)
