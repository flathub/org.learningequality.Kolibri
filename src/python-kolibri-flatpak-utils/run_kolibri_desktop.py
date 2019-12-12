#!/usr/bin/python3

import subprocess

from .kolibri_redirect import KolibriRedirectThread
from .utils import is_kolibri_socket_open


def kolibri_desktop_main(path='/'):
    if is_kolibri_socket_open():
        return _run_desktop(path)
    else:
        return _run_desktop_and_service(path)


def _run_desktop(path):
    kolibri_redirect = KolibriRedirectThread()

    kolibri_redirect.start()

    kolibri_redirect.await_started()

    kolibri_redirect_url = "http://127.0.0.1:{port}/?next={path}".format(
        port=kolibri_redirect.redirect_server_port,
        path=path
    )
    result = subprocess.run(['xdg-open', kolibri_redirect_url])

    if result.returncode == 0:
        kolibri_redirect.join()
    else:
        kolibri_redirect.stop()

    return result.returncode


def _run_desktop_and_service(path):
    # Start our own Kolibri instances

    from .kolibri_idle_monitor import KolibriIdleMonitorThread
    from .kolibri_service import KolibriServiceThread

    kolibri_idle_monitor = KolibriIdleMonitorThread()
    kolibri_service = KolibriServiceThread(
        heartbeat_port=kolibri_idle_monitor.idle_monitor_port
    )
    kolibri_idle_monitor.set_kolibri_service(kolibri_service)

    kolibri_redirect = KolibriRedirectThread()
    
    kolibri_idle_monitor.start()
    kolibri_service.start()
    kolibri_redirect.start()

    kolibri_redirect.await_started()

    kolibri_redirect_url = "http://127.0.0.1:{port}/?next={path}".format(
        port=kolibri_redirect.redirect_server_port,
        path=path
    )
    result = subprocess.run(['xdg-open', kolibri_redirect_url])

    if result.returncode == 0:
        kolibri_service.join()
    else:
        kolibri_service.stop()

    kolibri_redirect.stop()
    kolibri_idle_monitor.stop()

    if result.returncode == 0:
        return kolibri_service.kolibri_exitcode
    else:
        return result.returncode
