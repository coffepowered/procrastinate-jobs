from procrastinate import App
from procrastinate import PsycopgConnector
import sys
import os
from dotenv import load_dotenv

# Task declaration
import random
import time
from procrastinate import JobContext
import json

#from tasks import sum_with_persistence

load_dotenv()

pgconfig = {"host": os.environ["DB_HOST"],
            "port": os.environ["DB_PORT"],
            "user": os.environ["DB_USER"],
            "password": os.environ["DB_PASSWORD"],
            "dbname": os.environ["DB_NAME"]}

app = App(
    connector=PsycopgConnector( # learn more about connectors: https://procrastinate.readthedocs.io/en/stable/howto/basics/connector.html
        kwargs=pgconfig
    ),
    import_paths=["papp.tasks"]  # where to find tasks (can be a list
)

@app.task(name="sum")
def sum(a, b):
    print(f"Adding {a} + {b}")
    time.sleep(random.random() * 5)
    print("Done")
    return {"result": a + b}

    
def main():
    with app.open():
        a = int(sys.argv[1])
        b = int(sys.argv[2])
        print(f"[main] Scheduling sum({a}, {b})")
        MAX_JOBS = 2400
        i = 0
        while i < MAX_JOBS: # 200 should take 1m to exectute with 10 workers
            if i % (MAX_JOBS//10) == 0:
                print(f"[main] Scheduled {i} jobs")
            i += 1
            print(f"[main] Scheduling sum_spawns_job({a}, {b}) #{i}")
            sum.defer(a=a*i, b=b*i)
            time.sleep(0.002)
        print("[main] Scheduled everything")
        

if __name__ == "__main__":
    main()