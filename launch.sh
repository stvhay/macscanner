#!/bin/sh

echo "Checking for .venv directory..."
if [ ! -d ".venv" ]; then
    echo ".venv directory not found."
    rm -rf .venv
    python -m venv .venv
fi

echo "Checking file .deps to see if dependencies have been installed..."
if [ ! -f ".venv/.macscanner_deps" ]; then
    echo "Installing dependencies..."
    .venv/bin/pip install -U pip wheel setuptools
    .venv/bin/pip install -r requirements.txt
    cp -v mac-vendors.txt $(.venv/bin/python -c "import mac_vendor_lookup; mac_vendor_lookup; m = mac_vendor_lookup.MacLookup(); print(m.find_vendors_list())")
    touch .venv/.macscanner_deps
    echo "---------------------------------------------"
fi

echo "Starting MAC address publisher"
.venv/bin/python publish.py &
sleep 1.0
echo "Launching web application"
.venv/bin/uvicorn main:app --reload
