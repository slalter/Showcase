import re

def remove_non_printable_chars(input_string):
    cleaned_string = re.sub(r'[^\x20-\x7E]', ' ', input_string)
    return cleaned_string

import time
import sys
import os
import asyncio
#a decorator that times each line and makes a log of the time elapsed, compiled by line number. Only works for sync methods.
def time_each_line(func):
    
    async def wrapper_async(*args, **kwargs):
        if os.environ.get('time_guru', None):
            starting_time = time.time()
            trace_lines.trace_paths = ['conversation', 'assignment', 'tool', 'feature']
            trace_lines.last_times = {}
            trace_lines.out = {}
            trace_lines.prev_line = {}
            for path in trace_lines.trace_paths:
                trace_lines.last_times[path] = time.time()
                trace_lines.out[path] = {}
                trace_lines.prev_line[path] = None
            sys.settrace(trace_lines)
            try:
                result = await func(*args, **kwargs)
            finally:
                sys.settrace(None)
            total_time = time.time() - starting_time
            log_text = "Total elapsed time: " + str(total_time) + "\n"
            for path in trace_lines.trace_paths:
                log_text += f"Path: {path}\n"
                sorted_items = sorted(trace_lines.out[path].items(), key=lambda item: sum(item[1]), reverse=True)
                for (file, line), times in sorted_items[:20]:
                    elapsed = sum(times)
                    log_text += f"{file}:{line}: Total time = {elapsed:.6f}s ({elapsed/total_time:.2f}%), Count = {len(times)}\n"
            print(log_text)
        else:
            result = await func(*args, **kwargs)
        return result
        

    def trace_lines(frame, event, arg):
        if event == 'line':
            paths = [path for path in trace_lines.trace_paths if path in frame.f_code.co_filename]
            if paths:
                print(frame.f_code.co_filename, frame.f_lineno)
            if not paths:
                return trace_lines
            for path in paths:
                current_time = time.time()
                elapsed = current_time - trace_lines.last_times[path]
                trace_lines.last_times[path] = current_time
                prev_path = trace_lines.prev_line[path]
                if prev_path and prev_path not in trace_lines.out[path]:
                    trace_lines.out[path][prev_path] = []
                    trace_lines.out[path][prev_path].append(elapsed)
                
                trace_lines.prev_line[path] = (frame.f_code.co_filename, frame.f_lineno)
            return trace_lines

    def wrapper(*args, **kwargs):
        if os.environ.get('time_guru', None):
            starting_time = time.time()
            trace_lines.trace_paths = ['conversation', 'assignment', 'tool', 'feature']
            trace_lines.last_times = {}
            trace_lines.out = {}
            trace_lines.prev_line = {}
            for path in trace_lines.trace_paths:
                trace_lines.last_times[path] = time.time()
                trace_lines.out[path] = {}
                trace_lines.prev_line[path] = None
            sys.settrace(trace_lines)
            try:
                result = func(*args, **kwargs)
            except Exception as e:
                raise
            finally:
                sys.settrace(None)
            total_time = time.time() - starting_time
            log_text = "Total elapsed time: " + str(total_time) + "\n"
            for path in trace_lines.trace_paths:
                log_text += f"Path: {path}\n"
                sorted_items = sorted(trace_lines.out[path].items(), key=lambda item: sum(item[1]), reverse=True)
                for (file, line), times in sorted_items[:20]:
                    elapsed = sum(times)
                    log_text += f"{file}:{line}: Total time = {elapsed:.6f}s ({elapsed/total_time:.2f}%), Count = {len(times)}\n"
            print(log_text)
        else:
            result = func(*args, **kwargs)
        return result


    return wrapper_async if asyncio.iscoroutinefunction(func) else wrapper


class CannotProceedException(Exception):
    '''
    this exception is called from within a flow when the flow cannot proceed due to some error. It shuts down the flow instead of simply telling the LLM something happened.
    Any except block that catches this exception should also raise it, so that the flow can be shut down.
    '''
    pass
