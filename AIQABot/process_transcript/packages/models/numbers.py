from dataclasses import dataclass, asdict, field, fields
from packages.cloudstorage import upload_blob_from_string, download_blob_to_string, upload_blob_from_bytes, delete_blobs_with_prefix
from packages.retreaver import getAllNumbers
from typing import List, Optional, Tuple
import json
import uuid 

def getNumberName(did):
    print(f"getting numbername for did {did}")
    did_name_pairs = {}
    result = download_blob_to_string('numberNames.json')
    if result:
        did_name_pairs = json.loads(result)
    else:
        updateNumberNames()
        result = download_blob_to_string('numberNames.json')
        if result:
            did_name_pairs = json.loads(result)
        else:
            raise Exception("Unable to get the DID/number pairs!")
    output = did_name_pairs.get(did, None)
    if not output:
        if '+' in did:
            did = did.replace('+','')
        output = did_name_pairs.get(did, None)
        if not output:
            updateNumberNames(did_name_pairs.get('num_refreshes',0))
            output = did_name_pairs.get(did, None)
            if not output:
                print(f"WARNING: no numbername! numrefreshes: {did_name_pairs.get('num_refreshes',0)}")
    return output


def updateNumberNames(num_refreshes = 0):
    print("updating numbernames storage...")
    numbers = getAllNumbers()
    did_name_pairs = {number['number']['number']:number['number']['name'] for number in numbers}
    if num_refreshes:
        did_name_pairs['num_refreshes'] = num_refreshes
    upload_blob_from_string(json.dumps(did_name_pairs),'numberNames.json')