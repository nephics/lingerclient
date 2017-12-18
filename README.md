# Lingerclient

*-- Blocking and non-blocking (asynchronous) clients for Linger*

This package provides Python clients for interacting with a [Linger](https://github.com/nephics/linger) server, which is a message queue and pubsub service with a REST HTTP API.

The linger clients are implemented in Python 3 using [Tornado](http://www.tornadoweb.org/) HTTP clients.

## Install

Install the `lingerclient` package with the following pip command:

    pip install https://github.com/nephics/lingerclient/archive/master.zip

This will also ensure that the dependency package `tornado` is installed.

## Example code

*Blocking client example:*

    import lingerclient

	lc = lingerclient.BlockingLingerClient()
	r = lc.post('test-channel', {'msg': 'My first message'})
	print(r)
	print(lc.channels())
	m = lc.get('test-channel')
	lc.delete(m['id'])

The `stream` method can be used for iterating over a stream from a channel:

    for m in lc.stream('test-channel'):
        print(m['body'])
        lc.delete(m['id'])

*Async client example:*

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


## Main client methods

**`channels()`**  
List active channels

**`post(channel, body, **kwargs)`**  
Post a message in the channel. Accepts keyword arguments for the query parameters: priority, timeout, deliver and linger.


**`get(channel, nowait=False)`**  
Get a message from the channel. Returns the a dict with the message id, body, channel, etc. If no message is available, None is returned. Set argument `nowait` to True to prevent long-polling.

**`stream(channel, max_retries=0)`**  
Get a stream (iterator) for channel. Argument max_retries can limit the number of failed reconnection attempts. Default is max_retries=0, which means no limit.

**`drain(channel)`**  
Drain the channel for messages (ie, delete all messages in the channel).

**`channel_stats(channel)`**  
Get channel stats

**`subscriptions(channel)`**  
List topics the channel is subscribed to

**`subscribe(channel, topic, **kwargs)`**  
Subscribe channel to topic. Accepts keyword arguments for the query parameters: priority, timeout, deliver and linger

**`unsubscribe(channel, topic)`**  
Unsubscribe channel from topic

**`topics()`**  
List all topics

**`publish(topic, body)`**  
Publish message on topic

**`subscribers(topic)`**  
List channels subscribed to topic

**`delete(msg_id)`**  
Delete message

**`stats()`**  
Get server stats

## Other client methods


**`__init__(linger_url=None, encode=json_encode, decode=json_decode, content_type='application/json', io_loop=None, **request_args)`**

The method signature is the same for `AsyncLingerClient` and `BlockingLingerClient`, as BlockingLingerClient is a wrapper for AsyncLingerClient, where each HTTP request to Linger is run in an IOLoop.

All parameters are optional.

The `linger_url` argument is the base url for the Linger server. Default is `http://127.0.0.1:8989/`.

The `encode` and `decode` arguments are for supplying custom message encoding and decoding functions. Default is JSON encoding/decoding.

The `content_type` argument should be set to the appropriate mime-type of the output of the encoding function. Default is `application/json`.

The `io_loop` is passed to the AsyncHTTPClient, used for connecting.

Keyword arguments in `request_args` are applied when making requests to Linger. By default the request argument `use_gzip` is True. Accessing a local Linger server, it may be relevant to set `use_gzip` to False.

The request arguments may include `auth_username` and `auth_password` for basic authentication. See `tornado.httpclient.HTTPRequest` for other possible arguments.

**`close()`**  
Closes the Linger client, freeing any resources used.

**`closed`** (property)  
Boolean indicating if the Linger client is closed.

# Support

Support for the software can be provided on a commercial basis, please see [www.nephics.com](http://www.nephics.com) for contact information.

# License

The code and documentation is licensed under the Apache License v2.0, see more in the LICENSE file.
