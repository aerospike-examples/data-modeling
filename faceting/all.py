import aerospike
import os
import hashlib

config = { 'hosts': [(os.environ.get("AEROSPIKE_HOST", "127.0.01"), 3000)],
           'policies': { 'key': aerospike.POLICY_KEY_SEND }
}

client = aerospike.client(config).connect()

def create_products():
  wheelbarrow = { 'sku': "123-ABC-723",
                  'name': "Wheelbarrow",
                  'pre_assembled': True,
                  'pickup_only': True,
                  'weight_in_kg': 12,
                  'category': ["Garden", "Tool"]
                }
  pump =        { 'sku': "737-DEF-911",
                  'name': "Bicycle Pump",
                  'pre_assembled': True,
                  'pickup_only': False,
                  'weight_in_kg': 0.5,
                  'category': ["Tool"]
                }
  kite =        { 'sku': "320-GHI-921",
                  'name': "Kite",
                  'pre_assembled': False,
                  'pickup_only': False,
                  'weight_in_kg': 0.5,
                  'category': ["Toy"]
                }
  client.put(("test", "products", wheelbarrow['sku']), wheelbarrow)
  client.put(("test", "products", pump['sku']), pump)
  client.put(("test", "products", kite['sku']), kite)

def create_lookups():
  client.put(("test", "lookups", "pre_assembled/True"), 
             { 'products': [ "123-ABC-723", "737-DEF-911"] })
  client.put(("test", "lookups", "store_pickup_only/True"), 
             { 'products': [ "123-ABC-723"] })

def match(key1, key2):
  m = []
  (key1, meta1, record1) = client.get(("test","lookups",key1))
  (key2, meta2, record2) = client.get(("test","lookups",key2))
  matches = list(set(record1['products']) & set(record2['products']))
  for sku in matches:
    (key, meta, record) = client.get(("test", "products", sku))
    m.append(record)
  return m

# Find matches based on two criteria
create_products()
create_lookups()
# Find the match
matches = match("pre_assembled/True", "store_pickup_only/True")
for m in matches:
  print m  

def create_hashed_lookups(lookup_key, products):
  h = hashlib.new("ripemd160")
  h.update(str(lookup_key))
  client.put(("test", "lookups", h.hexdigest()), 
             { 'products': products})

def match_hashed(lookup_key):
  m = []
  h = hashlib.new("ripemd160")
  h.update(str(lookup_key))
  (key, meta, found) = client.get(("test", "lookups", h.hexdigest()))
  for sku in found['products']:
    (key, meta, record) = client.get(("test", "products", sku))
    m.append(record)
  return m

# Find matches based on hashed criteria
lookup_key={'pickup_only': True, 'pre_assembled': True}
create_hashed_lookups(lookup_key, ["123-ABC-723"])
# Find the match
matches = match_hashed(lookup_key)
for m in matches:
  print m
