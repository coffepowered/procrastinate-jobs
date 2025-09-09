import os
import json
import psycopg
from psycopg import sql
from dotenv import load_dotenv
from tabulate import tabulate
import datetime
import typer

app_cli = typer.Typer()

# Load environment variables from .env file
load_dotenv()

# Database configuration
pgconfig = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": os.environ.get("DB_PORT", 5432),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", "postgres"),
    "dbname": os.environ.get("DB_NAME", None),
}

def run_and_print_query(conn, title, query_sql, params=None):
    """Executes a query and prints the results in a formatted table."""
    print("\n" + "="*80)
    print(f"Executing Query: {title}")
    print("="*80)

    with conn.cursor() as cur:
        try:
            cur.execute(query_sql, params)

            # Fetch column headers from the cursor description
            headers = [desc[0] for desc in cur.description]
            results = cur.fetchall()

            if not results:
                print("Query returned no results.")
            else:
                # Use tabulate to print a nice table
                print(tabulate(results, headers=headers, tablefmt="psql"))

        except psycopg.Error as e:
            print(f"An error occurred: {e}")

@app_cli.command()
def main(
    prefix: str = typer.Option(
        "worker-", help="The prefix of the worker name to filter results by."
    )
):
    """Main function to connect and query the database."""
    try:
        with psycopg.connect(**pgconfig) as conn:
            print("Successfully connected to the database.")
            query_params = (prefix,)

            # --- Query 1: Aggregation Query (with duration) ---
            query1_sql = """
                SELECT
                    COUNT(1) AS total_jobs,
                    status,
                    MIN(created_at) AS first_job_at,
                    MAX(updated_at) AS last_job_at,
                    MAX(updated_at) - MIN(created_at) AS duration
                FROM job_results
                WHERE STARTS_WITH(result ->> 'worker_name', %s)
                GROUP BY status;
            """
            run_and_print_query(conn, "Job Summary Aggregation", query1_sql, params=query_params)

            
            # --- Query 3: Group by worker name to get completed job counts ---
            query3_sql = """
                SELECT
                    result ->> 'worker_name' AS worker_name,
                    COUNT(job_id) AS jobs_completed
                FROM job_results
                WHERE STARTS_WITH(result ->> 'worker_name', %s)
                GROUP BY worker_name
                ORDER BY jobs_completed DESC;
            """

            query3_sql = """
                SELECT
                    result ->> 'worker_name' AS worker_name,
                    COUNT(job_id) AS jobs_completed,
                    -- Calculate jobs per minute, handling cases with zero duration to avoid division-by-zero errors.
                    COUNT(job_id) / NULLIF((EXTRACT(EPOCH FROM (MAX(updated_at) - MIN(created_at))) / 60.0), 0) AS jobs_per_minute
                FROM job_results
                WHERE STARTS_WITH(result ->> 'worker_name', %s)
                GROUP BY worker_name
                ORDER BY jobs_completed DESC;
            """
                        
            run_and_print_query(
                conn,
                f"Completed Jobs per Worker (prefix: '{prefix}')",
                query3_sql,
                params=query_params
            )

            query4_sql = """
            SELECT status, count(1) FROM public.procrastinate_jobs
            where attempts>1 group by status
            """
            run_and_print_query(
                conn,
                "Jobs retried more than once, how did they perform in the end?",
                query4_sql
            )


    except psycopg.Error as e:
        print(f"Failed to connect to or query the database: {e}")
        print("Please ensure your .env file is configured correctly and the database is running.")


if __name__ == "__main__":
    app_cli()