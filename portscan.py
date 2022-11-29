#
# portscan  -- implements an IP host tcp listener discovery REST API service
#
# Written by Glen Darling (mosquito@darlingevil.com), November 2022.
#

import multiprocessing
import queue
import os
import socket
import time
from datetime import datetime, timezone
import logging
import json
from flask import Flask
from flask import send_file
from waitress import serve

# Basic debug printing
DEBUG = False
def debug (s):
  if DEBUG:
    print(s)

# Get values from the environment or use defaults
def get_from_env(v, d):
  if v in os.environ and '' != os.environ[v]:
    return os.environ[v]
  else:
    return d
MY_REST_API_BASE_URL = get_from_env('MY_REST_API_BASE_URL', '/portscan')
MY_REST_API_PORT     = int(get_from_env('MY_REST_API_PORT', '8004'))
MY_NUM_PROCESSES     = int(get_from_env('MY_NUM_PROCESSES', '50'))

# REST API details
REST_API_BIND_ADDRESS = '0.0.0.0'
REST_API_PORT = MY_REST_API_PORT
REST_API_BASE_URL = MY_REST_API_BASE_URL
restapi = Flask('portscan')

def check (ip, port):
  try:
    debug('Trying "' + ip + ':' + port + '"...')
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex((ip, int(port)))
    sock.close()
    if (0 == result):
      debug('--> connected')
      return { 'ip': ip, 'port': port }
    elif (111 == result):
      return { 'error': 'Connection refused (no listener or too busy).' }
    else:
      return { 'error': 'Connect returned ' + str(result) + '.' }
  except socket.gaierror:
    return { 'error': 'Unable to resolve host "' + ip + '".' }
  except socket.error:
    debug('--> no listener')
    return { 'error': 'Unable to connect to host "' + ip + ':' + port + '".' }
  except Exception as e:
    return { 'error': 'Received return code: ' + str(e) }
  # NOT REACHED

def proc (id, input, output):
  debug('Process id ' + str(id) + ' has started.')
  while True:
    try:
      msg = input.get_nowait()
      (ip, port) = msg.split(':')
      out = check(ip, port)
      if not 'error' in out:
        output.put(out)
        debug('INFO: adding: "' + json.dumps(out) + '"')
    except queue.Empty:
      # This exception occurs when an item cannot immediately be removed from
      # the queue. This may be because it is empty, BUT it may also be because
      # the queue is busy. So a second check to verify the queue is actually
      # empty is needed here! What a goofy API.
      if input.empty():
        debug('INFO: Process id ' + str(id) + ' has ended.')
        return

def multi_proc (input, output):

  # Note the time before process creation begins
  _start = time.time()

  debug('Create {0} new processes...'.format(MY_NUM_PROCESSES))
  procs = list()
  for i in range(MY_NUM_PROCESSES):
    p = multiprocessing.Process(target=proc, args=((i),(input),(output),))
    p.daemon = True
    p.start()
    procs.append(p)

  # Note the scan start time once all procs are up and running
  _wait = time.time()
  debug('Wait for all procs to finish...')
  for i, p in enumerate(procs):
    p.join()

  # Note the final end time
  _end = time.time()

  # Compute the process phase timing
  times = (
    _wait - _start,
    _end - _wait,
    _end - _start)

  # Construct the JSON results (adding in the host IPv4 and MAC info)
  utc_now = datetime.now(timezone.utc).isoformat()
  debug('This scan took took {0} seconds.'.format(times[2]))
  temp = '{"time":{'
  temp += ('"prep_sec":%0.4f' % times[0]) + ','
  temp += ('"scan_sec":%0.4f' % times[1]) + ','
  temp += ('"total_sec":%0.4f' % times[2]) + '},'
  temp += '"scan":['
  while not output.empty():
    try:
      out = output.get_nowait()
      debug(out)
      temp += json.dumps(out) + ','
    except queue.Empty:
      pass
  temp = temp[:-1]
  temp += ']}'

  # Give results
  return temp

# GET: (base URL)/<ipv4>/<port>/json
@restapi.route(REST_API_BASE_URL + '/<ipv4>/<port>/json', methods=['GET'])
def single_single (ipv4, port):
  return check(ipv4, port)

# GET: (base URL)/ips/<min_ip>/<max_ip>/<port>/json
@restapi.route(REST_API_BASE_URL + '/ips/<min_ip>/<max_ip>/<port>/json', methods=['GET'])
def single_port (min_ip, max_ip, port):
  try:
    debug('API: ips: "%s" ... "%s" (%d)' % (min_ip, max_ip, int(port)))
  except:
    return { 'error': 'Bad argument to "/ips" API: "%s", "%s", "%s".' % (min_ip, max_ip, port) }
  debug('Creating the input and output queues...')
  input = multiprocessing.Queue()
  output = multiprocessing.Queue()
  debug('Fill input queue with target IP addresses and this single port.')
  l = min_ip.split('.')
  try:
    prefix = '%d.%d.%d.' % (int(l[0]), int(l[1]), int(l[2]))
    min = int(l[3])
  except:
    return { 'error': 'Bad IP address: "%s".' % (min_ip) }
  try:
    max = int(max_ip.split('.')[3])
  except:
    return { 'error': 'Bad IP address: "%s".' % (max_ip) }
  for i in range(min, max + 1):
    input.put('%s%d:%d' % (prefix, i, int(port)))
  results = multi_proc(input, output)
  return results + '\n'

# GET: (base URL)/ports/<ipv4>/<min_port>/<max_port>/json
@restapi.route(REST_API_BASE_URL + '/ports/<ipv4>/<min_port>/<max_port>/json', methods=['GET'])
def single_ip (ipv4, min_port, max_port):
  try:
    debug('API: ports: "%s" (%d .. %d)' % (ipv4, int(min_port), int(max_port)))
  except:
    return { 'error': 'Bad argument to "/ports" API: "%s", "%s", "%s".' % (ipv4, min_port, max_port) }
  debug('Creating the input and output queues...')
  input = multiprocessing.Queue()
  output = multiprocessing.Queue()
  debug('Fill input queue with this one target IP address and these ports.')
  min = int(min_port)
  max = int(max_port)
  for i in range(min, max + 1):
    input.put('%s:%d' % (ipv4, i))
  results = multi_proc(input, output)
  return results + '\n'

# Main program (to start the web server thread)
if __name__ == '__main__':

  debug('Starting the REST API server...')
  serve(
    restapi,
    host=REST_API_BIND_ADDRESS,
    port=REST_API_PORT)


