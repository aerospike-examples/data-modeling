import aerospike
import os
import time
import random
import string

config = {'hosts': [(os.environ.get('AEROSPIKE_HOST', '127.0.01'), 3000)],
          'policies': { 'key': aerospike.POLICY_KEY_SEND }
}
wpolicy = {'gen': aerospike.POLICY_GEN_EQ }
mpolicy_create = { 'map_write_mode': aerospike.MAP_CREATE_ONLY }

client = aerospike.client(config).connect()

def create_event(event, available):
  client.put(("test", "events", for_event), {'name': event, 'available': available})

def create_user(user):
  client.put(("test", "users", user), {'username': user})

# Part Zero - Purchase as two writes
def simple_purchase(user, event, qty):
  (key, meta, record) = client.get(("test", "events", event))
  client.put( key, {'available': record['available'] - qty},
              {}, meta, wpolicy)
  purchase = { "event": event, 'qty': qty }
  client.list_append(("test", "users", user), "purchased", purchase)

# Simple purchase
requestor = "Fred"
for_event = "Mens 800m Final"
create_user(requestor)
create_event(for_event, 500)
simple_purchase(requestor, for_event, 5)
# Query results
(key, meta, record) = client.get(("test", "users", requestor))
print record
(key, meta, record) = client.get(("test", "events", for_event))
print record

# Part One - Storing purchase within the event
def purchase(user, event, qty):
  (key, meta, record) = client.get(("test", "events", event))
  operations = [
    {
      'op' : aerospike.OPERATOR_WRITE,
      'bin': "available",
      'val': record['available'] - qty
    },
    {
      'op' : aerospike.OP_LIST_APPEND,
      'bin' : "sold_to",
      'val' : {'who': user, 'qty': qty}
    }
  ]
  client.operate(key, operations, meta, wpolicy)

# Purchase valid number of tickets
for_event = "Mens 100m Final"
requested = 5
create_event(for_event, 500)
purchase(requestor, for_event, requested)
# Query results
(key, meta, record) = client.get(("test", "events", for_event))
print record

# Purchase invalid number of tickets
purchase(requestor, for_event, 500)
# Query results
(key, meta, record) = client.get(("test", "events", for_event))
print record

# Part Two - Check availability
def check_availability_and_purchase(user, event, qty):
  (key, meta, record) = client.get(("test","events",for_event))
  if record['available'] >= qty:
    operations = [
      {
        'op' : aerospike.OPERATOR_INCR,
        'bin': "available",
        'val': qty * -1
      },
      {
        'op' : aerospike.OP_LIST_APPEND,
        'bin' : "sold_to",
        'val' : {'who': user, 'qty': qty}
      }
    ]
    client.operate(key, operations, meta, wpolicy)

# Check availability before purchasing
# No purchase, not enough stock
for_event = "Womens 4x400m Final"
create_event(for_event, 10)
check_availability_and_purchase(requestor, for_event, 11)
(key, meta, record) = client.get(("test","events",for_event))
print record

# Purchase,  enough stock
check_availability_and_purchase(requestor, for_event, 9)
(key, meta, record) = client.get(("test","events",for_event))
print record

# Part Three - Reserve stock
def reserve(user, event, qty):
  (key, meta, record) = client.get(("test","events",event))
  if record['available'] >= qty:
    # Create the reservation and decrement the stock
    operations = [
      {
        'op' : aerospike.OPERATOR_INCR,
        'bin': "available",
        'val': qty * -1
      },
      {
        'op' : aerospike.OP_MAP_PUT,
        'bin': "reservations",
        'key': user,
        'val': { 'qty': qty, 'ts': long(time.time()) },
        'map_policy': mpolicy_create
      }
    ]
    (key, meta, record) = client.operate(key, operations, meta, wpolicy)
    if creditcard_auth(user):
      # Remove the reservation and add the ticket sale
      operations = [
        {
          'op' : aerospike.OP_LIST_APPEND,
          'bin' : "sold_to",
          'val' : { 'who': user, 'qty': qty, 'order': generate_order_id() }
        },
        {
          'op' : aerospike.OP_MAP_REMOVE_BY_KEY,
          'bin' : "reservations",
          'key': user,
          'return_type': aerospike.MAP_RETURN_VALUE
        }
      ]
      client.operate(key, operations, meta, wpolicy)
    else:
      # Back out the reservation on a credit card decline
      backout_reservation(key, meta, user, qty)

def generate_order_id():
  return ''.join(random.choice(string.ascii_uppercase + string.digits) \
    for _ in range(6))

def creditcard_auth(user):
  # TODO: Credit card auth happens here, but lets just sleep
  # return random.choice([True, False])
  time.sleep(1)
  return True

def backout_reservation(key, meta, user, qty):
  operations = [
    {
      'op' : aerospike.OPERATOR_INCR,
      'bin': "available",
      'val': qty
    },
    {
      'op' : aerospike.OP_MAP_REMOVE_BY_KEY,
      'bin' : "reservations",
      'key': user,
      'return_type': aerospike.MAP_RETURN_NONE
    }
  ]
  return client.operate(key, operations, meta, wpolicy)

# Query results
for_event = "Womens Marathon Final"
create_event(for_event, 500)
reserve(requestor, for_event, 5)
(key, meta, record) = client.get(("test", "events", for_event))
print record

# Part Four - Expire Reservation
def create_expired_reservation(event):
  reservation = { 'name': event, 
                  'available': 469, 
                  'reservations': { 'Fred': {
                                      'qty': 5, 
                                      'ts': long(time.time())
                                    },
                                    'Jim': { 
                                      'qty': 7, 
                                      'ts': long(time.time() - 50)
                                    },
                                    'Amy': { 
                                      'qty': 19, 
                                      'ts': long(time.time() - 31)
                                    },
                                  }
                }
  client.put(("test", "events", for_event), reservation)

def expire_reservation(event):
  (key, meta, record) = client.get(("test", "events", event))
  # Cutoff is 30 seconds ago
  cutoff_ts = long(time.time()-30)
  for i in record["reservations"]:
    res = record["reservations"][i]
    if res["ts"] < cutoff_ts:
      (key, meta, _) = backout_reservation(key, meta, i, res['qty'])

# Expire reservations
for_event = "Womens Javelin"
create_expired_reservation(for_event)
expire_reservation(for_event)
# Query results
(key, meta, record) = client.get(("test", "events", for_event))
print record

# Part Five - Posting purchases
def reserve_with_pending(user, event, qty):
  (key, meta, record) = client.get(("test","events",event))
  if record['available'] >= qty:
    # Create the reservation and decrement the stock
    operations = [
      {
        'op' : aerospike.OPERATOR_INCR,
        'bin': "available",
        'val': qty * -1
      },
      {
        'op' : aerospike.OP_MAP_PUT,
        'bin': "reservations",
        'key': user,
        'val': { 'qty': qty, 'ts': long(time.time()) },
        'map_policy': mpolicy_create
      }
    ]
    (key, meta, record) = client.operate(key, operations, meta, wpolicy)
    if creditcard_auth(user):
      # Remove the reservation and add the ticket sale
      order_id = generate_order_id()
      operations = [
        {
          'op' : aerospike.OP_LIST_APPEND,
          'bin' : "sold_to",
          'val' : { 'who': user, 'qty': qty, 'order': order_id }
        },
        {
          'op' : aerospike.OP_MAP_REMOVE_BY_KEY,
          'bin' : "reservations",
          'key': user,
          'return_type': aerospike.MAP_RETURN_VALUE
        },
        {
          'op' : aerospike.OP_LIST_APPEND,
          'bin' : "pending",
          'val' : { 'who': user, 'qty': qty, 'order': order_id}
        }
      ]
      client.operate(key, operations)
    else:
      # Back out the reservation on a credit card decline
      backout_reservation(key, meta, user, qty)

def post_purchases(event):
  (key, meta, record) = client.get(("test","events",event))
  for res in record["pending"]:
    # Add to users record
    operations = [
      {
        'op' : aerospike.OP_MAP_PUT,
        'bin' : "purchases",
        'key' : res['order'],
        'val' : {'event': event, 'qty': res['qty']}
      }
    ]
    client.operate(("test","users", res['who']), operations)
    operations = [
      {
        'op' : aerospike.OP_LIST_POP,
        'bin' : "pending",
        'index' : 0
      }
    ]
    (key, record, meta) = client.operate(key, operations, meta, wpolicy)

# Post purchases and query results
create_user(requestor)
for_event = "Mens Discus"
create_event(for_event, 500)
reserve_with_pending(requestor, for_event, 5)
post_purchases(for_event)
(key, meta, record) = client.get(("test", "events", for_event))
print record
(key, meta, record) = client.get(("test", "users", requestor))
print record
