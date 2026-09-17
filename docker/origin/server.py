#!/usr/bin/env python3

"""
A deliberately dumb origin server used to stand in for an edge (or a canary) in
the local Docker harness.

Serves the edgemanage test object at any path. Behaviour is driven entirely by
environment variables, read on every request so that a compose file edit plus a
container restart is all that is needed to change how an edge behaves:

 EDGE_NAME  label used in log lines (default: the hostname)
 DELAY      float seconds to sleep before responding (default: 0)
 MODE       ok      - serve the test object (default)
            500     - return a 500, triggering FetchFailed in edgetest
            corrupt - serve different bytes, triggering VerifyFailed
            hang    - sleep past const.FETCH_TIMEOUT so the fetch times out
            close   - drop the connection, exercising the FETCH_RETRY loop
 PORT       port to listen on (default: 80)
 OBJECT     path to the test object (default: /srv/myobject.edgemanage)
"""

import os
import socket
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_OBJECT = "/srv/myobject.edgemanage"
CORRUPT_BODY = b"this is not the object you are looking for\n"
# Longer than const.FETCH_TIMEOUT (10) so that "hang" reliably times out.
HANG_SECONDS = 30


def env(name, default):
    value = os.environ.get(name)
    return value if value else default


def log(message, *args):
    edge_name = env("EDGE_NAME", socket.gethostname())
    sys.stderr.write("[%s] %s\n" % (edge_name, message % args))
    sys.stderr.flush()


class OriginHandler(BaseHTTPRequestHandler):

    # Keep our own log format - the default one writes to stderr with a
    # timestamp we don't need and no Host header, which is the interesting bit.
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        mode = env("MODE", "ok")
        delay = float(env("DELAY", "0"))

        log("GET %s Host=%s UA=%s mode=%s delay=%s",
            self.path, self.headers.get("Host"),
            self.headers.get("User-Agent"), mode, delay)

        if mode == "close":
            log("closing connection without responding")
            self.close_connection = True
            try:
                self.connection.close()
            except OSError:
                pass
            return

        if mode == "hang":
            time.sleep(HANG_SECONDS)
        elif delay:
            time.sleep(delay)

        if mode == "500":
            self.respond(500, b"deliberate failure\n")
            return

        if mode == "corrupt":
            self.respond(200, CORRUPT_BODY)
            return

        object_path = env("OBJECT", DEFAULT_OBJECT)
        try:
            with open(object_path, "rb") as object_f:
                body = object_f.read()
        except OSError as e:
            log("could not read test object %s: %s", object_path, e)
            self.respond(500, b"test object missing\n")
            return

        self.respond(200, body)

    def respond(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    port = int(env("PORT", "80"))
    log("origin listening on port %d, serving %s", port, env("OBJECT", DEFAULT_OBJECT))
    ThreadingHTTPServer(("0.0.0.0", port), OriginHandler).serve_forever()
