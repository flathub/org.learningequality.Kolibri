#!/usr/bin/python3

import fcntl
import io
import os
import socket
import subprocess
import urllib.request

from contextlib import contextmanager
from urllib.error import URLError


XDG_DATA_HOME = os.environ.get('XDG_DATA_HOME', None)

KOLIBRI_IDLE_TIMEOUT_MINS = int(os.environ.get("KOLIBRI_IDLE_TIMEOUT_MINS", 60))
KOLIBRI_IDLE_TIMEOUT_SECS = KOLIBRI_IDLE_TIMEOUT_MINS * 60

KOLIBRI_HTTP_PORT = int(os.environ.get("KOLIBRI_HTTP_PORT", 8080))
KOLIBRI_URL = "http://127.0.0.1:{}".format(KOLIBRI_HTTP_PORT)


@contextmanager
def singleton_service(service='kolibri', state=''):
    # Ensures that only a single copy of a service is running on the system,
    # including in different containers.
    lockfile_path = os.path.join(XDG_DATA_HOME, "{}.lock".format(service))
    with open(lockfile_path, "w") as lockfile:
        with _flocked(lockfile):
            lockfile.write(state)
            lockfile.flush()
            yield


def get_singleton_service(service):
    lockfile_path = os.path.join(XDG_DATA_HOME, "{}.lock".format(service))

    try:
        lockfile = open(lockfile_path, "r")
    except OSError:
        state = None
        is_started = False
    else:
        state = lockfile.read()
        try:
            with _flocked(lockfile):
                pass
        except io.BlockingIOError:
            is_started = True
        else:
            is_started = False

    return is_started, state


def is_kolibri_socket_open():
    with socket.socket() as sock:
        return sock.connect_ex(("127.0.0.1", KOLIBRI_HTTP_PORT)) == 0


def get_is_kolibri_responding():
    # Check if Kolibri is responding to http requests at the provided URL.

    # TODO: It would be nice to have a status API we can query to confirm this
    #       is indeed Kolibri.

    try:
        result = urllib.request.urlopen('{}/api/auth'.format(KOLIBRI_URL))
    except URLError:
        return False
    else:
        return result.status == 200


def get_kolibri_running_tasks():
    return subprocess.run("/app/bin/check_for_running_tasks.sh").returncode


@contextmanager
def _flocked(fd):
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
