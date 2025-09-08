from papp import main
from procrastinate import JobContext
import json
# job persistence
import functools
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

def render_query(query_template, **params):
    """
    Renders a SQLAlchemy parameterized query into a raw SQL string
    with literal values, without needing a database connection.
    """
    query = text(query_template).bindparams(**params)  # 👈 bind params here
    compiled_query = query.compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True}
    )
    return str(compiled_query)

def task_with_persistence_shared_conn(original_func=None, **task_kwargs):
    """
    Alternative approach: Use Procrastinate's own connection pool
    This avoids creating a separate connection pool
    """
    def wrap(func):
        from papp import main as app_instance # lazy import to avoid circular imports

        @functools.wraps(func)
        async def new_func(context: JobContext, *job_args, **job_kwargs):
            job_id = context.job.id
            task_name = context.task.name
            worker_name = context.worker_name
            
            print(f"[MIDDLEWARE] Worker {worker_name}: Starting job {job_id} ({task_name})")
            # Use ON CONFLICT to handle job retries gracefully. This marks the job as RUNNING.
            query_start_template = (
                "INSERT INTO job_results (job_id, task_name, status, updated_at) "
                "VALUES (:job_id, :task_name, 'RUNNING', NOW()) "
                "ON CONFLICT (job_id) DO UPDATE SET status = 'RUNNING', updated_at = NOW()"
            )
            query_start = render_query(
                query_start_template, job_id=job_id, task_name=task_name
            )
            print(query_start)
            await context.app.connector.execute_query_async(query_start)
            
            try:
                result = func(context, *job_args, **job_kwargs)
                # result is a json b field
                #await context.app.connector.execute_query_async(... )

                # hack
                result["worker_name"] = worker_name
                
                # On success, update the job status to COMPLETED and store the result
                query_success_template = (
                    "UPDATE job_results SET status = 'COMPLETED', result = :result, "
                    "error_message = NULL, updated_at = NOW() WHERE job_id = :job_id"
                )
                query_success = render_query(
                    query_success_template, result=json.dumps(result), job_id=job_id
                )
                await context.app.connector.execute_query_async(query_success)

                
                print(f"[MIDDLEWARE] Worker {worker_name}: Job {job_id} completed successfully")
                return result
                
            except Exception as e:
                print(f"[MIDDLEWARE] Worker {worker_name}: Job {job_id} failed: {e}")
                error_message = str(e)

                # On failure, update the status to FAILED and record the error message
                query_fail_template = (
                    "UPDATE job_results SET status = 'FAILED', error_message = :error_message, "
                    "updated_at = NOW() WHERE job_id = :job_id"
                )
                query_fail = render_query(
                    query_fail_template, error_message=error_message, job_id=job_id
                )
                await context.app.connector.execute_query_async(query_fail)
                raise

        # Always pass context and apply the procrastinate task decorator
        task_kwargs['pass_context'] = True

        return app_instance.app.task(**task_kwargs)(new_func)

    if not original_func:
        return wrap
    return wrap(original_func)


