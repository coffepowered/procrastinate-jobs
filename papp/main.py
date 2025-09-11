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
        kwargs=pgconfig,
        min_size=1,
        max_size=2,
    ),
    import_paths=["papp.tasks"]  # where to find tasks (can be a list
)
