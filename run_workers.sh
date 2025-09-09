#!/bin/bash

# Makes the script executable: chmod +x run_workers.sh
#
# Sample Usage:
#   ./run_workers.sh 5 my-worker-
#
# Arguments:
#   $1: The number of workers to start (defaults to 10).
#   $2: The prefix for each worker's name (defaults to 'w_').
#   $3: The concurrency per worker (defaults to 1).


NUM_WORKERS=${1:-10}
WORKER_PREFIX=${2:-worker_}
CONCURRENCY=${3:-1}


echo "🚀 Starting ${NUM_WORKERS} workers with prefix '${WORKER_PREFIX}'..."

for i in $(seq 1 ${NUM_WORKERS}); do
  # Pass concurrency to each worker
  python run_worker.py --name=${WORKER_PREFIX}$i --concurrency=${CONCURRENCY} &
done

# The 'wait' command will pause the script here until all background jobs are finished.
wait

echo "✅ All workers have completed their tasks."