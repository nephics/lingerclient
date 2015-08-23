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
