from papp.main import app
import typer
import logging

app_cli = typer.Typer()


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

@app_cli.command()
def run_workers(
    concurrency: int = typer.Option(1, help="Concurrency per worker"),
    queues: str = typer.Option(None, help="Comma-separated list of queues (leave empty for all)"),
    name: str = typer.Option("worker", help="worker name"),
    delete_jobs: str = typer.Option("never", help="Delete jobs policy"),
    wait: bool = typer.Option(False, help="Shutdown when no jobs to do"),
):
    # example
    qlist = queues.split(",") if queues else None
    logging.info(f"Starting worker with concurrency {concurrency}, queues={qlist}, delete_jobs={delete_jobs}, wait={wait}")

    logging.info(f"Spawning worker: {name}")
    app.run_worker(
        queues=qlist,
        name=name,
        concurrency=concurrency,
        delete_jobs=delete_jobs,
        wait=wait
    )
    logging.info("Started.")

if __name__ == "__main__":
    app_cli()