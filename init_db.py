
import os
from dotenv import load_dotenv
import psycopg

load_dotenv()

# Database configuration
pgconfig = {"host": os.environ["DB_HOST"], "port": os.environ["DB_PORT"], "user": os.environ["DB_USER"], "password": os.environ["DB_PASSWORD"], "dbname": os.environ.get("DB_NAME", "postgres")}
pg_config_default = pgconfig.copy()
pg_config_default["dbname"] = "postgres"

# SQL for creating the results table
CREATE_RESULTS_TABLE = """
DROP TABLE IF EXISTS job_results;
CREATE TABLE IF NOT EXISTS job_results (
    job_id INTEGER PRIMARY KEY,
    task_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    result JSONB,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_job_results_task_name ON job_results(task_name);
CREATE INDEX IF NOT EXISTS idx_job_results_status ON job_results(status);
"""


def create_database_if_not_exists():
    """Ensure database exists, creating it if necessary"""
    db_name = pgconfig['dbname']
    if pgconfig['dbname'] == 'postgres':
        return  # Don't try to create the default db
    with psycopg.connect(**pg_config_default, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (db_name,))
            exists = cur.fetchone()
            if not exists:
                print(f"Database {db_name} does not exist. Creating...")
                # Use SQL identifier to safely escape the database name
                cur.execute(psycopg.sql.SQL("CREATE DATABASE {};").format(
                    psycopg.sql.Identifier(db_name)
                ))
                print(f"Database {db_name} created.")
            else:
                print(f"Database {db_name} already exists.")

def setup_database():
    """Initialize the database schema and show max connections."""
    print("Setting up database schema for job persistence...")
    with psycopg.connect(**pgconfig) as conn:
        with conn.cursor() as cur:
            # Setup the table
            cur.execute(CREATE_RESULTS_TABLE)
            
            
            # Query the server for the max_connections setting
            cur.execute("SHOW max_connections;")
            
            # fetchone() retrieves the next row of a query result set
            # It returns a single tuple, so we access the first element [0]
            max_connections = cur.fetchone()[0]
            
            print(f"PostgreSQL max connections: {max_connections} 🔌")
            
            print("Database schema setup complete.")
            conn.commit()

if __name__ == "__main__":
    create_database_if_not_exists()
    setup_database()