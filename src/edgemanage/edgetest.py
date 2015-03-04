# stdlib
import urlparse
import hashlib

# local
import const

# external
import requests

class EdgeException(Exception):
    def __init__(self, message, edgetest,
                 fetch_host, fetch_object):
        super(EdgeException, self).__init__(message)
        self.edgename = edgetest.edgename
        self.local_sum = edgetest.local_sum
        self.fetch_host = fetch_host
        self.fetch_object = fetch_object

class FetchFailed(EdgeException):
    def __init__(self, edgetest, fetch_host, fetch_object, reason):
        message = "Failed to fetch %s/%s from %s: %s" % (fetch_host, fetch_object,
                                                         edgetest.edgename, reason)
        super(FetchFailed, self).__init__(message, edgetest,
                                          fetch_host, fetch_object)

class VerifyFailed(EdgeException):
    def __init__(self, edgetest, fetch_host, fetch_object, reason):
        message = "Failed to verify %s/%s from %s: %s != %s" % (
            fetch_host, fetch_object, edgetest.edgename,
            edgetest.local_sum, reason)
        super(VerifyFailed, self).__init__(message, edgetest,
                                          fetch_host, fetch_object)

class EdgeTest(object):

    def __init__(self, edgename, local_sum):
        """
         edgename: FQDN string of the edge to be tested
         local_sum: the pre-computed known checksum of the object to be fetched
        """

        self.edgename = edgename
        self.local_sum = local_sum

    def fetch(self, fetch_host, fetch_object, proto="https"):
        """
         fetch_host: The Host header to use when fetching
         fetch_object: The path to the object to be fetched
        """
        response = requests.get(urlparse.urljoin(proto + "://" + self.edgename,
                                                 fetch_object),
                                verify=False,
                                timeout=const.FETCH_TIMEOUT,
                                headers = {"Host": fetch_host})

        if not response.ok:
            raise FetchFailed(self, fetch_host,
                              fetch_object, response.text)

        remote_hash = hashlib.md5(response.text).hexdigest()
        if remote_hash != self.local_sum:
            raise VerifyFailed(self, fetch_host,
                               fetch_object, remote_hash)

        return response.elapsed.total_seconds()
