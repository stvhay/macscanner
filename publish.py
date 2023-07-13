"""This module runs Scapy on an interface and publishes the output to a ZMQ PUB socket."""
import argparse
import asyncio
import signal
import aiozmq
import zmq
from scapy.all import sniff
from scapy.all import get_if_list
from scapy.layers.l2 import Ether
from scapy.layers.inet import IP


async def shutdown(signal_name, loop):
    """Cleanup tasks tied to the service's shutdown."""
    print(f"Received exit signal {signal_name}...")
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

    for task in tasks:
        task.cancel()

    print(f"Cancelling {len(tasks)} tasks")
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()


async def publish_mac_addresses(interface: str, bind='tcp://0.0.0.0:5556'):
    """Stream Mac Addresses and IP Addresses"""
    zmq_socket = await aiozmq.create_zmq_stream(zmq.PUB, bind=bind)

    def handle_packet(pkt):
        if Ether in pkt and IP in pkt:
            mac1 = pkt[Ether].src
            mac2 = pkt[Ether].dst
            ip1 = pkt[IP].src
            ip2 = pkt[IP].dst

            nonlocal seq
            zmq_socket.write([f'{mac1},{ip1},{seq}'.encode()])
            print(f'{mac1},{ip1},{seq}')
            seq += 1
            zmq_socket.write([f'{mac2},{ip2},{seq}'.encode()])
            print(f'{mac2},{ip2},{seq}')
            seq += 1


    loop = asyncio.get_event_loop()
    for signame in ['SIGINT', 'SIGTERM']:
        loop.add_signal_handler(
            getattr(signal, signame),
            lambda signame=signame: asyncio.create_task(shutdown(signame, loop)))

    seq = 0
    sniff(iface=interface, prn=handle_packet, store=False)


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Publishes Scapy data to a ZMQ PUB socket.")
    parser.add_argument("--interface", type=str, required=False, default=get_if_list(),
                        help="Interface to listen on. For example: eth0, wlan0 etc.")
    parser.add_argument("--zmq-bind-address", type=str, default='tcp://0.0.0.0:5556',
                        help="ZMQ bind address. Default is tcp://0.0.0.0:5556")
    args = parser.parse_args()

    asyncio.run(publish_mac_addresses(args.interface, args.zmq_bind_address))
