# Macscanner

This program launches a little web server that shows you mac addresses on your network.


## Prerequisites

1. A recent version of Python
2. Permissions to run utilities: `tcpdump` and `ping`.
3. The ability to create a Python venv in your environment, which can sometimes require a special system package.


## Instructions

```bash
./launch.sh
```


## Description

- The webserver is asynchronous (uvicorn)
- Build on FastAPI
- Uses very simple zmq pub-sub for message handling.


## Bugs

- Hardcodes the IP network to ping in order to get faster responses from network devices.