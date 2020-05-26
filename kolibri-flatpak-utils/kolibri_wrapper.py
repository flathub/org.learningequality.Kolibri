# Kolibri flatpak wrapper script.
# Discovers content extension directories, sets KOLIBRI_CONTENT_FALLBACK_DIRS
# accordingly, and runs scanforcontent when content extensions have changed.

import logging

logger = logging.getLogger(__name__)

import os
import subprocess
import sys

from kolibri_gnome.globals import KOLIBRI_HOME, init_logging

from .content_extensions import ContentExtensionsList

KOLIBRI = "/app/libexec/kolibri"


class KolibriContentOperation(object):
    def apply(self, run_kolibri_fn):
        raise NotImplementedError()

    @classmethod
    def from_channel_compare(cls, channel_compare):
        if channel_compare.added:
            logger.info("Channel added %s", channel_compare.channel_id)
            logger.info("include_node_ids %s", channel_compare.new_include_node_ids)
            logger.info("exclude_node_ids %s", channel_compare.new_exclude_node_ids)
            yield KolibriContentOperation_ImportChannel(
                channel_id=channel_compare.channel_id
            )
            yield KolibriContentOperation_ImportContent(
                channel_id=channel_compare.channel_id,
                include_node_ids=channel_compare.new_include_node_ids,
                exclude_node_ids=channel_compare.new_exclude_node_ids
            )
        elif channel_compare.removed:
            logger.info("Channel removed %s", channel_compare.channel_id)
            yield KolibriContentOperation_RescanContent(
                channel_id=channel_compare.channel_id,
                removed=True
            )
        elif channel_compare.exclude_nodes_added:
            # We need to rescan all content in the channel
            # TODO: Find a way to provide old_exclude_node_ids to
            #       Kolibri instead of scanning all content.
            logger.info("Channel update (exclude_nodes_added) %s", channel_compare.channel_id)
            yield KolibriContentOperation_RescanContent(
                channel_id=channel_compare.channel_id
            )
        elif channel_compare.include_nodes_removed:
            # We need to rescan all content in the channel
            # TODO: Find a way to provide old_include_node_ids to
            #       Kolibri instead of scanning all content.
            logger.info("Channel update (include_nodes_removed) %s", channel_compare.channel_id)
            yield KolibriContentOperation_RescanContent(
                channel_id=channel_compare.channel_id
            )
        else:
            # Channel content updated, no content removed
            # We can handle this case efficiently with importcontent
            logger.info("Channel update (good) %s", channel_compare.channel_id)
            logger.info("include_node_ids %s", channel_compare.new_include_node_ids)
            logger.info("exclude_node_ids %s", channel_compare.new_exclude_node_ids)
            yield KolibriContentOperation_ImportContent(
                channel_id=channel_compare.channel_id,
                include_node_ids=channel_compare.new_exclude_node_ids,
                exclude_node_ids=channel_compare.new_include_node_ids
            )


class KolibriContentOperation_ImportChannel(KolibriContentOperation):
    def __init__(self, channel_id):
        self.__channel_id = channel_id

    def apply(self, run_kolibri_fn):
        logger.info("Running importchannel for %s", self.__channel_id)
        return run_kolibri_fn("manage", "importchannel", "disk", self.__channel_id, KOLIBRI_HOME)


class KolibriContentOperation_ImportContent(KolibriContentOperation):
    def __init__(self, channel_id, include_node_ids, exclude_node_ids):
        self.__channel_id = channel_id
        self.__include_node_ids = include_node_ids
        self.__exclude_node_ids = exclude_node_ids

    def apply(self, run_kolibri_fn):
        logger.info("Running importcontent for %s", self.__channel_id)
        nodes_args = []
        for include_node_id in self.__include_node_ids:
            nodes_args.extend(['--node_ids', include_node_id])
        for exclude_node_id in self.__exclude_node_ids:
            nodes_args.extend(['--exclude_node_ids', exclude_node_id])
        return run_kolibri_fn("manage", "importcontent", *nodes_args, "disk", self.__channel_id, KOLIBRI_HOME)


class KolibriContentOperation_RescanContent(KolibriContentOperation):
    def __init__(self, channel_id, removed=False):
        self.__channel_id = channel_id
        self.__removed = removed


    def apply(self, run_kolibri_fn):
        logger.info("Running scanforcontent for %s", self.__channel_id)
        args = []
        if self.__removed:
            args.append("--channel-import-mode=none")
        return run_kolibri_fn("manage", "scanforcontent", "--channels={}".format(self.__channel_id), *args)


class Application(object):
    def __init__(self):
        self.__cached_extensions = ContentExtensionsList.from_cache()
        self.__active_extensions = ContentExtensionsList.from_flatpak_info()

    def run(self):
        success = all(
            operation.apply(self.__run_kolibri) == 0
            for operation in self.__iter_content_operations()
        )

        if success:
            self.__active_extensions.write_to_cache()

        args = sys.argv[1:]
        return self.__run_kolibri(*args)

    def __iter_content_operations(self):
        for extension_compare in ContentExtensionsList.compare(self.__cached_extensions, self.__active_extensions):
            for channel_compare in extension_compare.compare_channels():
                yield from KolibriContentOperation.from_channel_compare(channel_compare)

    @property
    def __kolibri_env(self):
        kolibri_env = os.environ.copy()
        kolibri_env["KOLIBRI_CONTENT_FALLBACK_DIRS"] = ";".join(
            extension.content_dir for extension in self.__active_extensions
        )
        return kolibri_env

    def __run_kolibri(self, *args):
        logger.info("run_kolibri %s", args)
        result = subprocess.run([KOLIBRI, *args], env=self.__kolibri_env, check=True)
        return result.returncode


def main():
    init_logging("kolibri-flatpak-wrapper.txt")
    application = Application()
    return application.run()
