import time
import sys
from papp.main import app
import typer
import random
from papp.tasks import sum
from papp.tasks import sum_with_persistence

app_cli = typer.Typer()


@app_cli.command()
def main(
        max_jobs: int = typer.Option(10, help="Number of jobs to schedule"),
        avg_duration: float = typer.Option(3.0, help="Average duration of each job in seconds")
):
    with app.open():
        a = random.randint(1, 100)
        b = random.randint(1, 100)
        print(f"[main] Scheduling sum({a}, {b})")
        i = 0
        while i < max_jobs: # 200 should take 1m to exectute with 10 workers
            if i % (max_jobs//10) == 0:
                print(f"[main] Scheduled {i} jobs")
            i += 1
            print(f"[main] Scheduling ({a}, {b}) #{i}")
            sum_with_persistence.defer(a=a*i, b=b*i, avg_sleep_time=avg_duration)
            time.sleep(0.002)
        print("[main] Scheduled everything")
        
if __name__ == "__main__":
    app_cli()