"""Stream Mac addresses"""
import asyncio
from ipaddress import IPv4Network
import json
import subprocess

from fastapi import FastAPI
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from mac_vendor_lookup import AsyncMacLookup, VendorNotFoundError
from pydantic import BaseModel
import aiozmq
import zmq


SYSTEMS = json.load(open("systems.json", 'r'))

class Subnet(BaseModel):
    """Defines a basic IPV4 subnet model as a string."""
    network: str


class PublishParams(BaseModel):
    """Defines a basic IPV4 subnet model as a string."""
    interface: str
    timeout: int=300


class Publisher:
    """This class manages the process that is publishing to the zmq socket."""
    process = None
    timeout_task = None

    @classmethod
    async def publish(cls, params:PublishParams):
        """Run the tcpdump publisher for the given subnet."""

        if cls.process:
            cls.stop()
        cls.process = await asyncio.create_subprocess_exec(".venv/bin/python",
                                        "publish.py", 
                                        "--interface", params.interface,
                                        stdout=asyncio.subprocess.PIPE,
                                        stderr=asyncio.subprocess.PIPE)
        cls.timeout_task = asyncio.create_task(cls.stop_after_timeout(params.timeout))

    @classmethod
    async def stop_after_timeout(cls, timeout):
        """Stop publisher after a given timeout."""
        await asyncio.sleep(timeout)
        if cls.process is not None:
            await cls.stop()

    @classmethod
    async def stop(cls):
        """Stop the publisher."""
        if cls.timeout_task is not None:
            cls.timeout_task.cancel()
            cls.timeout_task = None
        if cls.process:
            try:
                cls.process.terminate()
                await cls.process.wait()
            except ProcessLookupError:
                print("The process has already been terminated.")
            finally:
                cls.process = None



async def ping(ip_addr):
    """Ping an IP address"""
    result = await asyncio.create_subprocess_shell(f"ping -c 1 {ip_addr}",
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

    last_seq = None
    while True:
        messages = await socket.read()
        for raw_message in messages:
            mac, ip_addr, seq = raw_message.decode('utf-8').split(',')
            seq = int(seq)
            if last_seq is not None and last_seq != seq - 1:
                print("Dropped message.")
            last_seq = seq
            yield f"data: {mac},{ip_addr}\n\n"


zmq_context = zmq.Context()
maclookup = AsyncMacLookup()

app = FastAPI()
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


@app.get("/system/{mac}")
async def get_mac_vendor(mac: str):
    """Handler to get the MAC vendor"""
    lookup = SYSTEMS.get(mac[0:8], None)
    if lookup:
        return {"system": lookup}
    return {"system": ""}


@app.post("/ping")
async def ping_network(subnet: Subnet):
    """Pings a subnet to generate packets that tell you where devices are."""
    await ping_subnet(subnet.network)
    return {"message": f"Ping requests sent for subnet: {subnet.network}"}


@app.post("/publish")
async def publish(params: PublishParams):
    """Runs the tcpdump publisher.py in a separate process."""    
    # If a process is already running, terminate it.
    await Publisher.publish(params)
    return {"message": f"Started publish.py with interface {params.interface}"}
