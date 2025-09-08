from papp.main import app
import time
import random
from papp.utils import task_with_persistence_shared_conn
from procrastinate import JobContext

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
def sum_with_persistence(context: JobContext, a, b):
    #if random.random() > 0.5:
    #    raise Exception("Who could have seen this coming?")
    
    print(f"[{context.task.name}] {context.job.id=} on {context.worker_name=} | Adding {a} + {b}")
    time.sleep( random.randint(0, 6) ) # 3s on average
    print(f"[{context.task.name}] Done")

    return {"result": a + b,
            "job_id": context.job.id,
            "long_string": "x"*random.randint(100, 2500)}
