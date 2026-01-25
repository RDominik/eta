#!/bin/bash

# set virtual environment name
VENV_DIR="venv"

# create virtual environment if not exists
if [ ! -d "$VENV_DIR" ]; then
    echo "create virutal environment..."
    python3 -m venv "$VENV_DIR"
fi

# activate virtual environment
source "$VENV_DIR/bin/activate"

# package installation
echo "Python package installation..."
pip install --upgrade pip
pip install goodwe influxdb-client paho-mqtt


