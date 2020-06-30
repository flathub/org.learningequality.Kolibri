import itertools
import json
import os
import re

from configparser import ConfigParser

from kolibri_gnome.globals import KOLIBRI_HOME

CONTENT_EXTENSIONS_DIR = "/app/share/kolibri-content"
CONTENT_EXTENSION_RE = r"^org.learningequality.Kolibri.Content.(?P<name>\w+)$"


class ContentExtensionsList(object):
    """
    Keeps track of a list of content extensions, either cached from a file in
    $KOLIBRI_HOME, or generated from /.flatpak-info. Multiple lists can be
    compared to detect changes in the environment.
    """

    CONTENT_EXTENSIONS_STATE_PATH = os.path.join(
        KOLIBRI_HOME, "content-extensions.json"
    )

    def __init__(self, extensions=set()):
        self.__extensions = set(extensions)

    @classmethod
    def from_flatpak_info(cls):
        extensions = set()

        flatpak_info = ConfigParser()
        flatpak_info.read("/.flatpak-info")
        app_extensions = flatpak_info.get("Instance", "app-extensions", fallback="")
        for extension_str in app_extensions.split(";"):
            extension_ref, extension_commit = extension_str.split("=")
            content_extension = ContentExtension.from_ref(
                extension_ref, commit=extension_commit
            )
            if content_extension and content_extension.is_valid():
                extensions.add(content_extension)

        return cls(extensions)

    @classmethod
    def from_cache(cls):
        extensions = set()

        try:
            with open(cls.CONTENT_EXTENSIONS_STATE_PATH, "r") as file:
                extensions_json = json.load(file)
        except (OSError, json.JSONDecodeError):
            pass
        else:
            extensions = set(map(ContentExtension.from_json, extensions_json))

        return cls(extensions)

    def write_to_cache(self):
        with open(self.CONTENT_EXTENSIONS_STATE_PATH, "w") as file:
            extensions_json = list(map(ContentExtension.to_json, self.__extensions))
            json.dump(extensions_json, file)

    def get_extension(self, ref):
        return next((extension for extension in self.__extensions if extension.ref == ref), None)

    def __iter__(self):
        return iter(self.__extensions)

    @staticmethod
    def compare(old, new):
        changed_extensions = old.__extensions.symmetric_difference(new.__extensions)
        changed_refs = set(extension.ref for extension in changed_extensions)
        for ref in changed_refs:
            old_extension = old.get_extension(ref)
            new_extension = new.get_extension(ref)
            yield ContentExtensionCompare(ref, old_extension, new_extension)


class ContentExtension(object):
    """
    Represents a content extension, with details about the flatpak ref and
    support for an index of content which may be either cached or located in the
    content extension itself. We assume any ContentExtension instances with
    matching ref and commit must be the same.
    """

    def __init__(self, ref, name, commit, content_json=None):
        self.__ref = ref
        self.__name = name
        self.__commit = commit
        self.__content_json = content_json

    @classmethod
    def from_ref(cls, ref, commit):
        match = re.match(CONTENT_EXTENSION_RE, ref)
        if match:
            name = match.group("name")
            return cls(ref, name, commit, content_json=None)
        else:
            return None

    @classmethod
    def from_json(cls, json):
        return cls(
            json.get("ref"),
            json.get("name"),
            json.get("commit"),
            content_json=json.get("content"),
        )

    def to_json(self):
        return {
            "ref": self.ref,
            "name": self.name,
            "commit": self.commit,
            "content": self.content_json,
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

    def is_valid(self):
        return all(
            [os.path.isdir(self.content_dir), os.path.isfile(self.__content_json_path)]
        )

    @property
    def content_json(self):
        if self.__content_json is not None:
            return self.__content_json

        try:
            with open(self.__content_json_path, "r") as file:
                self.__content_json = json.load(file)
        except (OSError, json.JSONDecodeError):
            self.__content_json = {}

        return self.__content_json

    @property
    def __channels(self):
        channels_json = self.content_json.get("channels", [])
        return set(map(ContentChannel.from_json, channels_json))

    @property
    def channel_ids(self):
        return set(channel.channel_id for channel in self.__channels)

    def get_channel(self, channel_id):
        return next((channel for channel in self.__channels if channel.channel_id == channel_id), None)

    @property
    def base_dir(self):
        return os.path.join(CONTENT_EXTENSIONS_DIR, self.name)

    @property
    def content_dir(self):
        return os.path.join(self.base_dir, "content")

    @property
    def __content_json_path(self):
        return os.path.join(self.content_dir, "content.json")


class ContentChannel(object):
    def __init__(self, channel_id, include_node_ids, exclude_node_ids):
        self.__channel_id = channel_id
        self.__include_node_ids = include_node_ids or []
        self.__exclude_node_ids = exclude_node_ids or []

    @classmethod
    def from_json(cls, json):
        return cls(
            json.get("channel_id"), json.get("node_ids"), json.get("exclude_node_ids")
        )

    @property
    def channel_id(self):
        return self.__channel_id

    @property
    def include_node_ids(self):
        return set(self.__include_node_ids)

    @property
    def exclude_node_ids(self):
        return set(self.__exclude_node_ids)


class ContentExtensionCompare(object):
    def __init__(self, ref, old_extension, new_extension):
        self.__ref = ref
        self.__old_extension = old_extension
        self.__new_extension = new_extension

    @property
    def ref(self):
        return self.__ref
    
    def compare_channels(self):
        for channel_id in self.__all_channel_ids:
            old_channel = self.__old_channel(channel_id)
            new_channel = self.__new_channel(channel_id)
            yield ContentChannelCompare(channel_id, old_channel, new_channel)

    def __old_channel(self, channel_id):
        if self.__old_extension:
            return self.__old_extension.get_channel(channel_id)
        else:
            return None

    def __new_channel(self, channel_id):
        if self.__new_extension:
            return self.__new_extension.get_channel(channel_id)
        else:
            return None

    @property
    def __all_channel_ids(self):
        return set(itertools.chain(self.__old_channel_ids, self.__new_channel_ids))

    @property
    def __old_channel_ids(self):
        if self.__old_extension:
            return self.__old_extension.channel_ids
        else:
            return set()

    @property
    def __new_channel_ids(self):
        if self.__new_extension:
            return self.__new_extension.channel_ids
        else:
            return set()


class ContentChannelCompare(object):
    def __init__(self, channel_id, old_channel, new_channel):
        self.__channel_id = channel_id
        self.__old_channel = old_channel
        self.__new_channel = new_channel

    @property
    def channel_id(self):
        return self.__channel_id

    @property
    def added(self):
        return self.__new_channel and not self.__old_channel

    @property
    def removed(self):
        return self.__old_channel and not self.__new_channel

    @property
    def old_include_node_ids(self):
        return self.__old_channel.include_node_ids

    @property
    def new_include_node_ids(self):
        return self.__new_channel.include_node_ids

    @property
    def include_nodes_added(self):
        return self.new_include_node_ids.difference(self.old_include_node_ids)

    @property
    def include_nodes_removed(self):
        return self.old_include_node_ids.difference(self.new_include_node_ids)

    @property
    def old_exclude_node_ids(self):
        return self.__old_channel.exclude_node_ids

    @property
    def new_exclude_node_ids(self):
        return self.__new_channel.exclude_node_ids

    @property
    def exclude_nodes_added(self):
        return self.new_exclude_node_ids.difference(self.old_exclude_node_ids)

    @property
    def exclude_nodes_removed(self):
        return self.old_exclude_node_ids.difference(self.new_exclude_node_ids)
