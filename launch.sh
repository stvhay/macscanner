#!/bin/bash

# rm -rf .venv
# python -m venv .venv
source .venv/bin/activate
pip install -U pip wheel setuptools
pip install -r requirements.txt
uvicorn main:app --reload
deactivate