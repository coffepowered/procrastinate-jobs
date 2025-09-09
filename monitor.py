import os
import time
import csv
from pathlib import Path
from datetime import datetime
import signal
import typer
import psycopg2
import pandas as pd
import docker
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from dotenv import load_dotenv

load_dotenv()
# --- Database Connection Details ---
# Loaded from environment variables.
pgconfig = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": os.environ.get("DB_PORT", 5434),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", "password"),
    "dbname": os.environ.get("DB_NAME", "postgres"),
}

# --- SQL Query to fetch KPIs from pg_stat_activity ---
# This single query efficiently gathers connection stats and lock contention info.
PG_STATS_QUERY = """
SELECT
    COUNT(*) AS total_connections,
    COUNT(*) FILTER (WHERE state = 'active') AS active_connections,
    COUNT(*) FILTER (WHERE state = 'idle') AS idle_connections,
    COUNT(*) FILTER (WHERE wait_event_type = 'Lock') AS lock_waits,
    COUNT(*) FILTER (WHERE wait_event IS NOT NULL) AS waiting_connections
FROM pg_stat_activity;
"""

app = typer.Typer()


def get_docker_stats(container):
    """Fetches and calculates CPU and Memory usage for a Docker container."""
    stats = container.stats(stream=False)

    # --- Memory Calculation ---
    mem_usage = stats.get("memory_stats", {}).get("usage", 0)
    mem_limit = stats.get("memory_stats", {}).get("limit", 1)
    mem_percent = (mem_usage / mem_limit) * 100 if mem_limit > 0 else 0

    # --- CPU Calculation (mimics `docker stats` command) ---
    cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
    system_cpu_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]

    percpu_usage_list = stats["cpu_stats"]["cpu_usage"].get("percpu_usage", [])
    num_cpus = stats["cpu_stats"].get("online_cpus", len(percpu_usage_list) or 1)

    cpu_percent = 0.0
    if system_cpu_delta > 0.0 and cpu_delta > 0.0:
        cpu_percent = (cpu_delta / system_cpu_delta) * num_cpus * 100.0

    return {
        "cpu_percent": round(cpu_percent, 2),
        "memory_percent": round(mem_percent, 2),
        "memory_usage_mb": round(mem_usage / (1024 * 1024), 2),
    }


def generate_plots(df: pd.DataFrame, output_dir: Path):
    """Generates a summary plot of all collected metrics."""
    output_path = output_dir / "monitoring_summary.png"
    typer.echo(f"📊 Generating plot at {output_path}")

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp')

    fig, axes = plt.subplots(4, 1, figsize=(15, 20), sharex=True)
    fig.suptitle("PostgreSQL Performance Monitoring", fontsize=16)

    # Plot 1: CPU Usage
    axes[0].plot(df.index, df["cpu_percent"], label="DB CPU Usage (%)", color="blue", alpha=0.8)
    axes[0].set_ylabel("CPU (%)")
    axes[0].set_title("Container CPU Usage")
    axes[0].grid(True, linestyle='--', alpha=0.6)
    axes[0].legend()
    axes[0].set_ylim(bottom=0)

    # Plot 2: Memory Usage
    axes[1].plot(df.index, df["memory_percent"], label="DB Memory Usage (%)", color="green", alpha=0.8)
    axes[1].set_ylabel("Memory (%)")
    axes[1].set_title("Container Memory Usage")
    axes[1].grid(True, linestyle='--', alpha=0.6)
    axes[1].legend()
    axes[1].set_ylim(bottom=0)

    # Plot 3: DB Connections
    axes[2].plot(df.index, df["total_connections"], label="Total Connections", color="purple")
    axes[2].plot(df.index, df["active_connections"], label="Active Connections", color="orange", linestyle='--')
    axes[2].set_ylabel("Connections")
    axes[2].set_title("Database Connections")
    axes[2].grid(True, linestyle='--', alpha=0.6)
    axes[2].legend()
    axes[2].set_ylim(bottom=0)

    # Plot 4: Lock Contentions
    axes[3].plot(df.index, df["lock_waits"], label="Row Lock Waits", color="red")
    axes[3].set_ylabel("Count of Waits")
    axes[3].set_title("Row-Level Lock Contention")
    axes[3].grid(True, linestyle='--', alpha=0.6)
    axes[3].legend()
    axes[3].set_ylim(bottom=0)

    # Formatting the x-axis
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    plt.xlabel("Time")
    plt.xticks(rotation=45)
    plt.tight_layout(rect=[0, 0, 1, 0.97])

    plt.savefig(output_path)
    plt.close()


@app.command()
def run(
    output_dir: Path = typer.Option("perf", help="Directory to save results (CSV and plot)."),
    interval: float = typer.Option(1.0, "--interval", "-i", help="Polling interval in seconds."),
    duration: int = typer.Option(600, "--duration", "-d", help="Total monitoring duration in seconds."),
    container_name: str = typer.Option("pg-procrastinate", help="Name of the PostgreSQL Docker container."),
):
    """
    Monitors a PostgreSQL instance running in Docker for performance metrics.

    Collects CPU/Memory usage and connection/lock statistics. Saves results
    incrementally to a CSV and generates a summary plot at the end.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "monitoring_data.csv"

    typer.echo(f"🚀 Starting monitoring for {duration} seconds...")
    typer.echo(f"   - Polling interval: {interval}s")
    typer.echo(f"   - Docker container: '{container_name}'")
    typer.echo(f"   - Saving data to: {csv_path}")

    # --- Graceful Shutdown Handler ---
    # This class will be raised when SIGTERM is caught.
    class GracefulExit(SystemExit):
        pass

    # The handler function that raises our custom exception.
    def signal_handler(signum, frame):
        typer.echo("\n🛑 SIGTERM received, shutting down gracefully...")
        raise GracefulExit()
    
    signal.signal(signal.SIGTERM, signal_handler)  # install the signal handler


    start_time = time.time()
    
    # Define the headers for the CSV file.
    fieldnames = [
        "timestamp", "cpu_percent", "memory_percent", "memory_usage_mb",
        "total_connections", "active_connections", "idle_connections",
        "lock_waits", "waiting_connections"
    ]

    try:
        # Initialize clients
        docker_client = docker.from_env()
        pg_conn = psycopg2.connect(**pgconfig)
        pg_conn.autocommit = True
        pg_cursor = pg_conn.cursor()
        container = docker_client.containers.get(container_name)
        typer.echo("✅ Connected to Docker and PostgreSQL.")

        # Open the CSV file and create a writer object.
        # Data will be appended row-by-row within the loop.
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            while time.time() - start_time < duration:
                loop_start = time.time()

                # 1. Collect metrics
                timestamp = datetime.now().isoformat()
                docker_stats = get_docker_stats(container)

                pg_cursor.execute(PG_STATS_QUERY)
                pg_stats = dict(zip([desc[0] for desc in pg_cursor.description], pg_cursor.fetchone()))

                # 2. Combine and store metrics
                current_metrics = {
                    "timestamp": timestamp,
                    **docker_stats,
                    **pg_stats,
                }
                
                # MODIFIED: Write the current metrics directly to the CSV file.
                writer.writerow(current_metrics)
                csvfile.flush() # Ensure the data is written to disk immediately.

                # 3. Print progress
                progress = (time.time() - start_time) / duration * 100
                typer.echo(
                    f"\r[{progress:3.0f}%] CPU: {current_metrics['cpu_percent']:.1f}% | "
                    f"Mem: {current_metrics['memory_percent']:.1f}% | "
                    f"Active Conn: {current_metrics['active_connections']} | "
                    f"Lock Waits: {current_metrics['lock_waits']}",
                    nl=False,
                )

                # 4. Wait for the next interval
                elapsed = time.time() - loop_start
                time.sleep(max(0, interval - elapsed))

    except docker.errors.NotFound:
        typer.secho(f"Error: Docker container '{container_name}' not found.", fg=typer.colors.RED, err=True)
        return
    except psycopg2.OperationalError as e:
        typer.secho(f"Error connecting to PostgreSQL: {e}", fg=typer.colors.RED, err=True)
        return
    except (KeyboardInterrupt, GracefulExit):
        typer.echo("\n🛑 Monitoring interrupted by user or signal.")
    finally:
        if 'pg_conn' in locals() and pg_conn:
            pg_conn.close()

        typer.echo("\n✅ Monitoring finished.")

        if not csv_path.exists() or csv_path.stat().st_size <= len(','.join(fieldnames)):
            typer.echo("No data collected. Exiting without generating a plot.")
        else:
            # --- Read saved data and generate plots ---
            typer.echo(f"💾 Raw data saved to {csv_path}")
            df = pd.read_csv(csv_path)
            generate_plots(df, output_dir)

    typer.echo("\n✅ Monitoring finished.")

    # Check if any data was actually written before trying to create a plot.
    if not csv_path.exists() or csv_path.stat().st_size <= len(','.join(fieldnames)):
        typer.echo("No data collected. Exiting without generating a plot.")
        return

    # --- Read saved data and generate plots ---
    typer.echo(f"💾 Raw data saved to {csv_path}")
    df = pd.read_csv(csv_path)
    generate_plots(df, output_dir)


if __name__ == "__main__":
    app()
