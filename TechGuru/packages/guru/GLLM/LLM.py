from openai import OpenAI, AsyncOpenAI
import json
import time
import numpy as np
from .config import get_api_key, get_logging_path, get_default_model
import os
import csv
from datetime import datetime, timedelta
import re
import requests
import asyncio
import aiohttp
import traceback
from openai import APITimeoutError
from .log import Log
from concurrent.futures import ThreadPoolExecutor
MAGIC_WORDS = "Take a deep breath. Let's think step-by-step.\n"
AZURE_RESOURCE_NAME = os.environ.get("AZURE_RESOURCE_NAME")
AZURE_API_KEY = os.environ.get("AZURE_API_KEY")
AZURE_COMPLETION_MODEL = os.environ.get("AZURE_COMPLETION_MODEL")

model = get_default_model()
temperature = 0.5

#set GLLM_LOGGING_PATH to a path in the env variables to save usage stats in a csv.
GLLM_LOGGING_PATH = get_logging_path()
sessionId=""
if GLLM_LOGGING_PATH and not os.path.exists(GLLM_LOGGING_PATH):
    os.makedirs(GLLM_LOGGING_PATH)
if GLLM_LOGGING_PATH:
    current_datetime = datetime.now().strftime('%m-%d-%y')
    pattern = re.compile(rf'{re.escape(current_datetime)}-(\d+)\.csv')
    highest_integer = None
    highest_filename = None
    for filename in os.listdir(GLLM_LOGGING_PATH):
        match = pattern.match(filename)
        if match:
            # Extract the integer from the filename
            file_integer = int(match.group(1))
            
            # Check if it's the highest integer so far
            if highest_integer is None or file_integer > highest_integer:
                highest_integer = file_integer
                highest_filename = filename
    if highest_integer:
        newInt = highest_integer + 1
    else:
        newInt = 1
    sessionId = f"{current_datetime}-{newInt}"
DEFAULT_TIMEOUT = 120
#openai
OPEN_AI_KEY = get_api_key()

#if both auths exist, azure by default.
if not os.environ.get("GLLM_MODE", ""):
    if os.environ.get("AZURE_RESOURCE_NAME", None):
        os.environ['GLLM_MODE'] = 'AZURE'
    else:
        os.environ['GLLM_MODE'] = 'OPEN_AI'

print("current GLLM MODE: {}".format(os.environ.get('GLLM_MODE')))

def setMode(mode):
    if mode not in ['AZURE','OPEN_AI']:
        raise Exception("invalid mode!")
    os.environ['GLLM_MODE'] = mode


async def ex_oai_call(messages=None, prompt=None, model=model,
                      temp: float = 0.5, tools=None, request_type='', run=None, mode=None, logging_mode=None, timeout=DEFAULT_TIMEOUT, print_log=True):
    '''Get the model response for the given chat conversation.'''
    log = Log(logging_mode=logging_mode, print_log=print_log, mode=mode)
    if not tools:
        tools =[]
    if not messages:
        messages = []
    if mode and mode == 'AZURE':
        return await ex_oai_azure_async(messages=messages, prompt=prompt, model=model, temperature=temp, tools=tools, request_type=request_type, run=run, logging_mode=logging_mode, timeout=timeout, print_log=print_log)
    elif os.environ.get('GLLM_MODE') == 'AZURE':
        return await ex_oai_azure_async(messages=messages, prompt=prompt, model=model, temperature=temp, tools=tools, request_type=request_type, run=run, logging_mode=logging_mode, timeout=timeout, print_log=print_log)

    OPEN_AI_KEY = get_api_key()
    async_client = AsyncOpenAI(
        timeout=timeout,
        max_retries=0,
        api_key=OPEN_AI_KEY
    )

    if prompt:
        messages = [{"role": "system", "content": prompt}] + messages
    if not messages[0]['content'].startswith(MAGIC_WORDS):
        messages[0]['content'] = MAGIC_WORDS + messages[0]['content'] 

    i = 0
    max_tries = 8
    while True:
        try:
            startTime = datetime.now()
            if tools:
                response = await async_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temp,
                    tools=tools
                )
            else:
                response = await async_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temp
                )
            elapsedTime = (datetime.now() - startTime).total_seconds()
            log.add_attempt(messages, response, elapsedTime, request_type=request_type, llm_method = 'ex_oai_call')

            if response.choices[0].finish_reason in ["stop", "tool_calls"]:
                break
            else:
                print(f"no exception, but also not done: {response}")
        except Exception as e:
            elapsedTime = (datetime.now() - startTime).total_seconds()
            log.add_attempt(messages, str(e), elapsedTime, request_type=request_type, llm_method = 'ex_oai_call')
            if i > max_tries:
                raise TimeoutError(
                    f"gave up on getting a response from gpt after {i} tries due to {e}") from e
            print(f"failed to get a response from openai due to {traceback.format_exception(e)}. Retry {i} of {max_tries}")
            if isinstance(e, APITimeoutError):
                async_client = AsyncOpenAI(
                    timeout=timeout,
                    max_retries=2,
                    api_key=OPEN_AI_KEY
                )
            time.sleep(1.8**i)
            i += 1
    
    result = response.model_dump(exclude_unset=True)
    await async_client.close()
    
    if log.logging_mode == 'save_to_csv':
        log.save_to_csv()
    
    return log, result

'''def streamResponse(messages: list = [], prompt = None, model = model, temp = 0.5):
    OPEN_AI_KEY = get_api_key()
    client = OpenAI(
        timeout=100,
        max_retries=0,
        api_key = OPEN_AI_KEY
    )
    if prompt:
        messages = [{"role":"system","content":prompt}] + messages
    

    #add the magic words
    if not messages[0]['content'].startswith(MAGIC_WORDS):
        messages[0]['content'] = MAGIC_WORDS + messages[0]['content'] 

    i = 0
    max_tries = 8
    while True:
        try:
            startTime = datetime.now()
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temp,
                stream=True
            )
            try:
                for chunk in response:
                    current_content = chunk.choices[0].delta.content
                    yield current_content
                break
            except Exception as e:
                print(f"exception occured during yield statement: {e}")
        except Exception as e:
            if i > max_tries:
                raise Exception(
                    f"gave up on getting a response from gpt after {i} tries due to {e}") from e
            print(
                f"failed to get a response from openai due to {e}. Retry {i} of {max_tries}")
        print("sleeping...")
        time.sleep(1.8**i)
        i += 1'''
    
async def json_response(messages =None, prompt=None, model=model, temp=temperature, tools=None, request_type='', run='', mode=None, logging_mode=None, timeout=DEFAULT_TIMEOUT, print_log=True):
    '''Send the conversation to OpenAI and parse the response as JSON.'''
    log = Log(logging_mode=logging_mode, print_log=print_log, mode=mode)
    if not tools:
        tools =[]
    if not messages:
        messages = []
    if mode and mode == 'AZURE':
        return await json_azure_async(messages=messages, prompt=prompt, model=model, temperature=temp, tools=tools, request_type=request_type, run=run, logging_mode=logging_mode, timeout=timeout, print_log=print_log, mode=mode)
    elif os.environ.get('GLLM_MODE') == 'AZURE':
        return await json_azure_async(messages=messages, prompt=prompt, model=model, temperature=temp, tools=tools, request_type=request_type, run=run, logging_mode=logging_mode, timeout=timeout, print_log=print_log, mode=mode)

    OPEN_AI_KEY = get_api_key()
    async_client = AsyncOpenAI(
        timeout=timeout,
        max_retries=0,
        api_key=OPEN_AI_KEY
    )

    if prompt:
        messages = [{"role": "system", "content": prompt}] + messages
    if not messages[0]['content'].startswith(MAGIC_WORDS):
        messages[0]['content'] = MAGIC_WORDS + messages[0]['content'] 

    max_tries = 2
    tries = 0
    while tries < max_tries:
        try:
            startTime = datetime.now()
            result = await async_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temp,
                response_format={'type': 'json_object'}
            )
            elapsedTime = (datetime.now() - startTime).total_seconds()
            log.add_attempt(messages, result, elapsedTime, request_type=request_type, llm_method = 'json_response')

            out = json.loads(json.loads(result.model_dump_json())['choices'][0]['message']['content'])
            await async_client.close()
            return log, out
        except Exception as e:
            elapsedTime = (datetime.now() - startTime).total_seconds()
            log.add_attempt(messages, str(e), elapsedTime, request_type=request_type, llm_method = 'json_response')
            print(f"json_response failed due to {e}")
            if isinstance(e, APITimeoutError):
                async_client = AsyncOpenAI(
                    timeout=timeout,
                    max_retries=2,
                    api_key=OPEN_AI_KEY
                )
            tries += 1

    if log.logging_mode == 'save_to_csv':
        log.save_to_csv()

    raise Exception('Unable to get good response')

def ex_oai_call_sync(messages=None, prompt=None, model=model,
                      temp: float = 0.5, tools=None, request_type='', run=None, mode=None, logging_mode=None, timeout=DEFAULT_TIMEOUT, print_log=True) -> str:
    '''Get the model response for the given chat conversation.'''
    log = Log(logging_mode=logging_mode, print_log=print_log, mode=mode)
    if not tools:
        tools =[]
    if not messages:
        messages = []
    if mode and mode == 'AZURE':
        return ex_oai_azure_sync(messages=messages, prompt=prompt, model=model, temperature=temp, tools=tools, request_type=request_type, run=run, logging_mode=logging_mode, timeout=timeout, print_log=print_log)
    elif os.environ.get('GLLM_MODE') == 'AZURE':
        return ex_oai_azure_sync(messages=messages, prompt=prompt, model=model, temperature=temp, tools=tools, request_type=request_type, run=run, logging_mode=logging_mode, timeout=timeout, print_log=print_log)

    OPEN_AI_KEY = get_api_key()
    client = OpenAI(
        timeout=timeout,
        max_retries=0,
        api_key=OPEN_AI_KEY
    )

    if prompt:
        messages = [{"role": "system", "content": prompt}] + messages
    messages[0]['content'] = MAGIC_WORDS + messages[0]['content']

    i = 0
    max_tries = 8
    while True:
        try:
            startTime = datetime.now()
            if tools:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temp,
                    tools=tools
                )
            else:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temp
                )
            elapsedTime = (datetime.now() - startTime).total_seconds()
            log.add_attempt(messages, response, elapsedTime, request_type=request_type, llm_method = 'ex_oai_call_sync')

            if response.choices[0].finish_reason in ["stop", "tool_calls"]:
                break
            else:
                print(f"no exception, but also not done: {response}")
        except Exception as e:
            elapsedTime = (datetime.now() - startTime).total_seconds()
            log.add_attempt(messages, str(e), elapsedTime, request_type=request_type, llm_method = 'ex_oai_call_sync')
            if i > max_tries:
                raise Exception(f"gave up on getting a response from gpt after {i} tries due to {e}") from e
            print(f"failed to get a response from openai due to {traceback.format_exception(e)}. Retry {i} of {max_tries}")
            if isinstance(e, APITimeoutError):
                async_client = OpenAI(
                    timeout=timeout,
                    max_retries=2,
                    api_key=OPEN_AI_KEY
                )
            time.sleep(1.8**i)
            i += 1
    
    result = response.model_dump(exclude_unset=True)
    client.close()
    
    if log.logging_mode == 'save_to_csv':
        log.save_to_csv()
    
    return log, result

#TODO: can we absract this so that we send a list of the things we want the LLM to send back? Can we have that be dynamically hard-typed and verified?
def json_response_sync(messages =None, prompt=None, model=model, temp=temperature, tools=None, request_type='', run='', mode=None, logging_mode=None, timeout=DEFAULT_TIMEOUT, print_log=True):
    '''Send the conversation to OpenAI and parse the response as JSON.'''
    log = Log(logging_mode=logging_mode, print_log=print_log, mode=mode)
    if not tools:
        tools =[]
    if not messages:
        messages = []
    if mode and mode == 'AZURE':
        return json_azure_sync(messages=messages, prompt=prompt, model=model, temperature=temp, tools=tools, request_type=request_type, run=run, logging_mode=logging_mode, timeout=timeout)
    elif not mode and os.environ.get('GLLM_MODE') == 'AZURE':
        return json_azure_sync(messages=messages, prompt=prompt, model=model, temperature=temp, tools=tools, request_type=request_type, run=run, logging_mode=logging_mode, timeout=timeout)

    OPEN_AI_KEY = get_api_key()
    client = OpenAI(
        timeout=timeout,
        max_retries=0,
        api_key=OPEN_AI_KEY
    )

    if prompt:
        messages = [{"role": "system", "content": prompt}] + messages
    messages[0]['content'] = MAGIC_WORDS + messages[0]['content']

    max_tries = 2
    tries = 0
    while tries < max_tries:
        try:
            startTime = datetime.now()
            result = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temp,
                response_format={'type': 'json_object'}
            )
            elapsedTime = (datetime.now() - startTime).total_seconds()
            log.add_attempt(messages, result, elapsedTime, request_type=request_type, llm_method = 'json_response_sync')

            out = json.loads(json.loads(result.model_dump_json())['choices'][0]['message']['content'])
            client.close()
            return log, out
        except Exception as e:
            elapsedTime = (datetime.now() - startTime).total_seconds()
            log.add_attempt(messages, str(e), elapsedTime, request_type=request_type, llm_method = 'json_response_sync')
            print(f"json_response failed due to {e}")
            if isinstance(e, APITimeoutError):
                client = OpenAI(
                    timeout=timeout,
                    max_retries=2,
                    api_key=OPEN_AI_KEY
                )
            tries += 1

    if log.logging_mode == 'save_to_csv':
        log.save_to_csv()

    raise Exception('Unable to get good response')

def getEmbedding(text):
    text = str(text)
    OPEN_AI_KEY = get_api_key()
    client = OpenAI(
        timeout=20,
        max_retries=2,
        api_key = OPEN_AI_KEY
    )
    response = client.embeddings.create(
    input=text,
    model=os.environ.get('OPENAI_EMBEDDING_MODEL', None) if os.environ.get('OPENAI_EMBEDDING_MODEL', None) else "text-embedding-ada-002"
    )
    return response.data[0].embedding


def getEmbeddingsSyncFromList(text_list, max_workers = 100):
    text_list = [str(text) for text in text_list]
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        embeddings = list(executor.map(getEmbedding, text_list))
    return embeddings


def cleanStringForLLM(inp):
    output = str(inp)
    while '\\\\' in output:
        output = output.replace('\\\\','\\')
    while '  ' in output:
        output = output.replace('  ',' ')
    return output

def compare(emb1, emb2):
    '''
    compare two embeddings. Return a value in . Uses cosine similarity.
    '''
    return np.dot(emb1, emb2)/(np.linalg.norm(emb1)*np.linalg.norm(emb2))

def find_top_k_pairs(embeddings, k, descending=True):
    '''
    returns the top_k most similar vector pairs. Computationally fine for small len(list), but O(n^2) so be careful. Worth implementing ANN at some point?    
    From initial testing, less than 3k should be fine. We approach a second at 5k, but consider FOS and memory concerns.
    result is sorted descending.
    '''
    n = len(embeddings)
    k = min(k, n*(n-1)//2)
    if len(embeddings) < 2:
        return None
    # Step 1: Calculate pairwise cosine similarity matrix
    # Normalize embeddings to have unit norm
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    
    # Compute the cosine similarity (as dot product of normalized vectors)
    similarity_matrix = np.dot(embeddings, embeddings.T)
    
    # Step 2: Extract the upper triangle of the similarity matrix, excluding the diagonal
    i_upper = np.triu_indices_from(similarity_matrix, k=1)
    similarities = similarity_matrix[i_upper]
    
    # Step 3: Get the indices of the top-k most similar pairs
    top_k_indices = np.argpartition(similarities, -k)[-k:]
    top_k_similarities = similarities[top_k_indices]
    
    # Step 4: Convert flat indices to pair indices
    top_k_pairs = [(i_upper[0][idx], i_upper[1][idx]) for idx in top_k_indices]

    pairs_with_scores = [(pair[0], pair[1], top_k_similarities[i]) for i, pair in enumerate(top_k_pairs)]

    # Sort the results by similarity score in descending order (by default)
    top_k_sorted = sorted(pairs_with_scores, key=lambda x: x[2], reverse=descending)
    
    # Step 5: Return pairs with their corresponding similarity scores
    return top_k_sorted


def getShorthandSummary(text, model=model):
    prompt = f'Shorten the following text, if possible. If you cannot shorten the text, simply return the text. Include all important information, but use shorthand and incomplete sentences to reduce the size of the text. Do not add any new information. \ntext:{text}'
    result = ex_oai_call_sync(prompt=prompt, model=model)
    return result

async def getSnippet(text, model=model):
    prompt = f'In 3 words or less, describe what is in the following text:{str(text)}'
    result = await ex_oai_call(prompt=prompt, model=model)
    return result

def log(messages,response,elapsedTime, request_type=None, run='', logging_mode=None, mode=os.environ['GLLM_MODE']):
    global sessionId
    if mode=='AZURE':
        try:
            try:
                response = json.loads(response.text())
            except:
                try:
                    response = json.loads(response)
                except:
                    pass
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            request_tokens = response['usage']['prompt_tokens']
            response_tokens = response['usage']['completion_tokens']
            total_tokens = response['usage']['total_tokens']
            request_content = messages
            response_content = response
            model = response['model']
            promptCost,completionCost = getCosts(model)
            cost = (request_tokens*promptCost + response_tokens*completionCost)/1000

            if GLLM_LOGGING_PATH=='AZURE':
                import logging
                logger = logging.getLogger('azure')
                logger.setLevel(logging.WARNING)
                from azure.storage.blob import BlobServiceClient, BlobClient
                from io import StringIO
                try:
                    GLOBAL_CID = os.environ.get('GLOBAL_CID', '')
                    if GLOBAL_CID:
                        sessionId = GLOBAL_CID
                except Exception as e:
                    print(f"unable to find global CID")
                    sessionId = 'other'
                
                csv_file_name = f"{sessionId}.csv" if not run else f"{run}/{sessionId}.csv"
                
                fieldnames = ['Time', 'Request Tokens Used', 'Response Tokens Used', 'Total Tokens Used', 'Request Content', 'Response Content', 'Cost', 'Elapsed Time', 'Model', 'Request Type']

                connection_string = os.environ['AZURE_CONNECTION_STRING']
                container_name = "logs"
                blob_service_client = BlobServiceClient.from_connection_string(connection_string)
                blob_client = blob_service_client.get_blob_client(container=container_name, blob=csv_file_name)

                # Check if the Blob already exists and download its content
                csv_output = StringIO()
                try:
                    downloaded_blob = blob_client.download_blob()
                    csv_output.write(downloaded_blob.content_as_text())
                except Exception:
                    # If Blob does not exist, write the header
                    if request_type:
                        fieldnames.append('Request Type')
                    writer = csv.DictWriter(csv_output, fieldnames=fieldnames)
                    writer.writeheader()

                # Append new data to CSV
                writer = csv.DictWriter(csv_output, fieldnames=fieldnames)

                new_row = {
                    'Time': current_time,
                    'Request Tokens Used': request_tokens,
                    'Response Tokens Used': response_tokens,
                    'Total Tokens Used': total_tokens,
                    'Request Content': request_content,
                    'Response Content': response_content,
                    'Cost': cost,
                    'Elapsed Time': elapsedTime,
                    'Model': model
                }

                if request_type:
                    new_row.update({'Request Type': request_type})

                writer.writerow(new_row)

                # Upload updated CSV data to Azure Blob Storage
                csv_output.seek(0)  # Reset buffer position to the beginning
                blob_client.upload_blob(csv_output.read(), blob_type="BlockBlob", overwrite=True)
                return


            if run:
                csv_file_name = f"{run}/{sessionId}.csv"
            else:
                csv_file_name = f"{sessionId}.csv"

            csv_file_path = os.path.join(GLLM_LOGGING_PATH, csv_file_name)
            # Define the fieldnames for the CSV
            fieldnames = ['Time', 'Request Tokens Used', 'Response Tokens Used', 'Total Tokens Used', 'Request Content', 'Response Content', 'Cost','Elapsed Time','Model','Request Type']

            if request_type:
                fieldnames.append('Request Type')
            # Check if the CSV file exists, and create it if it doesn't
            if not os.path.isfile(csv_file_path):
                with open(csv_file_path, 'w', newline='') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()

            # Open the CSV file and append a new row
            with open(csv_file_path, 'a', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Create a new row with the specified data
                new_row = {
                    'Time': current_time,
                    'Request Tokens Used': request_tokens,
                    'Response Tokens Used': response_tokens,
                    'Total Tokens Used': total_tokens,
                    'Request Content': request_content,
                    'Response Content': response_content,
                    'Cost': cost,
                    'Elapsed Time':elapsedTime,
                    'Model':model
                }
                if request_type:
                    new_row.update({'Request Type': request_type})
            
                # Write the new row to the CSV file
                writer.writerow(new_row)
        except Exception as e:
            print(f"unable to log request to LLM because of {traceback.format_exception(e)}. messages: {messages}\n\n response: {response}\n\n")
    else:
        try:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            request_tokens = response.usage.prompt_tokens
            response_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens
            request_content = messages
            response_content = response.choices[0]
            model = response.model
            promptCost,completionCost = getCosts(model)
            cost = (request_tokens*promptCost + response_tokens*completionCost)/1000
            if GLLM_LOGGING_PATH=='AZURE':
                import logging
                logger = logging.getLogger('azure')
                logger.setLevel(logging.WARNING)
                from azure.storage.blob import BlobServiceClient, BlobClient
                from io import StringIO
                try:
                    GLOBAL_CID = os.environ.get('GLOBAL_CID', '')
                    if GLOBAL_CID:
                        sessionId = GLOBAL_CID
                except Exception as e:
                    print(f"unable to find global CID")
                    sessionId = 'other'
                
                csv_file_name = f"{sessionId}.csv" if not run else f"{run}/{sessionId}.csv"
                
                fieldnames = ['Time', 'Request Tokens Used', 'Response Tokens Used', 'Total Tokens Used', 'Request Content', 'Response Content', 'Cost', 'Elapsed Time', 'Model', 'Request Type']

                connection_string = os.environ['AZURE_CONNECTION_STRING']
                container_name = "logs"
                blob_service_client = BlobServiceClient.from_connection_string(connection_string)
                blob_client = blob_service_client.get_blob_client(container=container_name, blob=csv_file_name)

                # Check if the Blob already exists and download its content
                csv_output = StringIO()
                try:
                    downloaded_blob = blob_client.download_blob()
                    csv_output.write(downloaded_blob.content_as_text())
                except Exception:
                    # If Blob does not exist, write the header
                    if request_type:
                        fieldnames.append('Request Type')
                    writer = csv.DictWriter(csv_output, fieldnames=fieldnames)
                    writer.writeheader()

                # Append new data to CSV
                writer = csv.DictWriter(csv_output, fieldnames=fieldnames)

                new_row = {
                    'Time': current_time,
                    'Request Tokens Used': request_tokens,
                    'Response Tokens Used': response_tokens,
                    'Total Tokens Used': total_tokens,
                    'Request Content': request_content,
                    'Response Content': response_content,
                    'Cost': cost,
                    'Elapsed Time': elapsedTime,
                    'Model': model
                }

                if request_type:
                    new_row.update({'Request Type': request_type})

                writer.writerow(new_row)

                # Upload updated CSV data to Azure Blob Storage
                csv_output.seek(0)  # Reset buffer position to the beginning
                blob_client.upload_blob(csv_output.read(), blob_type="BlockBlob", overwrite=True)
                return

            csv_file_name = f"{sessionId}.csv"
            csv_file_path = os.path.join(GLLM_LOGGING_PATH, csv_file_name)
            # Define the fieldnames for the CSV
            fieldnames = ['Time', 'Request Tokens Used', 'Response Tokens Used', 'Total Tokens Used', 'Request Content', 'Response Content', 'Cost','Elapsed Time','Model','Request Type']

            # Check if the CSV file exists, and create it if it doesn't
            if not os.path.isfile(csv_file_path):
                with open(csv_file_path, 'w', newline='') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()

            # Open the CSV file and append a new row
            with open(csv_file_path, 'a', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Create a new row with the specified data
                new_row = {
                    'Time': current_time,
                    'Request Tokens Used': request_tokens,
                    'Response Tokens Used': response_tokens,
                    'Total Tokens Used': total_tokens,
                    'Request Content': request_content,
                    'Response Content': response_content,
                    'Cost': cost,
                    'Elapsed Time':elapsedTime,
                    'Model':model
                }
                if request_type:
                    new_row.update({'Request Type': request_type})
            
                # Write the new row to the CSV file
                writer.writerow(new_row)
        except Exception as e:
            print(f"unable to log request to LLM because of {e}")

def getCosts(model = model):
    '''
    returns (prompt, completion) in dollars per thousand tokens.
    '''
    if model in ["gpt-4-1106-preview", 'gpt-4-turbo-preview']:
        return (0.01,0.03)
    if "gpt-4o" in model:
        return (0.005,0.015)
    if model in ["gpt-4","gpt-4-0613"]:
        return (0.03,0.06)
    if model == "gpt-4-32k":
        return (0.06,0.12)
    if model in ["gpt-3.5-turbo","gpt-3.5-turbo-1106"]:
        return (0.001,0.002)
    print(f"unknown model: {model}. Returning 0 for cost.")
    return (0,0)




    
    

def asDict(gptmessage):
    message = {
        'role': gptmessage.role,
        'content': gptmessage.content,
    }
    if gptmessage.tool_calls:
        message['tool_calls']=gptmessage.tool_calls
    return message


#azure version
MODEL_TO_DEPLOYMENT = {
    'gpt-4-32k': 'Cade-GPT4-32',
    'gpt-4': 'Cade-GPT-4',
    'gpt-4-turbo-preview':'gpt-4-turbo-2024-04-09',
    'gpt-4-1106-preview':'CadenzaaGPT4Preview',
    'gpt-3.5-turbo':'gpt-35-turbo',
    'gpt-4-turbo':'gpt-4-turbo-2024-04-09',
    'gpt-4o':'gpt-4o'
}

async def ex_oai_azure_async(messages=None, prompt=None, temperature=0.5, model=AZURE_COMPLETION_MODEL, tools=None, request_type='', run='', logging_mode=None, timeout=DEFAULT_TIMEOUT, print_log=True):
    if not tools:
        tools =[]
    if not messages:
        messages = []
    log = Log(logging_mode=logging_mode, print_log=print_log, mode='AZURE')
    if prompt:
        messages = [{"role": "system", "content": prompt}] + messages
    messages[0]['content'] = MAGIC_WORDS + messages[0]['content']
    
    try:
        deployment_name = MODEL_TO_DEPLOYMENT[model]
    except KeyError:
        raise KeyError(f"Model {model} not found")

    url = f"https://{AZURE_RESOURCE_NAME}.openai.azure.com/openai/deployments/{deployment_name}/chat/completions?api-version=2023-12-01-preview"
    print(url)
    headers = {
        'Content-Type': 'application/json',
        'api-key': AZURE_API_KEY
    }

    payload = {
        'messages': messages,
        'temperature': temperature
    }

    if tools:
        payload['tools'] = tools

    i = 0
    max_tries = 8

    while True:
        try:
            startTime = datetime.now()
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=timeout) as response:
                    response_text = await response.text()
                    elapsedTime = (datetime.now() - startTime).total_seconds()
                    log.add_attempt(messages, response_text, elapsedTime, request_type=request_type, llm_method = 'ex_oai_azure_async')
                    if response.status == 200:
                        loaded = json.loads(response_text)
                        if loaded.get('error'):
                            raise Exception(f"openai returned this error (AZURE): {loaded}")
                        if log.logging_mode == 'save_to_csv':
                            log.save_to_csv()
                        return log, json.loads(response_text)
        except Exception as e:
            elapsedTime = (datetime.now() - startTime).total_seconds()
            log.add_attempt(messages, str(e), elapsedTime, request_type=request_type, llm_method = 'ex_oai_azure_async')
            if i > max_tries:
                raise TimeoutError(
                    f"gave up on getting a response from gpt after {i} tries due to {e}") from e
            print(f"failed to get a response from openai due to {e}. Retry {i} of {max_tries}")

        await asyncio.sleep(1.8**i)
        i += 1



def ex_oai_azure_sync(messages=None, prompt=None, temperature=0.5, model=AZURE_COMPLETION_MODEL, tools=None, request_type='', run='', logging_mode=None, timeout=DEFAULT_TIMEOUT, print_log=True):
    if not tools:
            tools =[]
    if not messages:
        messages = []
    log = Log(logging_mode=logging_mode, print_log=print_log, mode='AZURE')
    if prompt:
        messages = [{"role": "system", "content": prompt}] + messages
    messages[0]['content'] = MAGIC_WORDS + messages[0]['content']
    
    try:
        deployment_name = MODEL_TO_DEPLOYMENT[model]
    except KeyError:
        raise KeyError(f"Model {model} not found")

    url = f"https://{AZURE_RESOURCE_NAME}.openai.azure.com/openai/deployments/{deployment_name}/chat/completions?api-version=2023-12-01-preview"
    print('url:', url)
    headers = {
        'Content-Type': 'application/json',
        'api-key': AZURE_API_KEY
    }

    payload = {
        'messages': messages,
        'temperature': temperature
    }

    if tools:
        payload['tools'] = tools

    i = 0
    max_tries = 8

    while True:
        try:
            startTime = datetime.now()
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            response_text = response.content
            elapsedTime = (datetime.now() - startTime).total_seconds()
            log.add_attempt(messages, response_text, elapsedTime, request_type=request_type, llm_method = 'ex_oai_azure_sync')
            if response.status_code == 200:
                loaded = json.loads(response_text)
                if loaded.get('error'):
                    raise Exception(f"openai returned this error (AZURE): {loaded}")
                if log.logging_mode == 'save_to_csv':
                    log.save_to_csv()
                return log, json.loads(response_text)
        except Exception as e:
            elapsedTime = (datetime.now() - startTime).total_seconds()
            log.add_attempt(messages, str(e), elapsedTime, request_type=request_type, llm_method = 'ex_oai_azure_sync')
            if i > max_tries:
                raise Exception(f"gave up on getting a response from gpt after {i} tries due to {e}") from e
            print(f"failed to get a response from openai due to {e}. Retry {i} of {max_tries}")
        if i == 0:
            #change to 4o 
            deployment_name = MODEL_TO_DEPLOYMENT['gpt-4o']
            url = f"https://{AZURE_RESOURCE_NAME}.openai.azure.com/openai/deployments/{deployment_name}/chat/completions?api-version=2023-12-01-preview"
        if i == 1:
            #change back to original
            deployment_name = MODEL_TO_DEPLOYMENT[model]
            url = f"https://{AZURE_RESOURCE_NAME}.openai.azure.com/openai/deployments/{deployment_name}/chat/completions?api-version=2023-12-01-preview"
        time.sleep(1.8**i)
        i += 1

def json_azure_sync(messages =None, prompt=None, model=model, temperature=temperature, tools=None, request_type='', run='', mode=None, logging_mode=None, timeout=DEFAULT_TIMEOUT, print_log=True):
    '''Send the conversation to OpenAI and parse the response as JSON.'''
    log = Log(logging_mode=logging_mode, print_log=print_log, mode=mode)
    if not tools:
        tools =[]
    if not messages:
        messages = []
    if not tools:
        tools =[]
    if not messages:
        messages = []
    
    if prompt:
        messages = [{"role": "system", "content": prompt}] + messages
    messages[0]['content'] = MAGIC_WORDS + messages[0]['content']

    
    try:
        deployment_name = MODEL_TO_DEPLOYMENT[model]
    except KeyError:
        raise KeyError(f"Model {model} not found")

    url = f"https://{AZURE_RESOURCE_NAME}.openai.azure.com/openai/deployments/{deployment_name}/chat/completions?api-version=2023-12-01-preview"


    headers = {
        'Content-Type': 'application/json',
        'api-key': AZURE_API_KEY
    }

    payload = {
        'messages': messages,
        'temperature': temperature,
        'response_format': {"type": "json_object"}
    }

    if tools:
        payload['tools'] = tools

    i = 0
    max_tries = 8

    while True:
        try:
            startTime = datetime.now()
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            response_text = response.content.decode('utf-8')
            elapsedTime = (datetime.now() - startTime).total_seconds()
            log.add_attempt(messages, response_text, elapsedTime, request_type=request_type, llm_method = 'json_azure_sync')
            if response.status_code == 200:
                loaded = json.loads(response_text)
                if loaded.get('error'):
                    raise Exception(f"openai returned this error (AZURE): {loaded}")
                if log.logging_mode == 'save_to_csv':
                    log.save_to_csv()
                return log, json.loads(loaded['choices'][0]['message']['content'])
        except Exception as e:
            elapsedTime = (datetime.now() - startTime).total_seconds()
            log.add_attempt(messages, str(e), elapsedTime, request_type=request_type, llm_method = 'json_azure_sync')
            if i > max_tries:
                raise Exception(f"gave up on getting a response from gpt after {i} tries due to {e}") from e
            print(f"failed to get a response from openai due to {traceback.format_exception(e)}. Retry {i} of {max_tries}")

        time.sleep(1.8**i)
        i += 1

async def json_azure_async(messages=None, prompt=None, temperature=0.5, model=AZURE_COMPLETION_MODEL, tools=None, request_type='',run='', logging_mode=None, timeout = DEFAULT_TIMEOUT, print_log = None, mode=None):
    log = Log(logging_mode=logging_mode, print_log=print_log, mode=mode)

    if not tools:
        tools =[]
    if not messages:
        messages = []
    
    if prompt:
        messages = [{"role": "system", "content": prompt}] + messages
    
    try:
        deployment_name = MODEL_TO_DEPLOYMENT[model]
    except KeyError:
        raise KeyError(f"Model {model} not found")

    url = f"https://{AZURE_RESOURCE_NAME}.openai.azure.com/openai/deployments/{deployment_name}/chat/completions?api-version=2023-12-01-preview"

    #add the magic words
    if not messages[0]['content'].startswith(MAGIC_WORDS):
        messages[0]['content'] = MAGIC_WORDS + messages[0]['content'] 

    headers = {
        'Content-Type': 'application/json',
        'api-key': AZURE_API_KEY
    }

    payload = {
        'messages': messages,
        'temperature': temperature,
        'response_format': {"type": "json_object"}
    }

    if tools:
        payload['tools'] = tools

    i = 0
    max_tries = 8

    while True:
        try:
            startTime = datetime.now()
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=timeout) as response:
                    response_json = await response.json()
                    if response.status == 200:

                        elapsedTime = (datetime.now() - startTime).total_seconds()
                        log.add_attempt(messages, response_json, elapsedTime, request_type=request_type, llm_method = 'json_azure_async')
                        
                        return log, json.loads(response_json['choices'][0]['message']['content'])

                    try:
                        if GLLM_LOGGING_PATH:
                            log(messages, response_json, (datetime.now() - startTime).total_seconds(),request_type=request_type,run=run, logging_mode=logging_mode,mode='AZURE')
                    except Exception as e:
                        print(f"failed to log result of failed openai call due to: {e}: {response_json}")
        except Exception as e:
            if i > max_tries:
                raise TimeoutError(
                    f"gave up on getting a response from gpt after {i} tries due to {e}") from e
            print(
                f"failed to get a response from openai due to {traceback.format_exception(e)}. Retry {i} of {max_tries}")

        await asyncio.sleep(1.8**i)
        i += 1