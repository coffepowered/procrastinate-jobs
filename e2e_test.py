import os
import subprocess
import sys
import time
from pathlib import Path


# ANSI color codes for prettier terminal output
class BColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    WARNING = '\033[93m'

DB_CONNECTION_STRING = os.getenv("DB_CONNECTION_STRING", "")

# Prefix for worker names and result tracking. A timestamp is added for uniqueness.
PREFIX = f"w_{int(time.time())}_"

# Parameters for the job orchestrator. TODO: Orchestrator velociy a bottleneck ATM :) 
MAX_JOBS = 100_000
AVG_DURATION = 0.25

# Parameters for the workers
NUM_WORKERS = 8
CONCURRENCY = 5

# Postgres settings for the test
POSTGRES_MAX_CONN = 50
POSTGRES_CPUS = 2.0
POSTGRES_RAM = "2g"
# we're (on the very) safe side with this formula
pg_ram = ram_mb = int(POSTGRES_RAM.rstrip("g")) * 1024 # back of the envelope calc
calculated_max_conn = ram_mb // 10 - 10  # 10 MB per connection, 10 conn always free

print(f"{BColors.BOLD}Diagnostics (back-of-the-envelope): {BColors.ENDC}")
if NUM_WORKERS * CONCURRENCY > POSTGRES_MAX_CONN:
    print(
        f"{BColors.WARNING}⚠️ You may experience issues with max_connections. "
        f"Required={NUM_WORKERS * CONCURRENCY}, "
        f"Configured={POSTGRES_MAX_CONN}. "
        f"Reduce workers/concurrency or increase max_connections.{BColors.ENDC}"
    )

if calculated_max_conn < POSTGRES_MAX_CONN:
    print(
        f"{BColors.WARNING}⚠️ Postgres may deny new connections. "
        f"Configured max_connections={POSTGRES_MAX_CONN}, "
        f"Estimated safe={calculated_max_conn}. "
        f"Either increase RAM or reduce max_connections.{BColors.ENDC}"
    )
# ==============================================================================

# ---
# Monitoring facilities
# ---
def start_monitoring(test_dir: Path, duration: int = 300) -> subprocess.Popen:
    """
    Starts the performance_monitor.py script as a detached background process.

    Args:
        test_dir: The directory where logs and performance data will be saved.
        duration: The maximum duration for the monitoring script to run.

    Returns:
        The Popen object representing the running monitor process.
    """
    monitor_script_path = "monitor.py"
    log_path = Path(test_dir) / "monitoring.log"
    
    command = [
        sys.executable,  # Use the same python interpreter that is running this script
        monitor_script_path,
        "--output-dir", str(test_dir),
        "--duration", str(duration),
        "--interval", "1"
    ]

    print(f"{BColors.OKCYAN}▶️ Starting background monitoring... | Logging to {log_path}{BColors.ENDC}")
    
    # Open a log file for the monitor's output
    log_file = open(log_path, "w")

    # Use subprocess.Popen to run the command without blocking
    # stdout and stderr are redirected to the log file.
    try:
        monitor_process = subprocess.Popen(
            command,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True
        )
        print(f"{BColors.OKCYAN}✅ Monitoring process started with PID: {monitor_process.pid}{BColors.ENDC}")
        return monitor_process
    except FileNotFoundError:
        print(f"{BColors.FAIL}❌ Error: Command not found. Is '{command[0]}' installed and in your system's PATH?{BColors.ENDC}")
        log_file.close()
        sys.exit(1)


def stop_monitoring(monitor_process: subprocess.Popen):
    """
    Stops the background monitoring process.
    """
    print(f"{BColors.OKCYAN}▶️ Stopping monitoring process (PID: {monitor_process.pid})...{BColors.ENDC}")
    # poll() checks if the process has terminated. If it's None, it's still running.
    if monitor_process.poll() is None:
        # Terminate the process gracefully. This sends a SIGTERM signal.
        monitor_process.terminate()
        try:
            # Wait for up to 10 seconds for the process to terminate.
            monitor_process.wait(timeout=10)
            print(f"{BColors.OKCYAN}✅ Monitoring stopped gracefully.{BColors.ENDC}")
        except subprocess.TimeoutExpired:
            # If it doesn't terminate, force kill it. This sends a SIGKILL signal.
            print(f"{BColors.FAIL}⚠️ Monitoring process did not terminate gracefully. Forcing shutdown...{BColors.ENDC}")
            monitor_process.kill()
    else:
        print(f"{BColors.OKCYAN}✅ Monitoring process had already finished.{BColors.ENDC}")


def print_header(message):
    """Prints a formatted header to the console."""
    print(f"\n{BColors.HEADER}--------------------------------------------------{BColors.ENDC}")
    print(f"{BColors.HEADER} {message}{BColors.ENDC}")
    print(f"{BColors.HEADER}--------------------------------------------------{BColors.ENDC}")

def run_command(command, step_name, test_dir):
    """Runs a shell command, logs stdout/stderr to file."""
    log_path = os.path.join(test_dir, f"{step_name.replace(' ', '_')}.log")
    print(f"{BColors.OKCYAN}▶️ Executing: {' '.join(command)} | Logging to {log_path}{BColors.ENDC}")
    try:
        with open(log_path, "w") as log_file:
            result = subprocess.run(
                command,
                check=True,
                text=True,
                stdout=log_file,
                stderr=subprocess.STDOUT
            )
        if result.stdout:
            print(result.stdout)
    except FileNotFoundError:
        print(f"{BColors.FAIL}❌ Error: Command not found. Is '{command[0]}' installed and in your system's PATH?{BColors.ENDC}")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"{BColors.FAIL}❌ Error during '{step_name}'. Aborting. See {log_path}{BColors.ENDC}")
        sys.exit(1)



def main():
    """Main function to orchestrate the end-to-end test."""
    
    
    test_id = f"jobs{MAX_JOBS}_dur{AVG_DURATION}_w{NUM_WORKERS}_c{CONCURRENCY}_conn{POSTGRES_MAX_CONN}"
    test_dir = os.path.join("perf", test_id)
    os.makedirs(test_dir, exist_ok=True)
    print(f"{BColors.BOLD}🚀 Starting End-to-End Test. Assigned id {test_id}, outputs to {test_dir=}...{BColors.ENDC}")


    print(f"Worker Prefix for this run: {BColors.OKBLUE}{PREFIX}{BColors.ENDC}")
    # 2. Generate Jobs
    print_header("- Step 0: Init db")
    run_command(
        [
            "docker", "rm", "-f", "pg-procrastinate"
        ], 
        "Remove old postgres",
        test_dir=test_dir
    )
    time.sleep(2)
    run_command(
        [
            "docker", "run", "--name", "pg-procrastinate", "--detach", "--rm",
            f"--cpus={POSTGRES_CPUS}", f"--memory={POSTGRES_RAM}",
            "-p", "5434:5432",
            "-e", "POSTGRES_PASSWORD=password", # TODO: read from .env
            "postgres",
            "postgres", "-c", f"max_connections={POSTGRES_MAX_CONN}"
        ],
        "Start postgres",
        test_dir=test_dir
    )
    time.sleep(3) # wait for postgres to be ready
    run_command(["python", "init_db.py"], "Create tracking table and init db", test_dir=test_dir)
    # TODO: don't fail if already initialized
    run_command(["procrastinate", "-vv", "--app=papp.main.app", "schema", "--apply"], "Init App", test_dir=test_dir)


    # 2. Generate Jobs
    print_header("📊 Step 1: Generating Jobs")
    orchestrator_cmd = [
        "python", "orchestrator.py",
        "--max-jobs", str(MAX_JOBS),
        "--avg-duration", str(AVG_DURATION)
    ]
    # TODO: this step is slow with 100k jobs. Consider inserting them in batch
    run_command(orchestrator_cmd, "Job Generation", test_dir=test_dir)
    print(f"{BColors.OKGREEN}✅ Job generation complete.{BColors.ENDC}")

    # 3. Run Workers
    print_header("⚙️ Step 2: Monitoring & Consuming Jobs with Workers")
    monitor_proc = start_monitoring(test_dir, duration=600)

    workers_cmd = [
        "./run_workers.sh",
        str(NUM_WORKERS),
        PREFIX,
        str(CONCURRENCY)
    ]
    run_command(workers_cmd, "Worker Execution", test_dir=test_dir)
    print(f"{BColors.OKGREEN}✅ Job consumption complete.{BColors.ENDC}")
    if monitor_proc:
        stop_monitoring(monitor_proc)

    # 4. Check Results
    print_header("🔍 Step 3: Checking Test Results")
    results_cmd = [
        "python", "check_results.py",
        "--prefix", PREFIX
    ]
    run_command(results_cmd, "Result Check", test_dir=test_dir)
    
    print_header(f"{BColors.OKGREEN}Test Settings: {MAX_JOBS=}, {AVG_DURATION=}, {NUM_WORKERS=},  {CONCURRENCY=}, {POSTGRES_MAX_CONN=}!{BColors.ENDC}")
    print_header(f"{BColors.OKGREEN}🎉 Test Run Finished Successfully!{BColors.ENDC}")


if __name__ == "__main__":
    main()