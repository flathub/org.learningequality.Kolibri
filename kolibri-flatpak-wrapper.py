#!/usr/bin/python3

# Kolibri flatpak wrapper script.
# Discovers content extension directories, sets CONTENT_FALLBACK_DIRS
# accordingly, and runs scanforcontent when content extensions have changed.

import logging
logger = logging.getLogger(__name__)

import datetime
import json
import os
import re
import subprocess
import sys

from configparser import ConfigParser

from kolibri_gnome.globals import init_logging, XDG_DATA_HOME

KOLIBRI = os.environ.get('X_KOLIBRI', 'kolibri')

CONTENT_EXTENSION_RE = r'^org.learningequality.Kolibri.Content.(?P<name>\w+)$'
CONTENT_EXTENSIONS_DIR = os.environ.get('X_CONTENT_EXTENSIONS_DIR', '')

CONTENT_EXTENSIONS_STATE_PATH = os.path.join(XDG_DATA_HOME, 'kolibri-content-extensions.json')


def load_content_extensions_state():
    try:
        with open(CONTENT_EXTENSIONS_STATE_PATH, 'r') as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return None


def save_content_extensions_state(content_extensions):
    with open(CONTENT_EXTENSIONS_STATE_PATH, 'w') as file:
        json.dump(content_extensions, file)


def find_content_extensions():
    result = {}

    flatpak_info = ConfigParser()
    flatpak_info.read('/.flatpak-info')
    app_extensions = flatpak_info.get('Instance', 'app-extensions', fallback='')
    for extension_str in app_extensions.split(';'):
        extension_ref, extension_commit = extension_str.split('=')
        content_extension_match = re.match(CONTENT_EXTENSION_RE, extension_ref)
        if content_extension_match:
            result[content_extension_match.group('name')] = extension_commit

    return result


def update_content_extensions(new_content_extensions, env=None):
    old_content_extensions = load_content_extensions_state()

    if new_content_extensions == old_content_extensions:
        return True

    logger.info("Content extensions have changed.")
    logger.info("Running scanforcontent: %s", datetime.datetime.today())
    result = subprocess.run([KOLIBRI, 'manage', 'scanforcontent'], env=env)
    if result.returncode == 0:
        logger.info("scanforcontent completed: %s", datetime.datetime.today())
        save_content_extensions_state(new_content_extensions)
        return True
    else:
        logger.warning("scanforcontent failed: %d", result.returncode)
        return False


def run_kolibri(env=None):
    return subprocess.run([KOLIBRI, *sys.argv[1:]], env=env).returncode


def main():
    init_logging('kolibri-flatpak-wrapper.txt')

    content_extensions = find_content_extensions()

    kolibri_env = os.environ.copy()
    content_path_list = [
        os.path.join(CONTENT_EXTENSIONS_DIR, name) for name in content_extensions.keys()
    ]
    os.environ['CONTENT_FALLBACK_DIRS'] = ':'.join(content_path_list)

    update_content_extensions(content_extensions, env=kolibri_env)

    return run_kolibri(env=kolibri_env)


if __name__ == "__main__":
    result = main()
    sys.exit(result)

