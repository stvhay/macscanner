"""Stream Mac addresses"""
import asyncio
import re
import subprocess

from fastapi import FastAPI
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from mac_vendor_lookup import AsyncMacLookup, VendorNotFoundError


async def stream_mac_addresses():
    """Stream Mac Addresses and IP Addresses"""
    pipe = await asyncio.create_subprocess_shell('tcpdump -i en0 -n -e',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    mac_regex = re.compile(r"(([0-9a-fA-F]{2}(?:[:-][0-9a-fA-F]{2}){5}))")
    full_ip_regex = re.compile(
        r"((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(\.\d{1,5}))?"
        r" > "
        r"((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(\.\d{1,5}))?")

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

        yield f'data: {mac1},{ip1}\n\n'
        yield f'data: {mac2},{ip2}\n\n'


app = FastAPI()


maclookup = AsyncMacLookup()
@app.on_event("startup")
async def startup_event():
    """Retrieve updated MAC address prefixes"""
    await maclookup.update_vendors()


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
