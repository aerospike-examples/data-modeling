import aerospike
import os
import time
import random
import string

config = { 'hosts': [(os.environ.get("AEROSPIKE_HOST", "127.0.01"), 3000)],
           'policies': { 'key': aerospike.POLICY_KEY_SEND }
}
wpolicy = {'gen': aerospike.POLICY_GEN_EQ}
mpolicy_create = {'map_write_mode': aerospike.MAP_CREATE_ONLY}

client = aerospike.client(config).connect()

def create_account(user, opening_balance):
  client.put(("test", "accounts", user), {'balance':opening_balance})

def simple_debit_credit(from_account, to_account, amount):
  (key, meta, record) = client.get(("test", "accounts",from_account))
  if record['balance'] >= amount:
    client.increment(("test", "accounts", from_account), "balance", amount * -1, meta, wpolicy)
    client.increment(("test", "accounts", to_account), "balance", amount)

# Part One - Simple Debit & Credit
create_account("Dad", 0)
create_account("Mum", 150)
simple_debit_credit("Mum", "Dad", 100)

# Part Two - Workflow
def transition_state(tx_id, from_state, to_state):
  (key_current, meta_current, record_current) = client.select(("test", "txs", tx_id), ["state"])
  if record_current['state'] == from_state:
    operations = [
      {
        'op' : aerospike.OPERATOR_WRITE,
        'bin': "state",
        'val': to_state,
      },
      {
        'op' : aerospike.OPERATOR_WRITE,
        'bin': "ts",
        'val': long(time.time()),
      },
    ]
    (key_changed, meta_changed, _) = client.operate(key_current, operations, meta_current, wpolicy)
    return (key_changed, meta_changed)
  else:
    return (key_current, meta_current)

def check_valid_transition(tx_id, expected_state, got_state):
  if expected_state != got_state:
    print('{0}: Incorrect state, expected:{1}, got:{2}'.format(tx_id, expected_state, got_state))
    return False
  else:
    return True

def process_debit_credit(tx_id):  
  (_, _, record) = client.get(("test", "txs", tx_id))
  if check_valid_transition(tx_id, record['state'], "Begin"):
    # Check if funding available
    (_, is_funded) = check_funding(tx_id, record['from'], record['amt'])
    if is_funded:
      process_debit(tx_id, record['from'], record['to'], record['amt'])
      process_credit(tx_id, record['from'], record['to'], record['amt'])
    else:
      process_insufficient_funds(tx_id)

def check_funding(tx_id, from_account, amt):
  (key, meta, record) = client.select(("test", "accounts", from_account), ["balance"])
  if record['balance'] >= amt:
    transition_state(tx_id, "Begin", "Approved")
    return (meta, True)
  else:
    return (meta, False)

def process_insufficient_funds(tx_id):
  transition_state(tx_id, "Begin", "Insufficient Funds")
  (_, _, record) = client.select(("test", "txs", tx_id), ["from", "amt"])
  print("{0}: Insufficient funds account:'{1}' amount:{2}".format(tx_id, record['from'], record['amt']))

def process_debit(tx_id, from_account, to_account, amount):
  (_, _, record) = client.select(("test", "txs", tx_id), ["state"])
  if check_valid_transition(tx_id, record['state'], "Approved"):
    # Fund the transaction. Verify that this has not been funded already
    (account_meta, is_funded) = check_funding(tx_id, from_account, amount)
    if not is_funded:
      process_insufficient_funds(tx_id)
    else:      
      transition_state(tx_id, "Approved", "Funding")
      operations = [
        {
          'op' : aerospike.OP_MAP_PUT,
          'bin': "txs",
          'key': tx_id,
          'val': {'amt': amount, 'to': to_account },
          'map_policy': mpolicy_create
        },
        {
          'op' : aerospike.OPERATOR_INCR,
          'bin' : "balance",
          'val' : amount * -1
        },
        {
          'op' : aerospike.OPERATOR_READ,
          'bin' : "balance"
        }
      ]
      #TODO: If the map already exists, then in >= 3.9.1 an exception will be thrown
      (_, _, record) = client.operate(("test", "accounts", from_account), operations, account_meta, wpolicy)
      transition_state(tx_id, "Funding", "Debited")
      print("{0}: Debited from:'{1}', amount:{2}, balance:{3}".format(tx_id, from_account, amount, record['balance']))

def process_credit(tx_id, from_account, to_account, amount):
  (_, _, record) = client.select(("test", "txs", tx_id), ["state"])
  if check_valid_transition(tx_id, record['state'], "Debited"):
    (key, meta, record) = client.get(("test", "accounts", to_account))
    # Apply the credit
    operations = [
      {
        'op' : aerospike.OP_MAP_PUT,
        'bin': "txs",
        'key': tx_id,
        'val': {'amt': amount, 'from': from_account },
        'map_policy': mpolicy_create
      },
      {
        'op' : aerospike.OPERATOR_INCR,
        'bin' : "balance",
        'val' : amount
      },
      {
        'op' : aerospike.OPERATOR_READ,
        'bin' : "balance"
      }
    ]
    #TODO: If the map already exists, then in >= 3.9.1 an exception will be thrown
    (_, _, record) = client.operate(key, operations, meta, wpolicy)
    transition_state(tx_id, "Debited", "Credited")
    print("{0}: Credited to:'{1}', amount:{2}, balance:{3}".format(tx_id, to_account, amount, record['balance']))

def generate_transaction_id():
  return ''.join(random.choice(string.ascii_uppercase + string.digits) \
    for _ in range(6))

def start_debit_credit(from_account, to_account, amount):
  tx_id = generate_transaction_id()
  client.put(("test", "txs", tx_id), 
             {'from': from_account,
              'to': to_account, 
              'amt': amount, 
              'state': "Begin",
              'ts': long(time.time())})
  return tx_id

create_account("Daughter", 0)
create_account("Son", 200)
# Enough funds
my_tx = start_debit_credit("Son", "Daughter", 10)
process_debit_credit(my_tx)
# Not enough funds
my_tx = start_debit_credit("Daughter", "Son", 11)
process_debit_credit(my_tx)


