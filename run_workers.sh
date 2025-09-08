#!/bin/bash

# Makes the script executable: chmod +x run_workers.sh
#
# Sample Usage:
#   ./run_workers.sh 5 my-worker-
#
# Arguments:
#   $1: The number of workers to start (defaults to 10).
#   $2: The prefix for each worker's name (defaults to 'w_').

NUM_WORKERS=${1:-10}
WORKER_PREFIX=${2:-worker_}

echo "🚀 Starting ${NUM_WORKERS} workers with prefix '${WORKER_PREFIX}'..."

for i in $(seq 1 ${NUM_WORKERS}); do
  # The worker name is now constructed using the prefix and the loop number.
  python run_worker.py --name=${WORKER_PREFIX}$i &
done

# The 'wait' command will pause the script here until all background jobs are finished.
wait

echo "✅ All workers have completed their tasks."