# cli/main.py
import argparse
from . import commands

def main():
    parser = argparse.ArgumentParser(prog='guru')
    subparsers = parser.add_subparsers(dest='command')

    # Subcommand 'init'
    parser_init = subparsers.add_parser('init', help='Initialize project')
    parser_init.add_argument('-d', action='store_true', help='default settings')
    parser_init.set_defaults(func=commands.init)
    

    # Subcommand 'new'
    parser_new = subparsers.add_parser('new', help='Create something new')
    new_subparsers = parser_new.add_subparsers(dest='new_command')

    # Subcommand 'new prompt'
    parser_new_prompt = new_subparsers.add_parser('prompt', help='Create a new prompt')
    parser_new_prompt.set_defaults(func=commands.new_prompt)

    # Subcommand 'new assignment'
    parser_new_assignment = new_subparsers.add_parser('assignment', help='Create a new assignment')
    parser_new_assignment.set_defaults(func=commands.new_assignment)

    # Subcommand internal prompts
    parser_internal_prompts = subparsers.add_parser('internal_prompts', help='Create internal prompts')
    parser_internal_prompts.set_defaults(func=commands.internal_prompts)

    # Parse arguments and call the appropriate function
    args = parser.parse_args()

    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()
if __name__ == "__main__":
    main()