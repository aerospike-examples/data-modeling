import aerospike
import os
import hashlib
import random
import string
import time
import copy

config = {'hosts': [(os.environ.get('AEROSPIKE_HOST', '127.0.01'), 3000)],
          'policies': { 'key': aerospike.POLICY_KEY_SEND }
}
wpolicy = {'gen': aerospike.POLICY_GEN_EQ, 'key': aerospike.POLICY_KEY_SEND}
mpolicy_create = { 'map_write_mode': aerospike.MAP_CREATE_ONLY }

client = aerospike.client(config).connect()

# Moving parts
def generate_xfer():
  return ''.join(random.choice(string.ascii_uppercase + string.digits) \
    for _ in range(6))

def create_location(name, type, part):
  operations = [
    {
      'op' : aerospike.OPERATOR_WRITE,
      'bin': "type",
      'val': type
    },
    {
      'op' : aerospike.OP_MAP_PUT,
      'bin': "parts",
      'key': part,
      'val': {}
    }
  ]
  client.operate(("test", "locations", name), operations, {}, wpolicy)

def create_part(part, location):
  client.put(("test", "parts", part), {'location': location}, {}, wpolicy)

def start_transfer(part, from_loc, to_loc):
  xfer = generate_xfer()
  client.put( ("test", "xfers", xfer),
              { 'status': "Started",
                'xfer_out': "Ready",
                'xfer_in': "Ready",
                'from_loc': from_loc,
                'to_loc': to_loc,
                'part': part, 
                'ts': long(time.time())},
              {}, wpolicy)
  return xfer

def add_transfer_requests(xfer):
  (key, meta, record) = client.get(("test", "xfers", xfer))
  if record['xfer_out'] == "Ready":
    client.map_put( ("test", "locations", record['from_loc']),
                    "xfers",
                    xfer,
                    { 'part': record['part'],
                      'to_loc': record['to_loc'],
                      'xfer_in': "",
                      'xfer_out': "Requested"},
                    {},
                    wpolicy)
  if record['xfer_in'] == "Ready":
    in_rec = copy.copy(record)
    in_rec['xfer_in'] = "Requested"
    client.map_put( ("test", "locations", record['to_loc']),
                     "xfers",
                    xfer,
                    { 'part': record['part'],
                      'from_loc': record['from_loc'],
                      'xfer_in': "Requested",
                      'xfer_out': ""},
                    {},
                    wpolicy)

def process_xfer_out(location):
  (key, meta, record) = client.get(("test", "locations", location))
  for xfer_key in record['xfers']:
    xfer = record['xfers'][xfer_key]
    if xfer['xfer_out'] == "Requested":
      # Move the part out
        operations = [
          {
            'op' : aerospike.OP_MAP_REMOVE_BY_KEY,
            'bin': "xfers",
            'key': xfer_key,
            'return_type': aerospike.MAP_RETURN_NONE
          },
          {
            'op' : aerospike.OP_MAP_REMOVE_BY_KEY,
            'bin': "parts",
            'key': xfer['part'],
            'return_type': aerospike.MAP_RETURN_NONE
          }
        ]
        (key, meta, record) = client.operate(key, operations, meta, wpolicy)
        # Update the xfer record  
        client.put(("test", "xfers", xfer_key), {'xfer_out': "Done"}, {}, wpolicy)

def process_xfer_in(location):
  (key, meta, record) = client.get(("test", "locations", location))
  for xfer_key in record['xfers']:
    xfer = record['xfers'][xfer_key]
    if xfer['xfer_in'] == "Requested":
      # Move the part in
        operations = [
          {
            'op' : aerospike.OP_MAP_REMOVE_BY_KEY,
            'bin': "xfers",
            'key': xfer_key,
            'return_type': aerospike.MAP_RETURN_NONE
          },
          {
            'op' : aerospike.OP_MAP_PUT,
            'bin': "parts",
            'key': xfer['part'],
            'val': {}
          }
        ]
        (key, meta, record) = client.operate(key, operations, meta, wpolicy)
        # Update the xfer record
        client.put(("test", "xfers", xfer_key), {'xfer_in': "Done"}, {}, wpolicy)

def complete_xfer(xfer):
  (xfer_key, xfer_meta, xfer_record) = client.get(("test", "xfers", xfer))
  if ( xfer_record['xfer_in'] == "Done" and 
       xfer_record['xfer_out'] == "Done" and
       xfer_record['status'] != 'Finished' ):
    (part_key, part_meta, part_record) = client.get(("test", "parts", xfer_record['part']))
    client.put(part_key, {'location': xfer_record['to_loc']}, part_meta, wpolicy)
    client.put(xfer_key, {'status': "Finished"}, xfer_meta, wpolicy)

# Create parts & locations
part = "8BQWQM"
from_loc = "Las Vegas"
to_loc = "Mountain View"

create_location(from_loc, "Warehouse", part)
create_location(to_loc, "Store", "ABC123")
create_part(part, from_loc)
# transfer_part
xfer = start_transfer(part, from_loc, to_loc)
add_transfer_requests(xfer)
process_xfer_out(from_loc)
process_xfer_in(to_loc)
complete_xfer(xfer)

# Print the results
(_, _, record) = client.get(("test", "locations", from_loc))
print record
(_, _, record) = client.get(("test", "locations", to_loc))
print record
(_, _, record) = client.get(("test", "parts", part))
print record
(_, _, record) = client.get(("test", "xfers", xfer))
print record

