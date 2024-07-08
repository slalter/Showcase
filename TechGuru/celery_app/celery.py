import os
import requests
from kombu import Queue
import traceback
from celery import Task
from celery.schedules import crontab
from celery.exceptions import Retry, MaxRetriesExceededError
from celery.signals import worker_process_init
from celery.result import AsyncResult
from celery import group, chord
from datetime import datetime
import sys
import io
from functools import wraps
from celery import Celery



def make_celery(app):
    celery = Celery(
        app.import_name,
        backend=f'redis://{os.environ["REDIS_NAME"]}:6379/0',
        broker=f'redis://{os.environ["REDIS_NAME"]}:6379/0'
    )
    # Define multiple queues
    celery.conf.task_queues = (
        Queue('high_priority', routing_key='high_priority'),
        Queue('medium_priority', routing_key='medium_priority'),
        Queue('low_priority', routing_key='low_priority')
    )


    # Default queue and routing key
    celery.conf.task_default_queue = 'medium_priority'
    celery.conf.task_default_routing_key = 'medium_priority'
    celery.conf.update({
        'task_acks_late': True,
        'task_reject_on_worker_lost': True,
    }
    )

    celery.conf.update(app.config)

    return celery

from celery.signals import task_failure, task_prerun

@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **extras):
    pass


@task_failure.connect
def handle_task_failure(sender=None, task_id=None, exception=None, **kwargs):
    try:
        sender.retry(countdown=10,queue='low_priority')

    except sender.MaxRetriesExceededError as e:
        if isinstance(exception, Retry):
            return
        print(f"Task failed to retry with exception: {e}")
        return
    except Exception as e:
        if isinstance(e, Retry):
            print(f"Task failed to retry with exception: {e}")
            raise
        else:
            print(f"Task failed with exception: {e}")
            raise 

#not used
def getTaskDecorator(celery):
    def custom_task(*args, **kwargs):
        def decorator(func):
            @celery.task(*args, **kwargs)
            @wraps(func)
            def wrapper(*func_args, **func_kwargs):
                if os.getenv('monitor_memory') and False:
                    # Function to capture memory usage
                    def wrapped_func():
                        return func(*func_args, **func_kwargs)

                    mem_usage = memory_usage(wrapped_func, interval=1, timeout=None)
                    quicklog(f"Peak memory usage for {func.__name__}: {max(mem_usage)} MB")

                return func(*func_args, **func_kwargs)
            
            return wrapper
        
        return decorator

    return custom_task