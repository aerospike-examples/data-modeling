import aerospike
import os
import time
import random
import string

config = { 'hosts': [(os.environ.get("AEROSPIKE_HOST", "127.0.01"), 3000)],
           'policies': { 'key': aerospike.POLICY_KEY_SEND }
}
wpolicy = {'gen': aerospike.POLICY_GEN_EQ}
mpolicy_create = {'map_write_mode': aerospike.MAP_UPDATE}

client = aerospike.client(config).connect()

def create_account(device):
  client.put(("test", "accounts", device),
             {'tokens': {} } )

def create_activation(event, device, service, token):
  client.put(("test", "events", event),
             { 'todo': [{'service': service, 'device': device, 'token': token }],
               'entitlement': [], 
               'devices': [],
             })

def generate_token():
  return ''.join(random.choice(string.ascii_uppercase + string.digits) \
    for _ in range(6))

def provision(device, service, token):
  (key, meta, record) = client.get(("test", "accounts", device))
  if token == "":
    token = generate_token()
  if service in record['tokens']:
    service = record['tokens'][service]
    if service['status'] in ["New", "Suspended"]:
      client.map_put(key, 'tokens', service, 
                     { 'token': token,
                       'ts': long(time.time()),
                       'status': "Waiting" },
                     { 'map_write_mode': aerospike.MAP_UPDATE },
                     meta, wpolicy)
  else:
    client.map_put(key, 'tokens', service, 
                   { 'token': token,
                     'ts': long(time.time()),
                     'status': "Waiting" },
                   { 'map_write_mode': aerospike.MAP_CREATE_ONLY},
                   meta, wpolicy)

device_id = "ATV-123"
service1 = "NBCSports"
token = "MTOB1J"
service2 = "ABC"

# Provision the device
create_account(device_id)
provision(device_id, service1, token)
(key, meta, record) = client.get(("test","accounts",device_id))
print record

provision(device_id, service2, "")
(key, meta, record) = client.get(("test","accounts",device_id))
print record

def do_entitlement(device, service, token):
  (key, meta, record) = client.get(("test", "accounts", device_id))
  if service in record['tokens']:
    service_rec = record['tokens'][service]
    if service_rec['token'] == token:
      # Valid, so update last_logon_ts etc
        service_rec['failed'] = 0
        service_rec['last_logon_ts'] = long(time.time())
        service_rec['status'] = 'Active'
        client.map_put(key, "tokens", service, service_rec,
                       mpolicy_create, meta, wpolicy)
    else:
      if service_rec['status'] in ["Waiting", "Suspended"]:
        if service_rec['failed'] < 3:
          # increment and update last timestamp
          service_rec['failed'] +=1
          service_rec['last_logon_ts'] = long(time.time())
          client.map_put(key, "tokens", service, service_rec,
                         mpolicy_create, meta, wpolicy)
        else:
          # Exceeded limit
          service_rec['status'] = "Suspended"
          service_rec['last_logon_ts'] = long(time.time())
          client.map_put(key, "tokens", service, service_rec,
                         mpolicy_create, meta, wpolicy)
      else:
        # Record the attempt, even if the account is suspended
        client.put(key, {'last_logon_ts': long(time.time())})

# Entitlement will move the state, incorrect Token
do_entitlement(device_id, service1, token)
(key, meta, record) = client.get(("test","accounts",device_id))
print record

def process_todo(queue):
  (key, meta, record) = client.get(("test", "events", queue))
  # Take the next todo and create new entries into each workflow
  todo = record['todo']
  if len(todo) > 0:
    item = todo[0]
    item['ts'] = 0
    operations = [
      {
        'op' : aerospike.OP_LIST_POP,
        'bin': "todo",
        'index': 0
      },
      {
        'op' : aerospike.OP_LIST_APPEND,
        'bin': "entitlement",
        'val': item
      },
      {
        'op' : aerospike.OP_LIST_APPEND,
        'bin': "devices",
        'val': item
      }

    ]
    (key, meta, record) = client.operate(key, operations, meta, wpolicy)  

def do_device(item):
# TODO: Call the device processing
  pass

def process_device(queue):
  (key, meta, record) = client.get(("test", "events", queue))
  for i in range(len(record['devices'])):
    # Find a entitlement where the ts=0, i.e. has not been taken
    item = record['devices'][i]
    if item['ts'] == 0:
      item['ts'] = long(time.time())
      operations = [
        {
          'op' : aerospike.OP_LIST_SET,
          'bin' : "devices",
          'index': i,
          'val' : item
        }
      ]
      (key, meta, record) = client.operate(key, operations, meta, wpolicy)
      do_device(item)
      client.list_pop(key, "devices", i, meta, wpolicy)  

def process_entitlement(queue):
  (key, meta, record) = client.get(("test", "events", queue))
  for i in range(len(record['entitlement'])):
    # Find a entitlement where the ts=0, i.e. has not been taken
    item = record['entitlement'][i]
    if item['ts'] == 0:
      item['ts'] = long(time.time())
      operations = [
        {
          'op' : aerospike.OP_LIST_SET,
          'bin' : "entitlement",
          'index': i,
          'val' : item
        }
      ]
      (key, meta, record) = client.operate(key, operations, meta, wpolicy)
      do_entitlement(item['device'], item['service'], item['token'])
      client.list_pop(key, "entitlement", i, meta, wpolicy)    

# Create the activation event
create_activation("new device", device_id, "NBCSports", token)
# Process the outstanding todo
process_todo("new device")
process_device("new device")
process_entitlement("new device")
(key, meta, record) = client.get(("test","accounts",device_id))
print record

