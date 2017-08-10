import argparse
import os
import shlex
import subprocess
import sys
from subprocess import CalledProcessError, list2cmdline

from . import state, core, dockercore
from .eval import ActionNotFoundError, ArgError, EvalError, eval, layer
from .core import BuildError
from .dockercore import DockerBuildError, docker_get_image_shell
from .utils import (disable_friendly_exception, friendly_exception, hashstr,
                    rand)

HELP = 'my help'
PROG = 'plash'


NO_TERM_BUILD_ERROR = """plash error: Refusing to build when not connected to a tty(-like) device.
Set the env PLASH_BUILD_SILENT to enable building without output is such cases.
Or invoke this call with --build-only from a terminal to build and then run again.
The argv of this program was: {}""".format(sys.argv)

# shortcuts are specific to the stdlib
SHORTCUTS = [
    # shortcut, lsp, nargs
    ('-x', ['run'], '+'),
    ('-a', ['apt'], '+'),
    ('-y', ['yum'], '+'),
    ('-p', ['pip'], '+'),
    ('-b', ['apt', 'ubuntu-server'], 0),
    ('-o', ['os'], 1),
    ('-r', ['include', '~/.plashrc'], 0),
    ('-U', ['os', 'ubuntu'], 0),
    ('-F', ['os', 'fedora'], 0),
    ('-D', ['os', 'debian'], 0),
 ]


def add_shortcuts_to_parser(parser):
    group = parser.add_argument_group('shortcuts', 'shortcuts')
    for shortcut, lsp, nargs in SHORTCUTS:
        group.add_argument(
            shortcut,
            action=create_collect_lsp_action(lsp),
            nargs=nargs)

def create_collect_lsp_action(lsp_begin):
    class CollectAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            if not 'lsp' in namespace:
                setattr(namespace, 'lsp', [])
            previous = namespace.lsp
            previous.append(lsp_begin + list(values))
            setattr(namespace, 'lsp', previous) 
    return CollectAction

def get_argument_parser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description='Run programm from any Linux',
        prog=PROG,
        epilog=HELP)

    parser.add_argument("--build-silent", action='store_true')
    parser.add_argument("--build-verbose", "--build-loud", action='store_true', dest='verbose')
    parser.add_argument("--build-only", action='store_true')
    parser.add_argument("--build-again", "--rebuild", "--again", action='store_true')

    parser.add_argument("--no-stdlib", action='store_true')
    parser.add_argument("--traceback", action='store_true')
    parser.add_argument("--debug-lsp", action='store_true')

    parser.add_argument("--ignore-no-tty", action='store_false')

    parser.add_argument("--docker", "-d", action='store_true')

    parser.add_argument("--docker-save-image")

    parser.add_argument(
        "exec", type=str, nargs='*')

    add_shortcuts_to_parser(parser)

    return parser



def main():
    ap = get_argument_parser()
    _, unused_args = ap.parse_known_args(sys.argv[1:])
    # lsp = unused_args_to_lsp(unused_args)
    for arg in set(unused_args):
        if arg == '--':
            break
        if arg.startswith('--'):
            ap.add_argument(
                arg,
                action=create_collect_lsp_action([arg[2:]]),
                nargs='*')
    args = ap.parse_args()
    build_silent = args.build_silent or os.environ.get('PLASH_BUILD_SILENT')
    lsp = getattr(args, 'lsp', [])

    if args.traceback:
        disable_friendly_exception()
    if not args.no_stdlib:
        init = [['import', 'plash.stdlib']]
    else:
        init = []

    if args.debug_lsp:
        print(init + lsp)
        sys.exit(0)
    with friendly_exception([ActionNotFoundError, ArgError, EvalError]):
        state.reset()
        script = eval(init + lsp)

    os_image = state.get_os()
    if not os_image:
        with friendly_exception([ArgError]):
            raise ArgError('Specify an image')
    layers = (script + '\n').split(layer() + '\n')
    layers = [l for l in layers if l]
    if os_image == 'print':
        print(script)
        sys.exit(0)


    if os_image.startswith('build://'):
        build = os_image[len('build://'):]
        tmp_image = rand() # fixme cleanup this image later
        p = subprocess.Popen(['docker', 'build', build, '-t', tmp_image])
        exit = p.wait()
        assert exit == 0
        image = subprocess.check_output(
            ['docker', 'images', '--quiet', tmp_image])
        image = image.decode().rstrip('\n')
        subprocess.check_output(['docker', 'rmi', tmp_image])
    else:
        image = os_image

    # b = LayeredDockerBuildable.create(image, layers)
    # with friendly_exception([BuildError, CalledProcessError]):
    #     if args.build_again or not b.image_ready():
    #         if not sys.stdout.isatty() and not build_silent and not args.ignore_no_tty:
    #             sys.stderr.write(NO_TERM_BUILD_ERROR)
    #             print()
    #             sys.exit(127)


        bcmd = state.get_base_command() or ''
        command = (args.exec or [docker_get_image_shell(image)]) if not bcmd else shlex.split(bcmd) + (args.exec or [])

        plash_env = '{}-{}'.format( # some 
            os_image,
            hashstr('\n'.join(layers).encode())[:4])

        if not args.docker:
            execute = core.execute
            execute_extra_kws = {}
        else:
            execute = dockercore.execute
            execute_extra_kws = {'docker_save_image': args.docker_save_image}

        execute(image,
                layers,
                command,
                quiet_flag=args.build_silent,
                verbose_flag=args.verbose,
                skip_if_exists=not args.build_again,
                extra_mounts=state.pop_mountpoints(),
                **execute_extra_kws)

        # # something that could be used in the shell prompt
        # docker_run(
        #     b.get_image_name(),
        #     command,
        #     extra_envs={'PLASH_ENV': plash_env},
        #     )

        #     print('*** plash: building...')
        #     b.build(
        #         shell=docker_get_image_shell(image),
        #         quiet=build_silent,
        #         verbose=args.verbose,
        #         extra_mounts=state.pop_mountpoints(),
        #         skip_if_exists=not args.build_again)
        #     print('*** plash: done')
        #     print()

#     if args.save_image:
#         with friendly_exception([CalledProcessError], 'save-image'):
#             container_id = subprocess.check_output(
#                 ['docker', 'run', b.get_image_name(), 'hostname'])
#             container_id = container_id.decode().strip('\n')
#             subprocess.check_output(
#                 ['docker', 'commit', container_id, args.save_image])

#     bcmd = state.get_base_command() or ''
#     command = (args.exec or [docker_get_image_shell(image)]) if not bcmd else shlex.split(bcmd) + (args.exec or [])

#     plash_env = '{}-{}'.format( # some 
#         os_image,
#         hashstr('\n'.join(layers).encode())[:4])

#     # something that could be used in the shell prompt
#     docker_run(
#         b.get_image_name(),
#         command,
#         extra_envs={'PLASH_ENV': plash_env},
#         )
