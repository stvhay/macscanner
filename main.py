"""Stream Mac addresses"""
import asyncio
import re
import signal
import subprocess

import aiozmq
import zmq

from fastapi import FastAPI
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from mac_vendor_lookup import AsyncMacLookup, VendorNotFoundError


zmq_context = zmq.Context()


async def ping(ip):
    """Ping an IP address"""
    result = await asyncio.create_subprocess_shell(f"ping -c 1 {ip}",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    await result.communicate()

# CODE SMELL: Hardcoding a subnet.
async def ping_subnet():
    """Ping every IP address on the 172.16.0.0/24 subnet"""
    await asyncio.sleep(1.0)
    tasks = []
    for i in range(1, 255):
        ip = f"172.16.0.{i}"
        tasks.append(ping(ip))
    await asyncio.gather(*tasks)


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


async def publish_mac_addresses():
    """Stream Mac Addresses and IP Addresses"""
    zmq_socket = await aiozmq.create_zmq_stream(zmq.PUB, bind='tcp://*:5556')
    pipe = await asyncio.create_subprocess_shell('tcpdump -l -i en0 -n -e',
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

        zmq_socket.write([f'{mac1},{ip1}\n\n'.encode()])
        zmq_socket.write([f'{mac2},{ip2}\n\n'.encode()])


async def stream_mac_addresses():
    """Stream Mac Addresses and IP Addresses"""
    socket = await aiozmq.create_zmq_stream(zmq.SUB, connect='tcp://localhost:5556')
    socket.transport.setsockopt(zmq.SUBSCRIBE, b"")

    asyncio.create_task(ping_subnet())

    while True:
        messages = await socket.read()
        for raw_message in messages:
            message = raw_message.decode('utf-8')
            yield f"data: {message}\n\n"


app = FastAPI()


maclookup = AsyncMacLookup()
@app.on_event("startup")
async def startup_event():
    """Retrieve updated MAC address prefixes and start the mac address stream"""
    asyncio.create_task(publish_mac_addresses())


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """Root level redirect to index.html"""
    return RedirectResponse(url="/static/index.html")


@app.get("/stream")
async def read_stream():
    """Stream MAC addresses and IP addresses separated by a comma"""
    return StreamingResponse(stream_mac_addresses(), media_type="text/event-stream")


@app.get("/vendor/{mac}")
async def get_mac_vendor(mac: str):
    """Handler to get the MAC vendor"""
    try:
        vendor = await maclookup.lookup(mac)
    except VendorNotFoundError:
        vendor = ""
    return {"vendor": vendor}
