#!/usr/bin/python3

# Displays a loading screen, and then redirects to Kolibri once it is
# responding. Stops automatically if it does not receive a request after a
# certain amount of time.

import http.server
import socketserver
import threading
import time

from kolibri.utils import server
from urllib.parse import urlparse, parse_qs, quote

from .utils import KOLIBRI_URL, get_singleton_service, get_is_kolibri_responding


WWW_DIR = '/app/www'

KOLIBRI_REDIRECT_IDLE_TIMEOUT_SECS = 60


class KolibriRedirectThread(threading.Thread):
    def __init__(self):
        self.__running = None

        self.__redirect_server = socketserver.TCPServer(("", 0), RedirectHandler)
        self.__redirect_server.last_heartbeat = time.time()

        self.__redirect_server_thread = threading.Thread(
            target=self.__redirect_server.serve_forever
        )

        sockname = self.__redirect_server.socket.getsockname()
        self.__redirect_server_port = sockname[1]

        self.__start_event = threading.Event()

        super().__init__()

    @property
    def redirect_server_port(self):
        return self.__redirect_server_port

    def get_idle_seconds(self):
        return time.time() - self.__redirect_server.last_heartbeat

    def await_started(self):
        self.__start_event.wait()
        time.sleep(1)

    def start(self):
        self.__running = True
        self.__redirect_server_thread.start()
        self.__start_event.set()
        super().start()

    def stop(self):
        self.__running = False
        self.join()
        self.__start_event.clear()

    def run(self):
        while self.__running:
            time.sleep(5)

            idle_seconds = self.get_idle_seconds()

            print("Redirect server: last heartbeat was {} seconds ago...".format(idle_seconds))

            if idle_seconds > KOLIBRI_REDIRECT_IDLE_TIMEOUT_SECS:
                print("Redirect server: Stopping...")
                self.__redirect_server.shutdown()
                self.__running = False


class RedirectHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        kwargs['directory'] = WWW_DIR
        super().__init__(*args, **kwargs)

    def do_GET(self):
        self.server.last_heartbeat = time.time()

        url = urlparse(self.path)

        if url.path == '/' or url.path == '/poll':
            is_kolibri_responding = get_is_kolibri_responding()
            # if not is_kolibri_responding:
            #     # kolibri_started, kolibri_state = get_singleton_service('kolibri')
            #     # if kolibri_started:
            #     #     print("Error: Kolibri appears to be started, but not responding.")
            #     #     print("It is responding at '{}'. We expect it to be at '{}'.".format(
            #     #         kolibri_state, KOLIBRI_URL
            #     #     ))
        else:
            is_kolibri_responding = None

        if url.path == '/' and is_kolibri_responding:
            next_path = parse_qs(url.query).get('next', [''])[0]
            return self.redirect_response(next_path)
        elif url.path == '/poll':
            return self.poll_response(is_kolibri_responding)
        else:
            return super().do_GET()

    def poll_response(self, is_kolibri_responding):
        self.send_response(200)

        if is_kolibri_responding:
            self.send_header("X-Kolibri-Ready", "1")
            self.send_header("X-Kolibri-Location", KOLIBRI_URL)
        else:
            self.send_header("X-Kolibri-Starting", "1")

        self.end_headers()

    def redirect_response(self, redirect_path):
        redirect_url = "{}{}".format(KOLIBRI_URL, redirect_path)
        self.send_response(302)
        self.send_header("Location", redirect_url)
        self.end_headers()
