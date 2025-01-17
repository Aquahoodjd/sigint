#!/usr/bin/env python
# Based on :https://gist.github.com/LoranKloeze/6b713022619c2b32b32c6400a55a8433

import subprocess
import re
import time
import sys
import os
import signal
from multiprocessing import Process
from dotenv import load_dotenv
import os
import requests

load_dotenv()

headers = {"Authorization": "Bearer " + os.getenv('STATION_TOKEN')}


def channel_hopper():
    while True:
        for channel in range(1, 15):  # 2.5 GHz (1-14)
            try:
                subprocess.Popen("iwconfig %s channel %d" %
                                 (interface, channel), shell=True).wait()
                time.sleep(5)
            except KeyboardInterrupt:
                break


def tpcdump():
    ''' Capture probes with tpcdump'''
    while True:

        proc = subprocess.Popen(['tcpdump', '-l', '-I', '-i', interface, '-e', '-s',
                                 '256', 'type', 'mgt', 'subtype', 'probe-req'], stdout=subprocess.PIPE)

        regex = '(-\d+)dBm signal antenna 0.+SA:([0-9a-f]+:[0-9a-f]+:[0-9a-f]+:[0-9a-f]+:[0-9a-f]+:[0-9a-f]+) .+(Probe Request) \((.+)\)'
        while True:
            line = proc.stdout.readline()

            if line == '':
                break

            m = re.search(regex, line)
            if m is not None and len(m.groups()) == 4:
                probe = {
                    'type_id': 2,
                    'signal': m.group(1).rstrip(),
                    'identifier': m.group(2).rstrip(),
                    'ssid': m.group(4).rstrip(),
                    'time': int(time.time()),
                }
                print(probe)
                try:
                    requests.post(os.getenv('API_URL') +
                                  'logs', data=probe, headers=headers)
                except:
                    print("Error reaching the API")


def tshark():
    ''' Capture probes with tshark'''
    while True:

        proc = subprocess.Popen(
            ['tshark', '-i', interface, '-n', '-l', 'subtype', 'probereq'], stdout=subprocess.PIPE)

        regex = '([0-9a-f]+:[0-9a-f]+:[0-9a-f]+:[0-9a-f]+:[0-9a-f]+:[0-9a-f]+)(?:.*?)Probe Request, SN=(\d+), FN=(\d+), Flags=(.*?), SSID=(.*?)$'
        while True:
            line = proc.stdout.readline().decode('utf-8')

            if line == '':
                break

            m = re.search(regex, line)
            if m is not None and len(m.groups()) == 5:
                probe = {
                    'type_id': 2,
                    'identifier': m.group(1).rstrip(),
                    'signal': m.group(2).rstrip(),
                    'ssid': m.group(5).rstrip(),
                    'time': int(time.time()),
                }

                if probe['ssid'] == 'Wildcard (Broadcast)':
                    continue

                print(probe)
                try:
                    response = requests.post(os.getenv('API_URL') +
                                             'logs', data=probe, headers=headers)
                    if response.status_code != 201:
                        print('API Error:', response.content)
                except Exception as e:
                    print('API Error:', str(e))


def signal_handler(signal, frame):
    p.terminate()
    p.join()

    p2.terminate()
    p2.join()

    sys.exit(0)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage %s monitor_interface" % sys.argv[0])
        sys.exit(1)

    interface = sys.argv[1]

    p = Process(target=channel_hopper)
    p.start()

    p2 = Process(target=tshark)
    p2.start()

    # Capture CTRL-C
    signal.signal(signal.SIGINT, signal_handler)
