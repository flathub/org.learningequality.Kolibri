#!/usr/bin/python3

# Kolibri flatpak wrapper script.
# Discovers content extension directories, sets KOLIBRI_CONTENT_FALLBACK_DIRS
# accordingly, and runs scanforcontent when content extensions have changed.

import logging
logger = logging.getLogger(__name__)

import datetime
import json
import operator
import os
import re
import subprocess
import sys

from collections import namedtuple
from configparser import ConfigParser

from kolibri_gnome.globals import init_logging, XDG_DATA_HOME

KOLIBRI = os.environ.get('X_KOLIBRI', 'kolibri')


class ContentExtension(namedtuple('ContentExtension', ['ref', 'name', 'commit'])):
    CONTENT_EXTENSIONS_DIR = os.environ.get('X_CONTENT_EXTENSIONS_DIR', '')
    CONTENT_EXTENSION_RE = r'^org.learningequality.Kolibri.Content.(?P<name>\w+)$'

    @classmethod
    def from_ref(cls, ref, *args, **kwargs):
        match = re.match(cls.CONTENT_EXTENSION_RE, ref)
        if match:
            name = match.group('name')
            return cls(ref, name, *args, **kwargs)
        else:
            return None

    @classmethod
    def from_json(cls, json):
        return cls(
            json.get('ref'),
            json.get('name'),
            json.get('commit')
        )

    def to_json(self):
        return self._asdict()

    @property
    def path(self):
        return os.path.join(self.CONTENT_EXTENSIONS_DIR, self.name)

    def get_content(self):
        # TODO: Store this in the cache (ContentExtensionsList), not here.
        content_path = os.path.join(self.path, 'content.json')
        try:
            with open(content_path, 'r') as file:
                return json.load(file)
        except (OSError, json.JSONDecodeError):
            return {}

    def get_channels(self):
        return self.get_content().get('channels', [])


class ContentExtensionsList(object):
    CONTENT_EXTENSIONS_STATE_PATH = os.path.join(XDG_DATA_HOME, 'kolibri-content-extensions.json')

    def __init__(self, extensions=set()):
        self.__extensions = set(extensions)

    @classmethod
    def from_flatpak_info(cls):
        extensions = set()

        flatpak_info = ConfigParser()
        flatpak_info.read('/.flatpak-info')
        app_extensions = flatpak_info.get('Instance', 'app-extensions', fallback='')
        for extension_str in app_extensions.split(';'):
            extension_ref, extension_commit = extension_str.split('=')
            content_extension = ContentExtension.from_ref(extension_ref, commit=extension_commit)
            if content_extension:
                extensions.add(content_extension)

        return cls(extensions)

    @classmethod
    def from_cache(cls):
        extensions = set()

        try:
            with open(cls.CONTENT_EXTENSIONS_STATE_PATH, 'r') as file:
                extensions_json = json.load(file)
        except (OSError, json.JSONDecodeError):
            pass
        else:
            extensions = set(map(ContentExtension.from_json, extensions_json))

        return cls(extensions)

    def write_to_cache(self):
        with open(self.CONTENT_EXTENSIONS_STATE_PATH, 'w') as file:
            extensions_json = list(map(ContentExtension.to_json, self.__extensions))
            json.dump(extensions_json, file)

    @property
    def content_fallback_dirs(self):
        return ':'.join(
            map(operator.attrgetter('path'), self.__extensions)
        )

    @staticmethod
    def removed(old, new):
        removed_refs = old.__refs.difference(new.__refs)
        return old.__filter_extensions(removed_refs)

    @staticmethod
    def added(old, new):
        added_refs = new.__refs.difference(old.__refs)
        return new.__filter_extensions(added_refs)

    @staticmethod
    def changed(old, new):
        common_refs = old.__refs.intersection(new.__refs)
        old_extensions = old.__filter_extensions(common_refs)
        new_extensions = new.__filter_extensions(common_refs)
        return new_extensions.difference(old_extensions)

    @staticmethod
    def unchanged(old, new):
        common_refs = old.__refs.intersection(new.__refs)
        old_extensions = old.__filter_extensions(common_refs)
        new_extensions = new.__filter_extensions(common_refs)
        return new_extensions.intersection(old_extensions)

    @property
    def __extensions_dict(self):
        return dict((extension.ref, extension) for extension in self.__extensions)

    @property
    def __refs(self):
        return set(map(operator.attrgetter('ref'), self.__extensions))

    def __get_extension(self, ref):
        return self.__extensions_dict.get(ref)

    def __filter_extensions(self, refs):
        return set(map(self.__get_extension, refs))


def run_kolibri(args=None, env=None):
    if args is None:
        args = sys.argv[1:]
    return subprocess.run([KOLIBRI, *args], env=env).returncode


def run_kolibri_scan_content(channel_ids, env=None):
    logger.info("scanforcontent starting: %s %s", datetime.datetime.today(), channel_ids)
    scan_result = run_kolibri(['manage', 'scanforcontent', '--channels', ','.join(channel_ids)], env=env)
    if scan_result == 0:
        logger.info("scanforcontent completed: %s", datetime.datetime.today())
        return True
    else:
        logger.warning("scanforcontent failed: %d", scan_result)
        return False


def main():
    init_logging('kolibri-flatpak-wrapper.txt')

    cached_extensions = ContentExtensionsList.from_cache()
    active_extensions = ContentExtensionsList.from_flatpak_info()

    kolibri_env = os.environ.copy()
    kolibri_env['KOLIBRI_CONTENT_FALLBACK_DIRS'] = active_extensions.content_fallback_dirs

    changed_channels = set()

    for extension in ContentExtensionsList.removed(cached_extensions, active_extensions):
        logging.info("Removed extension: %s", extension.ref)
        changed_channels.update(
            map(operator.itemgetter('channel_id'), extension.get_channels())
        )

    for extension in ContentExtensionsList.added(cached_extensions, active_extensions):
        logging.info("Added extension: %s", extension.ref)
        changed_channels.update(
            map(operator.itemgetter('channel_id'), extension.get_channels())
        )

    for extension in ContentExtensionsList.changed(cached_extensions, active_extensions):
        logging.info("Changed extension: %s", extension.ref)
        changed_channels.update(
            map(operator.itemgetter('channel_id'), extension.get_channels())
        )

    for extension in ContentExtensionsList.unchanged(cached_extensions, active_extensions):
        logging.debug("Unchanged extension: %s", extension.ref)

    if len(changed_channels) > 0:
        scan_success = run_kolibri_scan_content(changed_channels, env=kolibri_env)
        if scan_success:
            active_extensions.write_to_cache()

    return run_kolibri(env=kolibri_env)


if __name__ == "__main__":
    result = main()
    sys.exit(result)

