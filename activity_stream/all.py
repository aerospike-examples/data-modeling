import aerospike
import os
import time
import math
import hashlib

config = { 'hosts': [(os.environ.get("AEROSPIKE_HOST", "127.0.01"), 3000)],
           'policies': { 'key': aerospike.POLICY_KEY_SEND }
}
wpolicy = {'gen': aerospike.POLICY_GEN_EQ}

client = aerospike.client(config).connect()

# Part Two - Fan out on write
def post_msg_fanout(sent_by, to, msg):
  recipients = to
  recipients.append(sent_by)
  post = {'msg': msg, 'from': sent_by, 'sent_ts': long(time.time())}
  for recipient in recipients:
    client.list_insert(("test", "msgs", recipient), "stream", 0, post)

def get_inbox_fanout(user):
  (key, meta, record) = client.get(("test", "msgs", "Jane"))
  return record['stream']

# Send message
post_msg_fanout("Joe", ["Bob", "Jane"], "Silly message...")
post_msg_fanout("Jane", ["Bob"], "My 1st message...")
# Print the messages for "Jane"
messages = get_inbox_fanout("Jane")
for msg in messages:
  print('{0}>> {1}'.format(msg['from'], msg['msg']))

# Part Three - Fan out on write with bucketing
def create_user(user):
  client.put(("test", "users", user), {'total':0})

def calc_bucket(count):
  # Bucket size is 3, just to make testing easier
  return int(math.floor(count/3)) + 1

def post_msg_bucketing(sent_by, to, msg):
  recipients = to
  recipients.append(sent_by)
  post = {'msg': msg, 'from': sent_by, 'sent_ts': long(time.time())}
  for recipient in recipients:
    (key, meta, record) = client.get(("test", "users", recipient))
    count = record['total'] +1
    client.increment(key, "total", 1, meta, wpolicy)
    # Bucket size is 50 messages
    bucket_key = {'user': recipient, 'seq': calc_bucket(count)}
    h = hashlib.new("ripemd160")
    h.update(str(bucket_key))
    client.list_insert(("test", "msgs", h.hexdigest()), "stream", 0, post)

def get_inbox_bucketing(user):
  messages = []
  (key, meta, record) = client.get(("test", "users", user))
  # Find all the buckets based on the total messages received
  for i in range(calc_bucket(record['total']), 0, -1):
    bucket_key = {'user': user, 'seq': i}
    h = hashlib.new("ripemd160")
    h.update(str(bucket_key))
    (key, meta, record) = client.get(("test", "msgs", h.hexdigest()))
    messages.extend(record['stream'])
  return messages

# Post some messages
create_user("Joe")
create_user("Bob")
create_user("Jane")
post_msg_bucketing("Joe", ["Bob", "Jane"], "Silly message...")
post_msg_bucketing("Jane", ["Joe"], "My 1st message...")
post_msg_bucketing("Jane", ["Joe"], "My 2nd message...")
post_msg_bucketing("Jane", ["Joe"], "My 3rd message...")
# Get a users inbox
messages = get_inbox_bucketing("Jane")
for msg in messages:
  print('{0}>> {1}'.format(msg['from'], msg['msg']))
