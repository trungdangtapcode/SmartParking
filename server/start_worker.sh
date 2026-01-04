#!/bin/bash
# Start Parking Monitor Worker

# Activate conda environment
eval "$(conda shell.bash hook)"
conda activate scheduler

# Start worker
cd "$(dirname "$0")"
python parking_monitor_worker.py --interval 5

# Alternative: Run in background
# python parking_monitor_worker.py --interval 5 > worker.log 2>&1 &
# echo $! > worker.pid
# echo "Worker started with PID: $(cat worker.pid)"
