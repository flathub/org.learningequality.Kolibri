#!/usr/bin/python3

import argparse

from .run_kolibri_desktop import kolibri_desktop_main
from .run_kolibri_service import kolibri_service_main


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='subparser', required=True)

    desktop_parser = subparsers.add_parser('desktop')
    desktop_parser.add_argument('path', nargs='?', type=str, default='/')

    service_parser = subparsers.add_parser('service')

    options = parser.parse_args()

    if options.subparser == 'desktop':
        return kolibri_desktop_main(options.path)
    elif options.subparser == 'service':
        return kolibri_service_main()
    else:
        print("Error: Invalid subcommand")
        return 1


if __name__== "__main__":
    exitcode = main()
    sys.exit(exitcode)
