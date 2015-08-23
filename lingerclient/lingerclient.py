"""Blocking and non-blocking (asynchronous) clients for Linger

Copyright 2015 Jacob Sondergaard
Licensed under the Apache License, Version 2.0
"""

import functools

from tornado.gen import coroutine
from tornado.ioloop import IOLoop
from tornado.escape import json_encode, json_decode
from tornado.httpclient import AsyncHTTPClient


__all__ = ["AsyncLingerClient", "BlockingLingerClient"]


__version__ = '0.1.0'


class AsyncLingerClient:
    """Basic wrapper class for making asynchronous requests to Linger.

    Example usage::

        import lingerclient
        from tornado import ioloop, gen

        @gen.coroutine
        def run_test():
            lc = lingerclient.AsyncLingerClient()
            r = yield lc.post('test-channel', {'msg': 'My first message'})
            print(r)
            r = yield lc.channels()
            print(r)
            m = yield lc.get('test-channel')
            yield lc.delete(m['id'])

        ioloop.IOLoop.current().run_sync(run_test)

    For any methods of this class: If there is a communication error, or an
    error is returned from Linger, the appropriate tornado.web.HTTPError
    is raised at the callpoint.
    """

    def __init__(self, linger_url='http://127.0.0.1:8989/', encode=json_encode,
                 decode=json_decode, content_type='application/json',
                 io_loop=None, **request_args):
        """Creates an `AsyncLingerClient`.

        All parameters are optional.

        The `linger_url` argument is the base url for the Linger server.
        Default is `http://127.0.0.1:8989/`.

        The `encode` and `decode` arguments are for supplying custom message
        encoding and decoding functions. Default is JSON encoding/decoding.

        The `content_type` argument should be set to the appropriate mime-type
        of the output of the encoding function. Default is `application/json`.

        The `io_loop` is passed to the AsyncHTTPClient, used for connecting.

        Keyword arguments in `request_args` are applied when making requests
        to Linger. By default the request argument `use_gzip` is True.
        Accessing a local Linger server, it may be relevant to set `use_gzip`
        to False.

        The request arguments may include `auth_username` and `auth_password`
        for basic authentication. See `tornado.httpclient.HTTPRequest` for
        other possible arguments.
        """
        if linger_url.endswith('/'):
            self._url = linger_url.rstrip('/')
        else:
            self.url = linger_url
        self._encode = encode
        self._decode = decode
        self._content_type = content_type
        self.io_loop = io_loop
        self._closed = False
        self._http = AsyncHTTPClient(io_loop)

    def close(self):
        """Closes the Linger client, freeing any resources used."""
        if not self._closed:
            self._client.close()
            self._closed = True

    @coroutine
    def channels(self):
        resp = yield self._http.fetch('/'.join([self._url, 'channels']))
        return json_decode(resp.body)

    @coroutine
    def post(self, channel, body):
        """Post a message in the channel."""
        data = self._encode(body)
        resp = yield self._http.fetch(
            '/'.join([self._url, 'channels', channel]),
            headers={'Content-Type': self._content_type},
            method='POST', body=data)
        return json_decode(resp.body)

    @coroutine
    def get(self, channel, pick=False):
        """Get a message from the channel.

        Returns the a dict with the message id, body, channel, etc.
        If no message is available, None is returned.

        Set argument `pick` to True to prevent prevent long-polling.
        """
        url = '/'.join([self._url, 'channels', channel])
        if pick:
            url = ''.join([url, '?pick'])
        resp = yield self._http.fetch(url)
        if not resp.body:
            return None
        msg = {
            'id': resp.headers['x-linger-msg-id'],
            'channel': resp.headers['x-linger-channel'],
            'priority': resp.headers['x-linger-priority'],
            'timeout': resp.headers['x-linger-timeout'],
            'linger': resp.headers['x-linger-linger'],
            'deliver': resp.headers['x-linger-deliver'],
            'delivered': resp.headers['x-linger-delivered'],
            'received': resp.headers['x-linger-received'],
            'topic': resp.headers.get('x-linger-topic', ''),
            'body': self._decode(resp.body)
        }
        return msg

    @coroutine
    def channel_topics(self, channel):
        """List topics the channel is subscribed to"""
        resp = yield self._http.fetch('/'.join([
            self._url, 'channels', channel, 'topics']))
        return json_decode(resp.body)

    @coroutine
    def channel_subscribe(self, channel, topic):
        """Subscribe channel to topic"""
        yield self._http.fetch('/'.join([
            self._url, 'channels', channel, 'topics', topic]),
            method='PUT')

    @coroutine
    def channel_unsubscribe(self, channel, topic):
        """Unsubscribe channel from topic"""
        yield self._http.fetch('/'.join([
            self._url, 'channels', channel, 'topics', topic]),
            method='DELETE')

    @coroutine
    def topics(self):
        """List topics"""
        resp = yield self._http.fetch('/'.join([self._url, 'topics']))
        return json_decode(resp.body)

    @coroutine
    def publish(self, topic, body):
        """Publish message on topic"""
        data = self._encode(body)
        resp = yield self._http.fetch(
            '/'.join([self._url, 'topics', topic]),
            headers={'Content-Type': self._content_type},
            method='POST', body=data)
        return json_decode(resp.body)

    @coroutine
    def topic_channels(self, topic):
        """List channels subscribed to topic"""
        resp = yield self._http.fetch('/'.join([
            self._url, 'topics', topic, 'channels']))
        return json_decode(resp.body)

    @coroutine
    def delete(self, msg_id):
        """Delete message"""
        yield self._http.fetch('/'.join([self._url, 'messages', str(msg_id)]),
                               method='DELETE')

    @coroutine
    def stats(self, topic):
        """Get server stats"""
        resp = yield self._http.fetch('/'.join([self._url, 'stats']))
        return json_decode(resp.body)


class BlockingLingerClient(AsyncLingerClient):
    """Basic wrapper class for making blocking requests to Linger.

    Example usage::

        import lingerclient

        lc = lingerclient.BlockingLingerClient()
        r = lc.post('test-channel', {'msg': 'My first message'})
        print(r)
        print(lc.channels())
        m = lc.get('test-channel')
        lc.delete(m['id'])

    For any methods of this class: If there is a communication error, or an
    error is returned from Linger, the appropriate tornado.web.HTTPError
    is raised.

    BlockingLingerClient is a wrapper for AsyncLingerClient, http requests to
    Linger are run in a seperate IOLoop.
    """

    def __init__(self, linger_url='http://127.0.0.1:8989/', encode=json_encode,
                 decode=json_decode, content_type='application/json',
                 io_loop=None, **request_args):
        """Creates a `BlockingLingerClient`.

        All parameters are optional.

        Keyword arguments in `request_args` are applied when making requests
        to Linger. By default the request argument `use_gzip` is True.
        Accessing a local Linger server, it may be relevant to set `use_gzip`
        to False.

        The request arguments may include `auth_username` and `auth_password`
        for basic authentication. See `tornado.httpclient.HTTPRequest` for
        other possible arguments.
        """

        io_loop = IOLoop(make_current=False)
        AsyncLingerClient.__init__(self, linger_url, encode, decode,
                                   content_type, io_loop, **request_args)

    def close(self):
        """Closes the Linger client, freeing any resources used."""
        if not self._closed:
            AsyncLingerClient.close(self)
            self.io_loop.close()

    def __getattribute__(self, name):
        try:
            attr = object.__getattribute__(self, name)
        except AttributeError:
            raise AttributeError("'{}' object has no attribute '{}'".format(
                                 self.__class__.__name__, name))

        if name == 'close' or name.startswith('_') or not hasattr(
                attr, '__call__'):
            # a 'local' or internal attribute, or a non-callable
            return attr

        # it's an asynchronous callable
        # return a callable wrapper for the attribute that will
        # run in its own IOLoop
        def wrapper(clb, *args, **kwargs):
            fn = functools.partial(clb, *args, **kwargs)
            return self.io_loop.run_sync(fn)
        return functools.partial(wrapper, attr)
