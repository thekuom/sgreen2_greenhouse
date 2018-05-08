import json
import threading
from typing import Optional

import requests
from requests import Response


class RestThread(threading.Thread):
    """
    A class used to easily send asynchronous calls to the REST API. After constructing the call,
    the response can be read with the response property.
    """

    def __init__(self, url: str, method: str, params: Optional[dict], data: Optional[str], headers: Optional[dict]):
        """
        The generic constructor for any REST method
        :param url: the url for the request
        :param method: the method of the request
        :param params: the url parameters to send
        :param data: the json stringified data to send in the body
        :param headers: any headers for the request
        """
        threading.Thread.__init__(self)
        self.url = url
        self.method = method
        self.params = params
        self.data = data
        self.headers = headers
        self.response = {}

    def run(self):
        """
        Makes the REST API call
        :return: None
        """
        self.response = RestRequest.send(url=self.url, method=self.method, params=self.params, data=self.data,
                                         headers=self.headers)


class RestRequest:
    @staticmethod
    def send(url: str, method: str, params: Optional[dict], data: Optional[str], headers: Optional[dict]) -> Response:
        return requests.request(method, url, params=params, data=data, headers=headers, timeout=2)


class RestGetThread(RestThread):
    """
    For GET requests
    """

    def __init__(self, url: str, params: Optional[dict]):
        """
        Constructs a RestThread with a GET method
        :param url: the url of the request
        :param params: a dictionary of url parameters
        """
        RestThread.__init__(self, url=url, method="get", params=params, data=None,
                            headers={"content-type": "application/json"})


class RestGet:
    @staticmethod
    def send(url: str, params: Optional[dict]) -> Response:
        return RestRequest.send(url=url, method="get", params=params, data=None,
                                headers={"content-type": "application/json"})


class RestPostThread(RestThread):
    """
    For POST requests
    """

    def __init__(self, url: str, data: Optional[dict]):
        """
        Constructs a RestThread with a POST method
        :param url: the url of the request
        :param data: a dictionary of data to send in the body
        """
        RestThread.__init__(self, url=url, method="post", params=None, data=json.dumps(data),
                            headers={"content-type": "application/json"})


class RestPost:
    @staticmethod
    def send(url: str, data: Optional[dict]) -> Response:
        return RestRequest.send(url=url, method="post", params=None, data=json.dumps(data),
                                headers={"content-type": "application/json"})


class RestPutThread(RestThread):
    """
    For PUT requests
    """

    def __init__(self, url: str):
        """
        Constructs a RestThread with a PUT method
        :param url: the url of the request
        """
        RestThread.__init__(self, url=url, method="put", params=None, data=None,
                            headers={"content-type": "application/json", "content-length": "0"})


class RestPut:
    @staticmethod
    def send(url: str) -> Response:
        return RestRequest.send(url=url, method="put", params=None, data=None,
                                headers={"content-type": "application/json", "content-length": "0"})


class RestDeleteThread(RestThread):
    """
    For DELETE requests
    """

    def __init__(self, url: str):
        """
        Constructs a RestThread with a DELETE method
        :param url: the url of the request
        """
        RestThread.__init__(self, url=url, method="delete", params=None, data=None,
                            headers={"content-type": "application/json"})


class RestDelete:
    @staticmethod
    def send(url: str) -> Response:
        return RestRequest.send(url=url, method="delete", params=None, data=None,
                                headers={"content-type": "application/json"})
