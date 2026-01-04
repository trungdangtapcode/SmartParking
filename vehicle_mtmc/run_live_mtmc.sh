#!/usr/bin/env bash
export LD_LIBRARY_PATH=/home/tin/TensorRT-8.6.1.6/targets/x86_64-linux-gnu/lib:$LD_LIBRARY_PATH

export PYTHONPATH=$(pwd)
python3 mtmc/run_live_mtmc.py --config examples/live_parking.yaml
