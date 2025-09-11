# Distributed Task Processing Test

This is a **proof-of-concept** testing the limits of high-throughput job processing using the Procrastinate Python library with PostgreSQL as the backend.

Sample results: on a small database instance (2 CPUs, 2GB RAM), this setup processed
- 100,000 jobs (avg duration = 1s) in 7 minutes and 53 seconds using 50 workers, 
- or 100,000 jobsjobs (avg duration = 0.25s) in 2 minutes using 8 workers (that's about 6k jobs/minute on each worker),
- or 1M jobs (avg duration = 1s) in 1h with less that 100 connections.

This repository provides the code for reproduction (see also sample results under `/perf`) and briefly discusses the trade-offs of this approach compared to dedicated queueing systems. Performance will vary based on workload characteristics, DB tuning, and network latency.

Also, take into account competences, organization etc.

### Approach and rationale
Approach and Rationale
While PostgreSQL is not a dedicated message broker like RabbitMQ or SQS, using it as one offers a powerful advantage: a unified, transactional data architecture. This simplifies the tech stack by leveraging existing infrastructure and operational expertise, avoiding the need to manage a separate queuing service.

This proof-of-concept aims to stress-test this pattern and provide concrete performance data to understand its practical limits.


#### a "Realistic" Workload
To produce meaningful results, the benchmark simulates a common I/O-bound task (e.g., an external API call). Each job is designed to mimic this behavior:

1. Simulate I/O Wait: The worker executes a sleep() command with a duration randomized around a configurable average (e.g., 1 second). This keeps worker CPU usage low, mirroring a process waiting on a network response.
2. Write Result to Database: After the wait, the worker performs an INSERT into a dedicated results table.

This means every task involves at least two database interactions: a SELECT ... FOR UPDATE SKIP LOCKED to acquire the job and an INSERT to store the outcome.

#### What this is Really Measuring
Given this workload, the benchmark specifically measures the efficiency of:
- Procrastinate's scheduling performance under high concurrency - also testing correctness and speed of the custome result storage (implemetend in `papp/utils.py`)
- PostgreSQL's ability to handle thousands of short-lived transactions and its resilience to row-level lock contention.

The general approach of using Postgres as a queue is a well-known architectural trade-off, with valid arguments for and against it. The results here offer a data-driven starting point for deciding if this pattern fits your specific context.

Notice that the general idea of using Postgres to manage queue is [debatable](https://news.ycombinator.com/item?id=39315833) and can be loved or refused depending on the context.


### On the result storage adopted in this test
Procrastinate takes an interesting approach to result storage - it doesn't provide one. Unlike Celery with its pluggable result backends, Procrastinate focuses purely on job queuing and execution, leaving result persistence as an application concern. This is another aspect of this POC.

Our architecture centers around PostgreSQL as both the job queue and result store. The orchestrator generates jobs and schedules them directly into PostgreSQL tables. A pool of 50 worker processes continuously polls for available jobs (or gets them via LISTEN/NOTIFY), processes them, and writes results back to custom tables in the same database (may as well be another DB, but let's keep it simple). This creates a complete audit trail - from job creation through execution to final results - all within a single transactional system.

### Outcome
On a small-sized database instance (2cpu, 2GB of RAM), I was able to process
- 100k jobs in about 8m with 50 workers (200 max connections)
- 1M jobs in about 1h with 60 workers (100 max connections i.e. under a induced connection scarcity)

Please check section Considerations technical thoughts.

# Files
Now you're finally ready to take a look at the repo structure! `papp` contains procrastinate python app

In the root folder, you can find  the following files:
1. `orchestrator.py`: creates jobs to be completed
2. `run_workers.sh`: runs the specified number of workers
3. `check_results.py`: ex-post analysis of completed jobs
4. `e2e_test.py`: runs everuthing e2e and save results

You'd probably most interested in skipping to section "automatically run a test below"

## Run the project manually

Install libraries
> uv sync

Run the database container (adapt as needed, e.g. limiting resources):
> docker rm -f pg-procrastinate && docker run --name pg-procrastinate --detach --rm -p 5434:5432 -e POSTGRES_PASSWORD=password postgres postgres -c max_connections=100

Creates DB, initialize persistence table
> python init_db.py

Initialize the procrastinate app
> procrastinate --app=papp.main.app schema --apply

Schedule a few jobs
> python orchestrator.py --max-jobs 20

### Run a test 

#### Manually

Choose a DB connection, then run this sequentially:

Generate jobs to run a test, with a given prefix for the workers
> python orchestrator.py --max-jobs 500 --avg-duration=1.0

Consume jobs (use prefix to get statistics). Syntax: number_of_workers prefix concurrency
> ./run_workers.sh 1 w_ 4

Check test result
> python check_results.py --prefix=w_

#### Automatically
Edit and run `e2e_test.py`. You'll see outputs both in the shell and under the perf/ folder.

> export PYTHONPATH=. && python e2e_test.py

Here are sample results for the last step (analysis).
In this case, 100k jobs (avg duration: 1s) were completed with 50 workers in about 8 minutes, on a small DB instance (2 cores, 2GB ram) with 200 max connections set on the db level.
```
================================================================================
Executing Query: Job Summary Aggregation
================================================================================
+--------------+-----------+----------------------------+----------------------------+----------------+
|   total_jobs | status    | first_job_at               | last_job_at                | duration       |
|--------------+-----------+----------------------------+----------------------------+----------------|
|       100000 | COMPLETED | 2025-09-09 08:08:16.578210 | 2025-09-09 08:16:10.282077 | 0:07:53.703867 |
+--------------+-----------+----------------------------+----------------------------+----------------+

================================================================================
Executing Query: Completed Jobs per Worker (prefix: 'w_1757404688_')
================================================================================
+-----------------+------------------+-------------------+
| worker_name     |   jobs_completed |   jobs_per_minute |
|-----------------+------------------+-------------------|
| w_1757404688_32 |             2056 |           261.3   |
| w_1757404688_23 |             2046 |           259.959 |
... (omissis)
| w_1757404688_10 |             1917 |           243.754 |
| w_1757404688_36 |             1885 |           239.501 |
+-----------------+------------------+-------------------+
```

Variation: 1M jobs with 100 max connections, 60 workers. Rest of the settings is the same as above:
```
================================================================================
Executing Query: Job Summary Aggregation
================================================================================
+--------------+-----------+----------------------------+----------------------------+----------------+
|   total_jobs | status    | first_job_at               | last_job_at                | duration       |
|--------------+-----------+----------------------------+----------------------------+----------------|
|      1000000 | COMPLETED | 2025-09-09 10:55:29.343527 | 2025-09-09 11:56:45.790988 | 1:01:16.447461 |
+--------------+-----------+----------------------------+----------------------------+----------------+

================================================================================
Executing Query: Completed Jobs per Worker (prefix: 'w_1757409548_')
================================================================================
+-----------------+------------------+-------------------+
| worker_name     |   jobs_completed |   jobs_per_minute |
|-----------------+------------------+-------------------|
| w_1757409548_16 |            17050 |           278.343 |
| w_1757409548_43 |            17032 |           278.017 |
(omissis...)
| w_1757409548_59 |            16428 |           268.292 |
| w_1757409548_53 |            16152 |           271.006 |
+-----------------+------------------+-------------------+
```

# Considerations
## Considerations on DB connections

A common objection to this architecture is database connection limits. The test is open, just run your own.
The test lets you freely choose the number of connections. In practice, the DB will see the following:

Each worker process has its own **single** connection pool shared among all subworkers.
Assuming workers are always active, the total requested connections is proportional to the number of workers $N_w$:

```math
C_{total} = C_{wproc} \cdot N_w
```

Each worker has one connection pool with maximum size $p_{size}$, so the maximum connections requested per worker is simply:
```math
C_{wproc} = p_{size}
```

However, the actual **utilization** depends on how often connections are actively used. Each subworker makes queries independently, so the average number of active connections per worker is:
```math
C_{active\_per\_worker} = S \cdot Q \cdot \frac{L}{T}
```

where:
- $S$ is the number of subworkers (e.g. async jobs being processed on the same worker. `procrastinate` calls this "concurrency")
- $Q$ is the number of queries done when processing a job (depends on implementation)
- $L$ is the query latency (e.g. assume 5-10ms in the same AWS region)
- $T$ is the average job duration (you can set it when running a test)

**Example Calculation** For instance, we make about 5 queries per job with 10ms latency and 1s job duration, using 50 workers:

**Maximum connections requested:**
```math
C_{total} = N_w \cdot p_{size} = 50 \cdot 4 = 200 \text{ connections}
```

**Average active connections:**
```math
C_{active} = N_w \cdot S \cdot Q \cdot \frac{L}{T} = 50 \cdot 5 \cdot 5 \cdot \frac{0.01}{1} = 12.5 \text{ connections}
```

**Connection utilization rate:**
```math
\text{Utilization} = \frac{C_{active}}{C_{total}} = \frac{12.5}{200} = 6.25\%
```

So while the database sees up to 200 connection requests, only ~6 are actively used on average - even under quite conservative assumptions.

Also notice that with 200 connection request we'd be hitting the connection limit on smaller instances.
Solutions can include (i) reducing the max pool size (would be super safe in this case) (ii) adopt pgbouncer connection pooling (or AWS equivalent) to better manage many connections on small instances.


> TODO: write a script to monitor connection usages during the tests

> TODO: add CPU usage monitoring script

## Considerations: what about SQS? Tradeoffs

This approach is not a universal replacement for services like SQS. The main limitation is scalability—you are bound by the resources of your database server.
Should one use a traditional message queue like AWS SQS, or leverage PostgreSQL as a task queue backbone? This decision would shape everything from operational complexity to analytical capabilities.

The PostgreSQL approach offers something compelling that managed queues struggle with: unified data architecture and [CMD-clickability](https://leontrolski.github.io/postgres-as-queue.html). Instead of managing separate systems for job queues, application data, and result storage, everything lives in one transactional database. This means when a job updates both business data and its own completion status, we get true ACID compliance. No worrying about partial failures where the job completes but the status update gets lost.

This unified approach also unlocked powerful analytics capabilities. While SQS gives basic message metrics through CloudWatch, the PostgreSQL setup lets us write complex SQL queries to understand job patterns, identify bottlenecks, and generate detailed performance reports. The same database that processes jobs can instantly tell which workers are most efficient or how job duration correlates with payload size.

| Feature | PostgreSQL Queue | AWS SQS |
|---------|------------------|---------|
| **Setup Complexity** | Low (entrypoint) to High (at scale) | Low (simple config) to Medium (to get observability) |
| **Query Capabilities** | Rich SQL analytics | Basic message filtering |
| **Operational Overhead** | Depends on use case and team | Depends |
| **Transactional Support** | Full ACID compliance | At-least-once delivery |
| **Scalability** | Limited by DB resources | Near-infinite AWS scaling |
| **Latency** | Low (direct DB access) | Higher (network API calls) |
| **Vendor Lock-in** | None (open source) | AWS-specific |
| **Dead Letter Queues** | Provided by `procrastinate` | Built-in feature |
| **Monitoring** | Very simple, end to end | Per service |
| **Scheduled Jobs** | Provided by `procrastinate` | Add a service |
| **Development** | Full local replicability | Testing overhead |


On the postgres side, **Transactional Support** means atomic commits across business data and job state. Example: In a single transaction, you can debit a user's account, mark an order as shipped, and schedule a follow-up email job.

On the other hand, SQS scales to a level that is simply not possible on a single Postgres instance.

## Next Steps
[x] Add a script to monitor active PostgreSQL connections during tests. There's now a nice plot for this.

[x] Implement CPU/Memory usage monitoring for the worker and DB containers. There's now a nice plot for this.

[x] Test `procrastinate` retry mechanisms (e.g. failure probability 5%), will be retried 3 times.

[ ] Spawn batch jobs via the orchestrator (this is the actual bottleneck ATM!)

