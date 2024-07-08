from guru.GLLM import LLM
import numpy as np
import json
import requests
import os

def getSet(set_name, embedded=False):
    print(f'Getting set {set_name}. embedded: {embedded}')
    if embedded:
        with open(f'data_sets/embedded/{set_name}.txt') as f:
            values = json.loads(f.read())
            for value in values:
                value[1] = np.array(value[1])
            return values
    else:
        with open(f'data_sets/notembedded/{set_name}.txt') as f:
            values =  eval(f.read())
            return values

    
def addSet(set_name, set):
    print(f'Adding set {set_name}')
    with open(f'data_sets/notembedded/{set_name}.txt', 'w') as f:
        f.write(str(set))
    embeddings = LLM.getEmbeddingsSyncFromList(set)
    values = []
    for noun, embedding in zip(set, embeddings):
        values.append([noun, embedding])
    string = json.dumps(values)
    with open(f'data_sets/embedded/{set_name}.txt', 'w') as f:
        f.write(string)
    return values

def combineSets(set1, set2):
    print(f'Combining sets {set1} and {set2}')
    set1 = getSet(set1)
    set2 = getSet(set2)
    combined = set1 + set2
    addSet(set1 + set2, combined)
    return combined

def makeSuperSet():
    '''
    combines all sets in the dir
    '''
    print('Making super set')
    sets = os.listdir('data_sets/notembedded')
    super_set = []
    for set in sets:
        set = set.split('.')[0]
        super_set += getSet(set, embedded=True)
    return super_set

from concurrent.futures import ThreadPoolExecutor

def getNewSet(size, embedded=False):
    url = 'https://random-word-api.herokuapp.com/word'
    new_set = []
    def getWord():
        response = requests.get(url)
        word = response.json()[0]
        return word
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(getWord) for _ in range(size)]
        for future in futures:
            new_set.append(future.result())


    #save the set to a file
    print(f'Adding set')
    #random name based on some of the words and the size
    name = new_set[0] + str(size)
    if embedded:
        return addSet(name, new_set)
    addSet(name, new_set)
    return new_set