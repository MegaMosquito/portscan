#
# portscan  -- implements an IP host tcp listener discovery REST API service
#
# Written by Glen Darling (mosquito@darlingevil.com), November 2022.
#

import queue
import sys
import os
import os.path
import socket
import time
import queue
import threading
from datetime import datetime, timezone
import logging
import json
import requests
from flask import Flask
from flask import send_file
from waitress import serve

# Basic debug printing
DEBUG_THREADS    = False
DEBUG_WORKERS    = False
DEBUG_INPUT      = True
DEBUG_HOSTS      = True
DEBUG_PORTS      = False
DEBUG_CHECK_PORT = False
def debug (flag, s):
  if flag:
    print(s)
    sys.stdout.flush()

# Get values from the environment or use defaults
def get_from_env(v, d):
  if v in os.environ and '' != os.environ[v]:
    return os.environ[v]
  else:
    return d
MY_LANSCAN_URL         = get_from_env('MY_LANSCAN_URL', '')
MY_REST_API_BASE_URL   = get_from_env('MY_REST_API_BASE_URL', 'portscan')
MY_CONTAINER_BIND_PORT = int(get_from_env('MY_CONTAINER_BIND_PORT', '80'))
MY_NUM_THREADS         = int(get_from_env('MY_NUM_THREADS', '50'))

# Configuration constants
TIME_FORMAT = '%Y-%m-%d %H:%M:%S'
SOCKET_CONNECT_TIMEOUT_SEC = 5
PORTSCANNER_SLEEP_MSEC = 1000
MANAGER_SLEEP_MSEC = 1000
CACHE_DIRECTORY = '/cache'
CACHE_EXPIRY_SEC = 60*60*24*2 # Expire cache entries after 2 days

# REST API details
webapp = Flask('portscan')

def check_host_port (ipv4, port):
  try:
    debug(DEBUG_CHECK_PORT, f'    --> TRYING: ipv4={ipv4}, port={port}.')
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(SOCKET_CONNECT_TIMEOUT_SEC)
    result = sock.connect_ex((ipv4, int(port)))
    sock.close()
    if (0 == result):
      debug(DEBUG_CHECK_PORT, f'      <-- CONNECTED to ipv4={ipv4}, port={port}.')
      return { 'ipv4': ipv4, 'port': port }
    elif (111 == result):
      debug(DEBUG_CHECK_PORT, f'      <-- REFUSED from ipv4={ipv4}, port={port}.')
      return { 'error': 'Connection refused (no listener or too busy).' }
    else:
      debug(DEBUG_CHECK_PORT, f'      <-- ERROR {result} from ipv4={ipv4}, port={port}.')
      return { 'error': 'Connect returned ' + str(result) + '.' }
  except socket.gaierror:
    debug(DEBUG_CHECK_PORT, f'      <-- ERROR RESOLVING ipv4={ipv4}, port={port}.')
    return { 'error': 'Unable to resolve host "' + ipv4 + '".' }
  except socket.error:
    debug(DEBUG_CHECK_PORT, f'      <-- FAILED to connect to ipv4={ipv4}, port={port}.')
    return { 'error': 'Unable to connect to host "' + ipv4 + ':' + port + '".' }
  except Exception as e:
    debug(DEBUG_CHECK_PORT, f'      <-- EXCEPTION {s} from ipv4={ipv4}, port={port}.')
    return { 'error': 'Received return code: ' + str(e) }
  # NOT REACHED

def portworker (n, ipv4, ports, results):
  debug(DEBUG_WORKERS, f'    --> STARTING port worker thread #{n}.')
  while True:
    try:
      debug(DEBUG_PORTS, f'        --> REQUESTING port for ipv4={ipv4}.')
      p = ports.get_nowait()
      debug(DEBUG_PORTS, f'          (worker {n} trying port {p} for ipv4={ipv4}.')
      r = check_host_port(ipv4, p)
      if 'ipv4' in r:
        debug(DEBUG_PORTS, f'      <-- PORT {p} is open on ipv4={ipv4}.')
        results.put(p, block=True)
      else:
        debug(DEBUG_PORTS, f'      <-- PORT {p} is closed on ipv4={ipv4}.')
    except queue.Empty:
      # This exception occurs when an item cannot immediately be removed from
      # the queue. This may be because it is empty, BUT it may also be because
      # the queue is busy. So a second check to verify the queue is actually
      # empty is needed here! What a goofy API.
      if ports.empty():
        debug(DEBUG_WORKERS, f'  <-- ENDING worker thread #{n}.')
        return
#    except Exception as e:
#      logging.exception(f'EXCEPTION: {e}.')
    time.sleep(0.1)

def record (mac, ipv4, results, times, utc_now):

  # Put queued results into a list
  ports = []
  while not results.empty():
    try:
      p = results.get_nowait()
      ports.append(p)
    except queue.Empty:
      pass
  sorted_ports = sorted(ports)

  # Construct the JSON , starting with the host info
  json_output = '{'
  json_output += '"host":{"ipv4":"' + ipv4 + '","mac":"' + mac + '"},'

  # The times
  json_output += '"time":{'
  json_output += '"utc":"' + utc_now + '",'
  json_output += ('"prep_sec":%0.4f' % times[0]) + ','
  json_output += ('"scan_sec":%0.4f' % times[1]) + ','
  json_output += ('"total_sec":%0.4f' % times[2])
  json_output += '},'

  # Add the (possibly empty) ports list
  json_output += '"ports":['
  if len(sorted_ports) > 0:
    for p in sorted_ports:
      json_output += str(p) + ','
    # Strip trailing comma
    json_output = json_output[:-1]
  json_output += '],'

  # The count of ports
  count = len(sorted_ports)
  json_output += '"count":' + str(count)

  # All done!
  json_output += '}'

  debug(DEBUG_HOSTS, f'RESULTS (for {ipv4}, {mac}): {count} ports open.')
  filepath = CACHE_DIRECTORY + '/' + mac
  debug(DEBUG_HOSTS, f'WRITING results into file "{filepath}".')
  f = open(filepath, "w")
  n = f.write(json_output)
  f.close()
  
def portscanner (input):
  debug(DEBUG_THREADS, f'STARTING the (never ending) portscanner thread.')
  while True:
    debug(DEBUG_HOSTS or DEBUG_PORTS, f'LOOKING for a new host to scan in portscanner.')
    try:
      j = input.get_nowait()
      _start = time.time()
      ipv4 = j['ipv4']
      mac = j['mac']
      debug(DEBUG_INPUT or DEBUG_HOSTS or DEBUG_PORTS, f'--> SCANNING: ipv4={ipv4}, mac={mac}.')
      debug(DEBUG_PORTS, f'  --> Enqueueing the set of ports in the "ports" queue...')
      ports = queue.Queue()
      results = queue.Queue()
      for p in range(1, 65536):
        ports.put(p, block=True)
      thread_pool = []
      for n in range(MY_NUM_THREADS):
        debug(DEBUG_WORKERS, f'  --> SPAWNING worker thread #{n}.')
        t = threading.Thread(target=portworker, args=(n, ipv4, ports, results,))
        thread_pool.append(t)
        t.start()
      c = 0
      _wait = time.time()
      for t in thread_pool:
        t.join()
        c += 1
        if c % 10 == 0:
          debug(DEBUG_WORKERS, f'  <-- JOINED {c}th worker thread.')
      debug(DEBUG_WORKERS, f'  <-- JOINED *all* worker threads.')
      if results.empty():
        debug(DEBUG_HOSTS or DEBUG_PORTS, f'<-- NO PORTS OPEN on ipv4={ipv4}, mac={mac}.')
      else:
        debug(DEBUG_HOSTS or DEBUG_PORTS, f'<-- FOUND ports open on ipv4={ipv4}, mac={mac}.')
      # Empty or not, record the results
      _end = time.time()
      times = (
        _wait - _start,
        _end - _wait,
        _end - _start)
      debug(DEBUG_HOSTS, f'SCAN of ipv4={ipv4}, mac={mac} took {times[2]:0.1} seconds.')
      utc_now = datetime.now(timezone.utc).strftime(TIME_FORMAT)
      record(mac, ipv4, results, times, utc_now)
    except queue.Empty:
      # This exception occurs when an item cannot immediately be removed from
      # the queue. This may be because it is empty, BUT it may also be because
      # the queue is busy. So a second check to verify the queue is actually
      # empty is needed here! What a goofy API.
      if input.empty():
        debug(DEBUG_INPUT, 'EMPTY "input" queue in portscanner thread.')
    except Exception as e:
      logging.exception(f'EXCEPTION: {e}.')
      raise

    # Sleep until next cycle
    debug(DEBUG_THREADS, f'Port scanner thread sleeping for {PORTSCANNER_SLEEP_MSEC / 1000.0} seconds...')
    time.sleep(PORTSCANNER_SLEEP_MSEC / 1000.0)

def manager (input):
  debug(DEBUG_THREADS, f'STARTING the (never ending) manager thread.')
  while True:
    debug(DEBUG_INPUT, f'PULLING new "lanscan" snapshot.')
    try:
      snapshot = requests.get(MY_LANSCAN_URL, verify=False, timeout=10)
      snapshot_json = snapshot.json()
    except:
      snapshot = ''
      snapshot_json = {}
    # Add any not-already-cached nodes into the input queue
    if 'scan' in snapshot_json:
      count = len(snapshot_json['scan'])
      debug(DEBUG_INPUT, f'ADDING {count} nodes to the "input" queue.')
      for node in snapshot_json['scan']:
        # Force uppercase for all MACs
        node['mac'] = node['mac'].upper()
        filepath = CACHE_DIRECTORY + '/' + node['mac']
        if not os.path.exists(filepath):
          debug(DEBUG_INPUT, f'ADDING ({node["ipv4"]},{node["mac"]}) to the "input" queue.')
          input.put(node, block=True)
    debug(DEBUG_INPUT, f'FILLED the input queue.')
    # Wait for that queue to empty
    while not input.empty():
      debug(DEBUG_INPUT, f'WAITING for the input queue to empty.')
      time.sleep(60)
    debug(DEBUG_INPUT, f'EMPTY "input" queue in manager thread.')
    # Clean the cache of any stale entries
    utc_now = datetime.now(timezone.utc)
    macs = os.listdir(CACHE_DIRECTORY)
    for mac in macs:
      filepath = CACHE_DIRECTORY + '/' + mac
      try:
        f = open(filepath, "r")
        data = f.read()
        f.close()
        j = json.loads(data)
        when = j['time']['utc']
        node = j['host']
        utc_then = datetime.strptime(when, TIME_FORMAT)
        utc_then = utc_then.replace(tzinfo=timezone.utc)
        age_sec = (utc_now - utc_then).total_seconds()
        if age_sec > CACHE_EXPIRY_SEC:
          debug(DEBUG_INPUT, f'SCHEDULING scan for {mac}.')
          input.put(node, block=True)
      except FileNotFoundError:
        pass
    # Sleep before starting again
    debug(DEBUG_THREADS, f'Manager thread sleeping for {MANAGER_SLEEP_MSEC / 1000.0} seconds...')
    time.sleep(MANAGER_SLEEP_MSEC / 1000.0)

# Request to **IMMEDIATELY** scan a specific port on a specific host
# GET: (base URL)/<ipv4>/<port>/json
@webapp.route('/' + MY_REST_API_BASE_URL + '/<ipv4>/<port>/json', methods=['GET'])
def immediate_port_check (ipv4, port):
  return check_host_port(ipv4, port)

# Request to retrieve all **CACHED** results from a specific host
# GET: (base URL)/<mac>/json
@webapp.route('/' + MY_REST_API_BASE_URL + '/<mac>/json', methods=['GET'])
def get_cached_host_scan (mac):
  filepath = CACHE_DIRECTORY + '/' + mac
  try:
    f = open(filepath, "r")
    data = f.read()
    f.close()
    return data + '\n'
  except FileNotFoundError:
    return '{"error":"host not found"}'

# Request to retrieve MAC addresses of all hosts with **CACHED** results
# GET: (base URL)/json
@webapp.route('/' + MY_REST_API_BASE_URL + '/json', methods=['GET'])
def get_cached_host_list ():
  macs = os.listdir(CACHE_DIRECTORY)
  json_output = '{"macs":['
  for mac in macs:
    json_output += '"' + mac.strip() + '",'
  json_output = json_output[:-1]
  json_output += ']}\n'
  return json_output

# Prevent caching on all requests
@webapp.after_request
def add_header(r):
  r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
  r.headers["Pragma"] = "no-cache"
  r.headers["Expires"] = "0"
  r.headers['Cache-Control'] = 'public, max-age=0'
  return r

# Main program (instantiates and starts polling thread and then web server)
if __name__ == '__main__':

  # This is the job queue, managed by the manager, consumed by the port scanner
  input = queue.Queue()

  # Start the thread that queues up hosts to scan, and keeps the cache clean
  manager_thread = threading.Thread(target=manager, args=(input,))
  manager_thread.start()

  # Start the thread that manages the port scan worker threads
  portscanner_thread = threading.Thread(target=portscanner, args=(input,))
  portscanner_thread.start()

  # Start the web server thread
  debug(DEBUG_THREADS, 'STARTING the REST API server thread...')
  threading.Thread(target=lambda: serve(
    webapp,
    host='0.0.0.0',
    port=MY_CONTAINER_BIND_PORT)).start(),

