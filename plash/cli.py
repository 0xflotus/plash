import argparse
import sys

from .eval import eval


class PlashArgumentParser(argparse.ArgumentParser):
        def convert_arg_line_to_args(self, arg_line):
            '''
            Actually plashs own domain specific language
            '''
            if not arg_line or arg_line.lstrip(' ').startswith('#'):
                return []

            elif arg_line.startswith('\t'):
                return ' ' + arg_line[1:]
            arg_line = arg_line.split('#')[0] # remove anything after an #
            args = arg_line.split()
            raw_action = args.pop(0)
            if not raw_action.startswith(('-', '@')):
                yield ':'+raw_action
            else:
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

def main():
    lsp, unknown = (read_lsp_from_args(sys.argv[1:]))
    print(unknown)
    print(lsp)
    print(eval(lsp))



# --collect apt
