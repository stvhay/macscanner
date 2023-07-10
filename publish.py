"""This module runs tcpdump on an interface and publishes the output to a ZMQ PUB socket."""
import argparse
import asyncio
import re
import signal
import subprocess
import aiozmq
import zmq


async def shutdown(signal_name, loop, pipe):
    """Cleanup tasks tied to the service's shutdown."""
    print(f"Received exit signal {signal_name}...")
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

    for task in tasks:
        task.cancel()

    print(f"Cancelling {len(tasks)} tasks")
    await asyncio.gather(*tasks, return_exceptions=True)
    pipe.terminate()  # Terminate the subprocess
    loop.stop()


async def publish_mac_addresses(interface: str, bind='tcp://0.0.0.0:5556'):
    """Stream Mac Addresses and IP Addresses"""
    zmq_socket = await aiozmq.create_zmq_stream(zmq.PUB, bind=bind)
    pipe = await asyncio.create_subprocess_shell(f'tcpdump -l -i {interface} -n -e',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)

    mac_regex = re.compile(r"(([0-9a-fA-F]{2}(?:[:-][0-9a-fA-F]{2}){5}))")
    full_ip_regex = re.compile(
        r"((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(\.\d{1,5})?)?"
        r" > "
        r"((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(\.\d{1,5})?)?")

    loop = asyncio.get_event_loop()
    for signame in ['SIGINT', 'SIGTERM']:
        loop.add_signal_handler(
            getattr(signal, signame),
            lambda signame=signame: asyncio.create_task(shutdown(signame, loop, pipe)))

    seq = 0
    while True:
        line = await pipe.stdout.readline()
        line = line.decode('utf-8').strip()
        macs = mac_regex.findall(line)
        ips = full_ip_regex.findall(line)

        # Extract the MAC addresses
        if len(macs) >= 2:
            mac1 = macs[0][0]
            mac2 = macs[1][0]
        else:
            continue  # Skip if MAC addresses are not found

        # Extract the IP addresses
        ip1 = ips[1][1] if ips and len(ips)==2 and ips[1][1] else ''
        ip2 = ips[1][4] if ips and len(ips)==2 and ips[1][4] else ''

        zmq_socket.write([f'{mac1},{ip1},{seq}'.encode()])
        seq += 1
        zmq_socket.write([f'{mac2},{ip2},{seq}'.encode()])
        seq += 1

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Publishes tcpdump data to a ZMQ PUB socket.")
    parser.add_argument("--interface", type=str, required=True, 
                        help="Interface to listen on. For example: eth0, wlan0 etc.")
    parser.add_argument("--zmq-bind-address", type=str, default='tcp://0.0.0.0:5556',
                        help="ZMQ bind address. Default is tcp://0.0.0.0:5556")
    args = parser.parse_args()

    asyncio.run(publish_mac_addresses(args.interface, args.zmq_bind_address))
