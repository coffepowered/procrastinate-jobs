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

@app_cli.command(
        prefix = ...
)
def main():
    """Main function to connect, populate, and query the database."""
    try:
        with psycopg.connect(**pgconfig) as conn:
            print("Successfully connected to the database.")

            where_clause = ... # select where result->>'worker_name' starts with a given prefix

            # --- Query 1: Aggregation Query ---
            query1_sql = "SELECT COUNT(1) AS total_jobs, MIN(created_at) AS first_job_at, MAX(updated_at) AS last_job_at FROM job_results;"
            run_and_print_query(conn, "Job Summary Aggregation", query1_sql)

            # --- Query 2: Detailed View with JSON extraction ---
            # This query selects all columns and also extracts 'worker_name' from the JSONB result field
            query2_sql = """
                SELECT 
                    job_id, 
                    task_name, 
                    status,
                    result ->> 'worker_name' AS worker_name,
                    created_at
                FROM job_results
                WHERE result ->> 'worker_name' ...
                ORDER BY job_id DESC;
            """
            run_and_print_query(conn, "Detailed Job Results (with worker_name)", query2_sql)

    except psycopg.Error as e:
        print(f"Failed to connect to or query the database: {e}")
        print("Please ensure your .env file is configured correctly and the database is running.")


if __name__ == "__main__":
    app_cli()
