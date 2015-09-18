"""Blocking and non-blocking (asynchronous) clients for Linger

Copyright 2015 Jacob Sondergaard
Licensed under the Apache License, Version 2.0
"""

import copy
import functools
import logging
import time

from tornado.gen import coroutine, Future
from tornado.ioloop import IOLoop
from tornado.escape import json_encode, json_decode
from tornado.httpclient import AsyncHTTPClient, HTTPError
from tornado.httputil import url_concat


__all__ = ["AsyncLingerClient", "BlockingLingerClient",
           "AsyncStream", "BlockingStream"]


__version__ = '0.1.0'


clog = logging.getLogger("linger")


class AsyncStream:

    def __init__(self, client, channel, max_retries=0):
        self.client = client
        self.channel = channel
        self.max_retries = max_retries
        self._clear()

    def _inc(self, message=None):
        if self.timeout < 60:
            self.timeout = 2 * self.timeout
        else:
            # wait a minute before re-connecting
            self.timeout = 60
        self.retries = self.retries + 1
        if self.max_retries > 0 and self.retries >= self.max_retries:
            raise HTTPError(code=599, message=message)

    def _clear(self):
        self.timeout = 0.5
        self.retries = 0

    @property
    def closed(self):
        return self.client.closed

    def _wait(self, message):
        f = Future()
        try:
            self._inc(message)
        except Exception as e:
            f.set_exception(e)
        else:
            self.client.io_loop.call_later(
                self.timeout, lambda: f.set_result(None))
        return f

    @coroutine
    def next(self):
        """Get next message from the channel.

        Returns a dict with the message id, body, channel, etc.
        """
        while not self.closed:
            t = time.time()
            msg = None
            try:
                msg = yield self.client._get(self.channel)
            except HTTPError as e:
                s = 'Request error. {}'.format(e)
                clog.debug(s)
                if 300 <= e.code < 500:
                    raise
                else:
                    yield self._wait(s)
            except Exception as e:
                # probably DNS error, or Linger server offline
                s = 'Connection error. {}'.format(e)
                clog.debug(s)
                yield self._wait(s)
                continue

            if msg:
                self._clear()
                return msg

            t = time.time() - t
            if t < 0.1:
                # that's very fast! (probably connection error)
                s = 'Connection dropping fast. Request time: {}s'.format(t)
                clog.debug(s)
                yield self._wait(s)

    def __iter__(self):
        return self

    __next__ = next


class BlockingStream(AsyncStream):

    def __init__(self, client, channel, max_retries=0):
        super().__init__(client, channel, max_retries)

    def next(self):
        return self.client.io_loop.run_sync(super().next)

    __next__ = next


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
            self._url = linger_url
        self._encode = encode
        self._decode = decode
        self._content_type = content_type
        self.io_loop = io_loop or IOLoop.current()
        if 'request_timeout' not in request_args:
            request_args['request_timeout'] = 135.0
        self.request_args = request_args
        self._closed = False
        self._http = AsyncHTTPClient(io_loop)

    def close(self):
        """Closes the Linger client, freeing any resources used."""
        if not self._closed:
            self._http.close()
            self._closed = True

    @property
    def closed(self):
        return self._closed

    def _test_closed(self):
        if self._closed:
            raise RuntimeError('Client is closed.')

    @coroutine
    def channels(self):
        self._test_closed()
        resp = yield self._http.fetch('/'.join([self._url, 'channels']),
                                      **self.request_args)
        return json_decode(resp.body)

    @coroutine
    def post(self, channel, body, **kwargs):
        """Post a message in the channel.

        Accepts keyword arguments for the query parameters: priority, timeout,
        deliver and linger.
        """
        self._test_closed()
        url = url_concat('/'.join([self._url, 'channels', channel]), kwargs)
        data = self._encode(body)
        req_args = copy.deepcopy(self.request_args)
        req_args.setdefault('headers', {}).update(
            {'Content-Type': self._content_type})
        resp = yield self._http.fetch(url, method='POST', body=data,
                                      **req_args)
        return json_decode(resp.body)

    @coroutine
    def get(self, channel, nowait=False):
        """Get a message from the channel.

        Returns the a dict with the message id, body, channel, etc.
        If no message is available, None is returned.

        Set argument `nowait` to True to prevent long-polling.
        """
        self._test_closed()
        url = '/'.join([self._url, 'channels', channel])
        if nowait:
            url = ''.join([url, '?nowait'])
        resp = yield self._http.fetch(url, **self.request_args)
        if not resp.body:
            return None
        msg = {
            'id': int(resp.headers['x-linger-msg-id']),
            'channel': resp.headers['x-linger-channel'],
            'priority': int(resp.headers['x-linger-priority']),
            'timeout': int(resp.headers['x-linger-timeout']),
            'linger': int(resp.headers['x-linger-linger']),
            'deliver': int(resp.headers['x-linger-deliver']),
            'delivered': int(resp.headers['x-linger-delivered']),
            'received': int(resp.headers['x-linger-received']),
            'topic': resp.headers.get('x-linger-topic', ''),
            'body': self._decode(resp.body)
        }
        return msg

    # provide access to the AsyncLingerClient.get in the BlockingLingerClient
    _get = get

    def stream(self, channel, max_retries=0):
        """Get a stream (iterator) for channel.

        Argument max_retries can limit the number of failed reconnection
        attempts. Default is max_retries=0, which means no limit.
        """
        return AsyncStream(self, channel, max_retries)

    @coroutine
    def channel_topics(self, channel):
        """List topics the channel is subscribed to"""
        self._test_closed()
        resp = yield self._http.fetch('/'.join([
            self._url, 'channels', channel, 'topics']),
            **self.request_args)
        return json_decode(resp.body)

    @coroutine
    def channel_subscribe(self, channel, topic, **kwargs):
        """Subscribe channel to topic.

        Accepts keyword arguments for the query parameters: priority, timeout,
        deliver and linger.
        """
        self._test_closed()
        url = url_concat('/'.join([
            self._url, 'channels', channel, 'topics', topic]), kwargs)
        yield self._http.fetch(url, method='PUT', body=b'',
                               **self.request_args)

    @coroutine
    def channel_unsubscribe(self, channel, topic):
        """Unsubscribe channel from topic"""
        self._test_closed()
        yield self._http.fetch('/'.join([
            self._url, 'channels', channel, 'topics', topic]),
            method='DELETE', **self.request_args)

    @coroutine
    def topics(self):
        """List topics"""
        self._test_closed()
        resp = yield self._http.fetch('/'.join([self._url, 'topics']),
                                      **self.request_args)
        return json_decode(resp.body)

    @coroutine
    def publish(self, topic, body):
        """Publish message on topic"""
        self._test_closed()
        data = self._encode(body)
        req_args = copy.deepcopy(self.request_args)
        req_args.setdefault('headers', {}).update(
            {'Content-Type': self._content_type})
        resp = yield self._http.fetch(
            '/'.join([self._url, 'topics', topic]),
            method='POST', body=data, **req_args)
        return json_decode(resp.body)

    @coroutine
    def topic_channels(self, topic):
        """List channels subscribed to topic"""
        self._test_closed()
        resp = yield self._http.fetch('/'.join([
            self._url, 'topics', topic, 'channels']),
            **self.request_args)
        return json_decode(resp.body)

    @coroutine
    def delete(self, msg_id):
        """Delete message"""
        self._test_closed()
        yield self._http.fetch('/'.join([self._url, 'messages', str(msg_id)]),
                               method='DELETE', **self.request_args)

    @coroutine
    def stats(self):
        """Get server stats"""
        self._test_closed()
        resp = yield self._http.fetch('/'.join([self._url, 'stats']),
                                      **self.request_args)
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
        super().__init__(linger_url, encode, decode, content_type, io_loop,
                         **request_args)

    def close(self):
        """Closes the Linger client, freeing any resources used."""
        if not self._closed:
            super().close()
            self.io_loop.close()

    def stream(self, channel, max_retries=0):
        """Get a stream (iterator) for channel.

        Argument max_retries can limit the number of failed reconnection
        attempts. Default is max_retries=0, which means no limit.
        """
        return BlockingStream(self, channel, max_retries)

    def __getattribute__(self, name):
        try:
            attr = object.__getattribute__(self, name)
        except AttributeError:
            raise AttributeError("'{}' object has no attribute '{}'".format(
                                 self.__class__.__name__, name))

        if name in ('close', 'stream') or name.startswith('_') or not hasattr(
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
