#!/bin/bash

#mac:
export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8

ROOT_DIR="."
#LOG_FILE="$ROOT_DIR/pausee.log"
PYTHON="$ROOT_DIR/.venv/bin/python"

cd "$ROOT_DIR"
echo "Starting at $(date)" 
$PYTHON pausee.py
echo "Finished at $(date)" 