"""Stream Mac addresses"""
import asyncio
from ipaddress import IPv4Network
import subprocess

from fastapi import FastAPI
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from mac_vendor_lookup import AsyncMacLookup, VendorNotFoundError
from pydantic import BaseModel
import aiozmq
import zmq

class Subnet(BaseModel):
    """Defines a basic IPV4 subnet model as a string."""
    network: str

zmq_context = zmq.Context()

async def ping(ip):
    """Ping an IP address"""
    result = await asyncio.create_subprocess_shell(f"ping -c 1 {ip}",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    await result.communicate()

async def ping_subnet(subnet: str):
    """Ping every IP address on the specified subnet"""
    network = IPv4Network(subnet)
    tasks = [ping(str(ip)) for ip in network.hosts()]
    await asyncio.gather(*tasks)


async def stream_mac_addresses():
    """Stream Mac Addresses and IP Addresses"""
    socket = await aiozmq.create_zmq_stream(zmq.SUB, connect='tcp://localhost:5556')
    socket.transport.setsockopt(zmq.SUBSCRIBE, b"")

    print("Streaming...")
    last_seq = None
    while True:
        messages = await socket.read()
        for raw_message in messages:
            mac, ip, seq = raw_message.decode('utf-8').split(',')
            seq = int(seq)
            if last_seq is not None and last_seq != seq - 1:
                print("Dropped message.")
            last_seq = seq
            yield f"data: {mac},{ip}\n\n"


app = FastAPI()


maclookup = AsyncMacLookup()
# @app.on_event("startup")
# async def startup_event():
#     """Retrieve updated MAC address prefixes and start the mac address stream"""
#     asyncio.create_task(publish_mac_addresses())


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

@app.post("/ping")
async def ping_network(subnet: Subnet):
    """Pings a subnet to generate packets that tell you where devices are."""
    print(subnet)
    await ping_subnet(subnet.network)
    return {"message": f"Ping requests sent for subnet: {subnet.network}"}
