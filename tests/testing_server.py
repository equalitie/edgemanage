#!/usr/bin/env python
"""
Simple HTTP server to serve content with a variable response per host
"""
import os
import time
import yaml
import logging
import argparse

from flask import Flask, request, Response, url_for, send_file
from werkzeug.serving import BaseWSGIServer

# Disable Flask logger except for error messages
logging.getLogger('werkzeug').setLevel(logging.ERROR)

handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter(fmt="%(asctime)s [%(levelname)s]: %(message)s")
)
logger = logging.getLogger('test_server')
logger.addHandler(handler)
logger.setLevel(logging.INFO)

app = Flask(__name__)


@app.after_request
def disable_cache_headers(response):
    """
    Disable caching for all endpoints
    """
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Pragma"] = "no-cache"
    return response


def get_edge_from_ip(host_address):
    """
    Extract the final octet of the host IP address to use as the edge ID.
    """
    host_ip = host_address.split(':')[0]
    edge_id = int(host_ip.split('.')[-1])
    try:
        return edge_id, app.config['EDGES'][edge_id]
    except KeyError:
        return edge_id, None


@app.route('/')
def index():
    return Response(
        "Edgemange V2 testing server. The test object is at {}".format(
            url_for('serve_test_object')))


@app.route('/test_object')
def serve_test_object():
    """
    Serve the EdgeManage test object.
    """
    edge_id, edge = get_edge_from_ip(request.host)
    if not edge:
        logger.info("Request for unknown edge %d", edge_id)
        return Response('404: {} is not a valid edge ID'.format(edge_id)), 404

    delay = edge.get('delay', 0)
    logger.info("Serving edge %d after a %d second delay", edge_id, delay)

    time.sleep(delay)
    return send_file(app.config['TEST_OBJECT'])


def get_request_monkeypatch(self):
    """
    Monkeypatch get_request() on the Werkzeug WSGI server

    This method will reject connections to the socket for edges which are "offline".
    The approach is hacky, but it shouldn't be a problem as the Werkzeug interface is
    pretty stable.
    """
    con, info = self.socket.accept()
    edge_id, edge = get_edge_from_ip(con.getsockname()[0])

    # Close the client socket if this edge should be offline.
    if edge and edge.get('offline'):
        logger.info("Closing connection for offline edge %d.", edge_id)
        con.close()
    return con, info


def is_valid_file(filename):
    """
    Type for argparse to check that a file exists.
    """
    if not os.path.exists(filename):
        raise argparse.ArgumentTypeError("{0} does not exist".format(filename))
    return filename


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Run slow web servers for testing EdgeManage under conditions '
        'of high network load and poor edge availability.'
    )
    parser.add_argument('--edge-config', type=is_valid_file,
                        default='test_server_configs/default.yaml',
                        help='YAML file describing the test edges and their delays '
                        '(default: %(default)s).')
    parser.add_argument('--test-object', type=is_valid_file,
                        default='test_data/edge_test_object.txt',
                        help='Test file to server from the edge / canary '
                        '(default: %(default)s).')
    args = parser.parse_args()

    with open(args.edge_config) as config_file:
        config = yaml.safe_load(config_file.read())
        logger.info("Loaded %d edges/canaries from config '%s'.",
                    len(config['edge_list']), args.edge_config)

    # Monkeypatch WSGI to allow rejecting connections early at the socket level.
    BaseWSGIServer.get_request = get_request_monkeypatch

    app.config['EDGES'] = config['edge_list']
    app.config['TEST_OBJECT'] = args.test_object

    logger.info("Test server running")
    app.run(host='0.0.0.0', threaded=True)
