from papp.main import app
import time
import random
from papp.utils import task_with_persistence_shared_conn, task_with_persistence_shared_conn_a
from procrastinate import JobContext
import asyncio

'''
Very Simple test tasks
'''
@app.task(name="sum")
def sum(a, b):
    print(f"Adding {a} + {b}")
    time.sleep(random.random() * 5)
    print("Done")
    return {"result": a + b}

@app.task(name="asum")
async def asum(a, b):
    print(f"Adding {a} + {b}")
    time.sleep(random.random() * 5)
    print("Done")
    return {"result": a + b}


@task_with_persistence_shared_conn(name="sum_with_persistence", pass_context=True, retry=3) # pass context, retry
def sum_with_persistence(context: JobContext, a, b, avg_sleep_time:float=3):
    #if random.random() > 0.5:
    #    raise Exception("Who could have seen this coming?")
    
    print(f"[{context.task.name}] {context.job.id=} on {context.worker_name=} | Adding {a} + {b}")
    time.sleep( random.randint(0, int(avg_sleep_time)*2) ) # 3s on average
    print(f"[{context.task.name}] Done")

    return {"result": a + b,
            "job_id": context.job.id,
            "long_string": "x"*random.randint(100, 2500)}

@task_with_persistence_shared_conn_a(name="asum_with_persistence", pass_context=True, retry=3) # pass context, retry
async def asum_with_persistence(context: JobContext, a, b, avg_sleep_time:float=3, fail_prob: float=0):
    random_float = random.random()
    if fail_prob > 0:
        if random_float > 1-fail_prob:
            raise ValueError(f"This is failed! Got {random_float}")
        
    print(f"[{context.task.name}] {context.job.id=} on {context.worker_name=} | Adding {a} + {b}")
    await asyncio.sleep(random.randint(0, int(avg_sleep_time) * 2))
    print(f"[{context.task.name}] Done")

    return {"result": a + b,
            "job_id": context.job.id,
            "long_string": "x"*random.randint(100, 2500),
            "meta": {"fail_prob": fail_prob, "random_float": random_float}}
