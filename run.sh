#!/bin/bash

export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8

ROOT_DIR="."
PYTHON="$ROOT_DIR/.venv/bin/python"

if [ "$1" == "-s" ]
then
  FILE="sceduledpausee.py"
else
  FILE="pausee.py"
fi

cd "$ROOT_DIR"
echo "Starting at $(date)"
echo "Running $PYTHON $FILE"
$PYTHON $FILE
echo "Finished at $(date)"