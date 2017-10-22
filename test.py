
import unittest

from tornado.gen import sleep
from tornado.testing import (AsyncHTTPTestCase, gen_test, main as testing_main)
from tornado.options import options

import linger
import lingerclient

options.logging = None


class TestMethods(AsyncHTTPTestCase):

    def get_app(self):
        application, self.settings = linger.make_app()
        return application

    def setUp(self):
        super().setUp()
        self._content_type = 'text/plain'
        self.client = lingerclient.AsyncLingerClient(
            self.get_url(''), content_type=self._content_type,
            io_loop=self.io_loop)
        self.kwargs = {  # default add_message kwargs
            'channel': 'test',
            'body': 'test msg',
            'priority': 0,
            'timeout': 30,
            'deliver': 0,
            'linger': 0,
            'topic': ''
        }

    def tearDown(self):
        cb = self.settings.get('shutdown_callback')
        if cb is not None:
            cb()
        super().tearDown()

    def check_msg(self, msg, orig):
        """Check that msg match the original"""
        self.assertIsNotNone(msg)
        self.assertEqual(msg['channel'], orig['channel'])
        self.assertEqual(msg['body'], orig['body'])
        self.assertEqual(msg['mimetype'], self._content_type)
        self.assertEqual(msg['topic'], orig['topic'])
        self.assertEqual(msg['timeout'], orig['timeout'])
        self.assertEqual(msg['priority'], orig['priority'])
        self.assertEqual(msg['linger'], orig['linger'])
        self.assertEqual(msg['deliver'], orig['deliver'])
        self.assertEqual(msg['delivered'], 1)

    @gen_test
    def test_add_get(self):
        """Add msg, get it again"""
        self.client.post(**self.kwargs)
        future = self.client.get(self.kwargs['channel'])
        msg = yield future
        self.check_msg(msg, self.kwargs)

    @gen_test
    def test_add_get_nowait(self):
        """Add msg, get it again without waiting"""
        self.client.post(**self.kwargs)
        future = self.client.get(self.kwargs['channel'], nowait=True)
        msg = yield future
        self.check_msg(msg, self.kwargs)

    @gen_test
    def test_get_wait_add(self):
        """Ask for msg, wait, add msg, get it again"""
        future = self.client.get(self.kwargs['channel'])
        self.client.post(**self.kwargs)
        msg = yield future
        self.check_msg(msg, self.kwargs)

    @gen_test
    def test_drain_channel(self):
        """Add msgs to channel, drain, check channel is empty"""
        count = 3
        for i in range(count):
            yield self.client.post(**self.kwargs)
        chan_name = self.kwargs['channel']
        channels = yield self.client.channels()

        # test: exists only this one channel
        self.assertEqual(channels, [chan_name])

        # test: all and only the messages added are ready, none are hidden
        stats = yield self.client.channel_stats(chan_name)
        self.assertEqual(stats, {'ready': count, 'hidden': 0})

        # test: no messages left in channel
        self.assertTrue(self.client.drain(chan_name))
        stats = yield self.client.channel_stats(chan_name)
        self.assertEqual(sum(stats.values()), 0)

    @gen_test(timeout=10)
    def test_subscribe_unsubscribe(self):
        """Subscribe and unsubscribe topic"""
        self.kwargs['topic'] = 'some-topic'
        kwargs = {k: self.kwargs[k] for k in (
            'channel', 'topic', 'priority', 'timeout', 'deliver', 'linger')}
        yield self.client.subscribe(**kwargs)

        chan_name = kwargs['channel']
        topic = kwargs['topic']
        channels = yield self.client.channels()

        # test: exists only this one channel
        self.assertEqual(channels, [chan_name])

        # test: exists only this one topic (globally)
        topics = yield self.client.topics()
        self.assertEqual(topics, [topic])

        # test: exists only this one topic for this channel
        topics = yield self.client.subscriptions(chan_name)
        self.assertEqual(topics, [topic])

        # subscribe first channel to another topic
        all_topics = [topic]
        kwargs['topic'] = 'another-topic'  # 2nd topic
        all_topics.append(kwargs['topic'])
        all_topics.sort()
        yield self.client.subscribe(**kwargs)

        # test: exists only these two topics (globally)
        topics = yield self.client.topics()
        self.assertEqual(topics, all_topics)

        # test: exists only these two topics for this channel
        topics = yield self.client.subscriptions(chan_name)
        self.assertEqual(topics, all_topics)

        # subscribe another channel to the second topic
        all_channels = [chan_name]
        kwargs['channel'] = 'another-test'  # 2nd channel
        all_channels.append(kwargs['channel'])
        all_channels.sort()
        yield self.client.subscribe(**kwargs)

        # test: exists only these two topics (globally)
        topics = yield self.client.topics()
        self.assertEqual(topics, all_topics)

        # test: exists only these two topics for the first channel
        topics = yield self.client.subscriptions(chan_name)
        self.assertEqual(topics, all_topics)

        # test: exists only the second topic for the second channel
        topics = yield self.client.subscriptions(kwargs['channel'])
        self.assertEqual(topics, [kwargs['topic']])

        # test: the first topic has only the first channel as subscriber
        channels = yield self.client.subscribers(topic)
        self.assertEqual(channels, [chan_name])

        # test: the second topic has both channels as subscribers
        channels = yield self.client.subscribers(kwargs['topic'])
        self.assertEqual(channels, all_channels)

        # unsucsbribe the second channel from the second topic
        yield self.client.unsubscribe(kwargs['channel'], kwargs['topic'])

        # test: the second topic has only the first channel as subscriber
        channels = yield self.client.subscribers(kwargs['topic'])
        self.assertEqual(channels, [chan_name])

        # unsucsbribe the first channel from the first topic
        yield self.client.unsubscribe(chan_name, topic)

        # test: exists only the first channel
        channels = yield self.client.channels()
        self.assertEqual(channels, [chan_name])

        # test: exists only the second topic (globally)
        topics = yield self.client.topics()
        self.assertEqual(topics, [kwargs['topic']])

        # unsucsbribe the first channel from the second topic
        yield self.client.unsubscribe(chan_name, kwargs['topic'])

        # test: exists no topics (globally)
        topics = yield self.client.topics()
        self.assertTrue(len(topics) == 0)

        # test: are no more channels
        channels = yield self.client.channels()
        self.assertTrue(len(channels) == 0)

    @gen_test
    def test_publish_subscribe(self):
        self.kwargs['topic'] = 'some-topic'
        sub_kwargs = {k: self.kwargs[k] for k in (
            'channel', 'topic', 'priority', 'timeout', 'deliver', 'linger')}
        yield self.client.subscribe(**sub_kwargs)

        pub_kwargs = {k: self.kwargs[k] for k in ('topic', 'body')}
        yield self.client.publish(**pub_kwargs)
        msg = yield self.client.get(self.kwargs['channel'], nowait=True)
        self.check_msg(msg, self.kwargs)

    @gen_test
    def test_timeout(self):
        """Timeout test"""
        self.kwargs['timeout'] = 1  # hide for only 1 sec
        self.client.post(**self.kwargs)
        future = self.client.get(self.kwargs['channel'], nowait=True)
        msg = yield future

        # test: no message ready
        future = self.client.get(self.kwargs['channel'], nowait=True)
        msg2 = yield future
        self.assertIsNone(msg2)

        # test: message is ready again
        yield sleep(1.2)
        future = self.client.get(self.kwargs['channel'], nowait=True)
        msg3 = yield future
        self.assertEqual(msg['delivered'], 1)
        self.assertEqual(msg3['delivered'], 2)
        for m in (msg, msg3):
            del m['delivered']
            del m['received']
        self.assertEqual(msg, msg3)

    @gen_test
    def test_linger(self):
        """Linger test"""
        self.kwargs['linger'] = 1  # purge after 1 sec
        yield self.client.post(**self.kwargs)

        # test: message has been purged
        yield sleep(1.4)
        msg = yield self.client.get(self.kwargs['channel'], nowait=True)
        self.assertIsNone(msg)

    @gen_test
    def test_deliver(self):
        """Deliver test"""
        self.kwargs['deliver'] = 1  # deliver only once
        self.kwargs['timeout'] = 1  # hide for only 1 sec
        yield self.client.post(**self.kwargs)
        msg = yield self.client.get(self.kwargs['channel'], nowait=True)

        # test: message has been purged
        yield sleep(1.2)
        msg = yield self.client.get(self.kwargs['channel'], nowait=True)
        self.assertIsNone(msg)

    @gen_test
    def test_priority(self):
        """Priority test"""
        # add message with priority 0
        self.kwargs['priority'] = 0
        self.kwargs['body'] = '1'
        yield self.client.post(**self.kwargs)

        # add message with priority 1
        self.kwargs['priority'] = 1
        self.kwargs['body'] = '2'
        yield self.client.post(**self.kwargs)

        # add message with priority -1
        self.kwargs['priority'] = -1
        self.kwargs['body'] = '0'
        yield self.client.post(**self.kwargs)

        for i in range(3):
            msg = yield self.client.get(
                self.kwargs['channel'], nowait=True)
            self.assertEqual(msg['priority'], i-1)
            self.assertEqual(int(msg['body']), i)


def all():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestMethods)


if __name__ == '__main__':
    testing_main()
