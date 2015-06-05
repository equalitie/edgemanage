# stdlib
import urlparse
import hashlib
import logging

# local
import const

# external
import requests

# Make requests stop logging so much. I love you but you need to shut
# up.
requests_log = logging.getLogger("requests")
requests_log.setLevel(logging.WARNING)

USER_AGENT="Edgemanage v2 (https://github.com/equalitie/edgemanage)"

class FetchFailed(Exception):
    def __init__(self, edgetest, fetch_host, fetch_object, reason):
        message = "Failed to fetch %s/%s from %s: %s" % (fetch_host, fetch_object,
                                                         edgetest.edgename, reason)
        super(FetchFailed, self).__init__(message)

        self.edgename = edgetest.edgename
        self.local_sum = edgetest.local_sum
        self.fetch_host = fetch_host
        self.fetch_object = fetch_object

class VerifyFailed(Exception):
    def __init__(self, edgetest, fetch_host, fetch_object, reason):
        message = "Failed to verify %s/%s from %s: %s != %s" % (
            fetch_host, fetch_object, edgetest.edgename,
            edgetest.local_sum, reason)
        super(VerifyFailed, self).__init__(message)

        self.edgename = edgetest.edgename
        self.local_sum = edgetest.local_sum
        self.fetch_host = fetch_host
        self.fetch_object = fetch_object


class EdgeTest(object):

    def __init__(self, edgename, local_sum):
        """
         edgename: FQDN string of the edge to be tested
         local_sum: the pre-computed known checksum of the object to be fetched
        """

        self.edgename = edgename
        self.local_sum = local_sum

    def fetch(self, fetch_host, fetch_object, proto="https", verify=False):
        """
         fetch_host: The Host header to use when fetching
         fetch_object: The path to the object to be fetched
        """
        try:
            response = requests.get(urlparse.urljoin(proto + "://" + self.edgename,
                                                     fetch_object),
                                    verify=verify,
                                    timeout=const.FETCH_TIMEOUT,
                                    headers = {"Host": fetch_host,
                                               "User-Agent": USER_AGENT})
        except requests.exceptions.Timeout as e:
            # Just assume it took the maximum amount of time
            return const.FETCH_TIMEOUT
        except requests.exceptions.ConnectionError as e:
            logging.error("Connection error when fetching from %s: %s", self.edgename, str(e))
            for i in range(const.FETCH_RETRY-1):
                logging.warning("Retrying connection to %s", self.edgename)
                try:
                    response = requests.get(urlparse.urljoin(proto + "://" + self.edgename,
                                                             fetch_object),
                                            verify=False,
                                            timeout=const.FETCH_TIMEOUT,
                                            headers = {"Host": fetch_host})
                    # Request was successful, stop retrying and
                    # continue
                    break
                except requests.exceptions.ConnectionError as e:
                    continue
            else:
                logging.error("Failed to connect to %s after retrying %d times",
                              self.edgename, const.FETCH_RETRY)
                # The loop finished without a break - we got more
                # connection errors. Let's bail and return the maximum
                # amount of time. for/else is weird.
                return const.FETCH_TIMEOUT

        if not response.ok:
            logging.error("Object fetch failed on %s", self.edgename)
            raise FetchFailed(self, fetch_host,
                              fetch_object, response.text)

        remote_hash = hashlib.md5(response.content).hexdigest()

        if remote_hash != self.local_sum:
            logging.error("Failed to verify hash on %s!!", self.edgename)
            raise VerifyFailed(self, fetch_host,
                               fetch_object, remote_hash)

        return response.elapsed.total_seconds()
