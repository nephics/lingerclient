
import lingerclient

lc = lingerclient.BlockingLingerClient()

chan = 'test-channel'
n = 10

# post messages
for i in range(n):
    lc.post(chan, {'msg': 'Message {}'.format(i + 1)})


# stream messages
ids = []
i = 0
for m in lc.stream(chan):
    ids.append(m['id'])
    i += 1
    if i >= n:
        break

# delete messages
for i in ids:
    lc.delete(i)

print('Sent, received and deleted {} messages.'.format(n))
