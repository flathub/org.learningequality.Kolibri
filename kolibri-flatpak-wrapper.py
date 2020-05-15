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

from kolibri_gnome.globals import init_logging, KOLIBRI_HOME

KOLIBRI = os.environ.get('X_KOLIBRI', 'kolibri')


class ContentExtension(object):
    """
    Represents a content extension, with details about the flatpak ref and
    support for an index of content which may be either cached or located in the
    content extension itself. We assume any ContentExtension instances with
    matching ref and commit must be the same.
    """

    CONTENT_EXTENSIONS_DIR = os.environ.get('X_CONTENT_EXTENSIONS_DIR', '')
    CONTENT_EXTENSION_RE = r'^org.learningequality.Kolibri.Content.(?P<name>\w+)$'

    def __init__(self, ref, name, commit, content=None):
        self.__ref = ref
        self.__name = name
        self.__commit = commit
        self.__content = content

    @classmethod
    def from_ref(cls, ref, commit):
        match = re.match(cls.CONTENT_EXTENSION_RE, ref)
        if match:
            name = match.group('name')
            return cls(ref, name, commit, content=None)
        else:
            return None

    @classmethod
    def from_json(cls, json):
        return cls(
            json.get('ref'),
            json.get('name'),
            json.get('commit'),
            content=json.get('content')
        )

    def to_json(self):
        return {
            'ref': self.ref,
            'name': self.name,
            'commit': self.commit,
            'content': self.content
        }

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __hash__(self):
        return hash((self.__ref, self.__name, self.__commit))

    @property
    def ref(self):
        return self.__ref

    @property
    def name(self):
        return self.__name

    @property
    def commit(self):
        return self.__commit

    @property
    def content(self):
        if self.__content is not None:
            return self.__content

        content_json_path = os.path.join(self.content_dir, 'content.json')

        try:
            with open(content_json_path, 'r') as file:
                self.__content = json.load(file)
        except (OSError, json.JSONDecodeError):
            self.__content == {}

        return self.__content

    @property
    def channels(self):
        return self.content.get('channels', [])

    @property
    def base_dir(self):
        return os.path.join(self.CONTENT_EXTENSIONS_DIR, self.name)

    @property
    def content_dir(self):
        return os.path.join(self.base_dir, 'content')


class ContentExtensionsList(object):
    """
    Keeps track of a list of content extensions, either cached from a file in
    $KOLIBIR_HOME, or generated from /.flatpak-info. Multiple lists can be
    compared to detect changes in the environment.
    """

    CONTENT_EXTENSIONS_STATE_PATH = os.path.join(KOLIBRI_HOME, 'content-extensions.json')

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
        return list(map(operator.attrgetter('content_dir'), self.__extensions))

    @staticmethod
    def removed(old, new):
        removed_refs = old.__refs.difference(new.__refs)
        return old.__filter_extensions(removed_refs)

    @staticmethod
    def added(old, new):
        added_refs = new.__refs.difference(old.__refs)
        return new.__filter_extensions(added_refs)

    @staticmethod
    def updated(old, new):
        common_refs = old.__refs.intersection(new.__refs)
        old_extensions = old.__filter_extensions(common_refs)
        new_extensions = new.__filter_extensions(common_refs)
        return new_extensions.difference(old_extensions)

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


class Application(object):
    def __init__(self):
        self.__cached_extensions = ContentExtensionsList.from_cache()
        self.__active_extensions = ContentExtensionsList.from_flatpak_info()

    def run(self):
        process_success = all([
            self.__process_removed_extensions(),
            self.__process_added_extensions(),
            self.__process_updated_extensions()
        ])

        if process_success:
            self.__active_extensions.write_to_cache()

        return self.__run_kolibri()

    def __process_removed_extensions(self):
        # For each removed channel, run scanforcontent
        # TODO: Is there a less expensive way of doing this than scanforcontent?
        channel_ids = set()
        for extension in ContentExtensionsList.removed(self.__cached_extensions, self.__active_extensions):
            logging.info("Removed extension: %s", extension.ref)
            channel_ids.update(
                map(operator.itemgetter('channel_id'), extension.channels)
            )
        return self.__kolibri_scan_content(channel_ids, ['--channel-import-mode=none'])

    def __process_added_extensions(self):
        # For each added channel, run scanforcontent
        # TODO: Instead of scanforcontent, use importcontent with --node_ids and --exclude_node_ids
        channel_ids = set()
        for extension in ContentExtensionsList.added(self.__cached_extensions, self.__active_extensions):
            logging.info("Added extension: %s", extension.ref)
            channel_ids.update(
                map(operator.itemgetter('channel_id'), extension.channels)
            )
        return self.__kolibri_scan_content(channel_ids)

    def __process_updated_extensions(self):
        # For each updated channel, run scanforcontent
        # TODO: Instead of scanforcontent, use importcontent with --node_ids and --exclude_node_ids
        channel_ids = set()
        for extension in ContentExtensionsList.updated(self.__cached_extensions, self.__active_extensions):
            logging.info("Updated extension: %s", extension.ref)
            channel_ids.update(
                map(operator.itemgetter('channel_id'), extension.channels)
            )
        return self.__kolibri_scan_content(channel_ids)

    def __kolibri_scan_content(self, channel_ids, args=[]):
        if len(channel_ids) == 0:
            return True

        logger.info("scanforcontent starting for channels %s: %s", channel_ids, datetime.datetime.today())

        try:
            self.__run_kolibri(['manage', 'scanforcontent', '--channels={}'.format(','.join(channel_ids)), *args])
        except CalledProcessException as error:
            logger.warning("scanforcontent failed: %s", datetime.datetime.today())
            return False
        else:
            logger.info("scanforcontent completed: %s", datetime.datetime.today())
            return True

    def __run_kolibri(self, args=None):
        if args is None:
            args = sys.argv[1:]
        result = subprocess.run([KOLIBRI, *args], env=self.__kolibri_env, check=True)
        return result.returncode

    @property
    def __kolibri_env(self):
        kolibri_env = os.environ.copy()
        kolibri_env['KOLIBRI_CONTENT_FALLBACK_DIRS'] = ';'.join(self.__active_extensions.content_fallback_dirs)
        return kolibri_env


def main():
    init_logging('kolibri-flatpak-wrapper.txt')
    application = Application()
    return application.run()


if __name__ == "__main__":
    result = main()
    sys.exit(result)

