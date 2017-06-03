import argparse
import os
import subprocess
import sys
from subprocess import CalledProcessError

from .eval import ActionNotFoundError, ArgError, EvalError, eval, layer
from .runos import BuildError, LayeredDockerBuildable, docker_run, runos
from .utils import (disable_friendly_exception, friendly_exception, hashstr,
                    rand)

HELP = 'my help'
PROG = 'plash'

SHORTCUTS = [
    # shortcut, lsp, nargs
    ('-a', ['apt'], '+'),
    ('-p', ['pip'], '+'),
    ('-b', ['apt', 'ubuntu-server'], 0),
 ]


def add_shortcuts_to_parser(parser):
    group = parser.add_argument_group('shortcuts', 'shortcuts')
    for shortcut, lsp, nargs in SHORTCUTS:
        group.add_argument(
            shortcut,
            action=create_collect_lsp_action(lsp),
            nargs=nargs)

class PlashArgumentParser(argparse.ArgumentParser):
        def convert_arg_line_to_args(self, arg_line):
            '''
            Actually plashs own domain specific language
            '''
            if arg_line and not arg_line.lstrip(' ').startswith('#'):
                if arg_line.startswith('\t'):
                    yield ' ' + arg_line[1:]
                else:
                    arg_line = arg_line.split('#')[0] # remove anything after an #
                    args = arg_line.split()
                    raw_action = args.pop(0)
                    # if not raw_action.startswith(('-', '@')):
                    #     yield ':'+raw_action
                    # else:
                    yield raw_action
                    for arg in args:
                        if arg.startswith('#'):
                            break
                        yield ' ' + arg

def create_collect_lsp_action(lsp_begin):
    class CollectAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            if not 'lsp' in namespace:
                setattr(namespace, 'lsp', [])
            previous = namespace.lsp
            previous.append(lsp_begin + list(values))
            setattr(namespace, 'lsp', previous) 
    return CollectAction

def read_lsp_from_args(args):
    parser = PlashArgumentParser(prefix_chars='-:', fromfile_prefix_chars='@')

    add_shortcuts_to_parser(parser)

    parsed, unknown = parser.parse_known_args(args)
    registered = []
    for arg in unknown:
        if arg.startswith(":") and not arg in registered:
            #you can pass any arguments to add_argument
            parser.add_argument(
                arg,
                nargs='*',
                action=create_collect_lsp_action([arg[1:]]))
            registered.append(arg)

    args, unknown = parser.parse_known_args(args)
    lsp = getattr(args, 'lsp', [])
    return lsp, unknown


def get_argument_parser(args):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description='Run programm from any Linux',
        prog=PROG,
        epilog=HELP)

    parser.add_argument("--build-quiet", action='store_true', dest='quiet')
    parser.add_argument("--build-verbose", "--build-loud", action='store_true', dest='verbose')
    parser.add_argument("--build-only", action='store_true')
    parser.add_argument("--build-again", "--rebuild", "--again", action='store_true')
    parser.add_argument("--no-stdlib", action='store_true')
    parser.add_argument("--traceback", action='store_true')
    parser.add_argument("--debug-lsp", action='store_true')

    parser.add_argument("--save-image")

    if not 'PLASH_COLLECT_MODE' in os.environ:
        parser.add_argument(
            "image", type=str)
        parser.add_argument(
            "exec", type=str, nargs='*', default=['bash'])

    add_shortcuts_to_parser(parser)

    return parser



def main():
    lsp, unused_args = read_lsp_from_args(sys.argv[1:])
    ap = get_argument_parser(unused_args)
    args = ap.parse_args(unused_args)
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
        script = eval(init + lsp)
    collect_to = os.environ.get('PLASH_COLLECT_MODE')
    if collect_to:
        with friendly_exception(
                [IOError], 'write-collect-file'), open(collect_to, 'w') as f:
            f.write(script)
        sys.exit(0)

    layers = script.split('{}'.format(layer()))
    plash_env = '{}-{}'.format(
        args.image,
        hashstr('\n'.join(layers).encode())[:4])
    if args.image == 'print':
        print(script)
        sys.exit(0)


    if args.image.startswith('build://'):
        build = args.image[len('build://'):]
        tmp_image = rand() # fixme cleanup this image later
        p = subprocess.Popen(['docker', 'build', build, '-t', tmp_image])
        exit = p.wait()
        assert exit == 0
        image = subprocess.check_output(
            ['docker', 'images', '--quiet', tmp_image])
        image = image.decode().rstrip('\n')
        subprocess.check_output(['docker', 'rmi', tmp_image])
    else:
        image = args.image

    b = LayeredDockerBuildable.create(image, layers)

    with friendly_exception([BuildError, CalledProcessError]):
        if args.build_again:
            b.build(
                quiet=args.quiet,
                verbose=args.verbose)
        else:
            b.ensure_builded(
                quiet=args.quiet,
                verbose=args.verbose)

    if args.save_image:
        with friendly_exception([CalledProcessError], 'save-image'):
            container_id = subprocess.check_output(
                ['docker', 'run', b.get_image_name(), 'hostname'])
            container_id = container_id.decode().strip('\n')
            subprocess.check_output(
                ['docker', 'commit', container_id, args.save_image])

    command = args.exec if not args.build_only else None
    if command:
        exit = docker_run(b.get_image_name(), command,
                          extra_envs={'PLASH_ENV': plash_env})
        sys.exit(exit)
