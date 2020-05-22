# Kolibri flatpak wrapper script.
# Discovers content extension directories, sets KOLIBRI_CONTENT_FALLBACK_DIRS
# accordingly, and runs scanforcontent when content extensions have changed.

import logging

logger = logging.getLogger(__name__)

import datetime
import operator
import os
import subprocess
import sys

from kolibri_gnome.globals import init_logging

from .content_extensions import ContentExtensionsList

KOLIBRI = "/app/libexec/kolibri"


class Application(object):
    def __init__(self):
        self.__cached_extensions = ContentExtensionsList.from_cache()
        self.__active_extensions = ContentExtensionsList.from_flatpak_info()

    def run(self):
        process_success = all(
            [
                self.__process_removed_extensions(),
                self.__process_added_extensions(),
                self.__process_updated_extensions(),
            ]
        )

        if process_success:
            self.__active_extensions.write_to_cache()

        return self.__run_kolibri()

    def __process_removed_extensions(self):
        # For each removed channel, run scanforcontent
        # TODO: Is there a less expensive way of doing this than scanforcontent?
        channel_ids = set()
        for extension in ContentExtensionsList.removed(
            self.__cached_extensions, self.__active_extensions
        ):
            logging.info("Removed extension: %s", extension.ref)
            channel_ids.update(
                map(operator.attrgetter("channel_id"), extension.channels)
            )
        return self.__kolibri_scan_content(channel_ids, ["--channel-import-mode=none"])

    def __process_added_extensions(self):
        # For each added channel, run scanforcontent
        # TODO: Instead of scanforcontent, use importcontent with --node_ids and --exclude_node_ids
        channel_ids = set()
        for extension in ContentExtensionsList.added(
            self.__cached_extensions, self.__active_extensions
        ):
            logging.info("Added extension: %s", extension.ref)
            channel_ids.update(
                map(operator.attrgetter("channel_id"), extension.channels)
            )
        return self.__kolibri_scan_content(channel_ids)

    def __process_updated_extensions(self):
        # For each updated channel, run scanforcontent
        # TODO: Instead of scanforcontent, use importcontent with --node_ids and --exclude_node_ids
        channel_ids = set()
        for extension in ContentExtensionsList.updated(
            self.__cached_extensions, self.__active_extensions
        ):
            logging.info("Updated extension: %s", extension.ref)
            channel_ids.update(
                map(operator.attrgetter("channel_id"), extension.channels)
            )
        return self.__kolibri_scan_content(channel_ids)

    def __kolibri_scan_content(self, channel_ids, args=[]):
        if len(channel_ids) == 0:
            return True

        logger.info(
            "scanforcontent starting for channels %s: %s",
            channel_ids,
            datetime.datetime.today(),
        )

        try:
            self.__run_kolibri(
                [
                    "manage",
                    "scanforcontent",
                    "--channels={}".format(",".join(channel_ids)),
                    *args,
                ]
            )
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
        kolibri_env["KOLIBRI_CONTENT_FALLBACK_DIRS"] = ";".join(
            self.__active_extensions.content_fallback_dirs
        )
        return kolibri_env


def main():
    init_logging("kolibri-flatpak-wrapper.txt")
    application = Application()
    return application.run()
