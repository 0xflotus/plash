import argparse
import sys

from .eval import eval, layer
from .runos import runos
from .utils import hashstr

HELP = 'my help'
PROG = 'plash'


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

class CollectLspAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if not 'lsp' in namespace:
            setattr(namespace, 'lsp', [])
        previous = namespace.lsp                             
        # remove escape eventual the space that is used as escape char
        values = list(i[1:] if i.startswith(' ') else i for i in values)
        previous.append([self.dest.replace('_', '-')] + values)
        setattr(namespace, 'lsp', previous) 

def read_lsp_from_args(args):
    parser=PlashArgumentParser(prefix_chars='-:', fromfile_prefix_chars='@')
    parsed, unknown = parser.parse_known_args()
    registered = []
    for arg in unknown:
        if arg.startswith(":") and not arg in registered:
            #you can pass any arguments to add_argument
            parser.add_argument(arg, nargs='*', action=CollectLspAction)
            registered.append(arg)

    args, unknown = parser.parse_known_args()
    lsp = getattr(args, 'lsp', [])
    return lsp, unknown


def get_argument_parser(args):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description='Run programm from any Linux',
        prog=PROG,
        epilog=HELP)

    parser.add_argument("--build-quiet", action='store_true', dest='quiet')
    parser.add_argument("--no-lib", action='store_true')
    parser.add_argument("--no-bootstrap", action='store_true')
    parser.add_argument(
        "image", type=str)
    parser.add_argument(
        "exec", type=str, nargs='*', default=['bash'])
    return parser



def main():
    lsp, unused_args = (read_lsp_from_args(sys.argv[1:]))
    ap = get_argument_parser(unused_args)
    args = ap.parse_args(unused_args)
    # print(args, unused_args)
    if not args.no_lib:
        init = [['import', 'plash.actions']]
        if not args.no_bootstrap:
            init += [['bootstrap', args.image]]
    else:
        init = []
    script = eval(init + lsp)
    layers = script.split('{}'.format(layer()))
    plash_env = '{}-{}'.format(
        args.image,
        hashstr('\n'.join(layers).encode())[:4])
    exit = runos(
        args.image,
        layers,
        args.exec,
        quiet=args.quiet,
        extra_envs={'PLASH_ENV': plash_env}
    )



# --collect apt
