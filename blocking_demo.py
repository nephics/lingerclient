import lingerclient

lc = lingerclient.BlockingLingerClient()
r = lc.post('test-channel', {'msg': 'My first message'})
print(r)
print(lc.channels())
m = lc.get('test-channel')
lc.delete(m['id'])
