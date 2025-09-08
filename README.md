# procrastinate-jobs
Tests with procrastinate python library

Folders
- `papp` contains procrastinate python app

## Run the project

Install libraries
> uv sync


Run the database container (adapt as neede):
> docker rm -f pg-procrastinate && docker run --name pg-procrastinate --detach --rm -p 5434:5432 -e POSTGRES_PASSWORD=password postgres postgres -c max_connections=100


Creates DB, initialize persistence table
> python init_db.py

Initialize the procrastinate app
> procrastinate --app=papp.main.app schema --apply

