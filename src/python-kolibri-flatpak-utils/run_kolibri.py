#!/usr/bin/python3

import argparse

from .run_kolibri_desktop import kolibri_desktop_main
from .run_kolibri_service import kolibri_service_main


def main():
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest='subcommand', required=False)

    desktop_parser = subcommands.add_parser('desktop')
    desktop_parser.add_argument('path', nargs='?', type=str, default='/')

    service_parser = subcommands.add_parser('service')

    options = parser.parse_args()

    if options.subcommand is None:
        return kolibri_desktop_main()
    elif options.subcommand == 'desktop':
        return kolibri_desktop_main(options.path)
    elif options.subcommand == 'service':
        return kolibri_service_main()
    else:
        print("Error: Invalid subcommand")
        return 1


if __name__== "__main__":
    exitcode = main()
    sys.exit(exitcode)
