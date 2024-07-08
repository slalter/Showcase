from google.cloud import storage
import json
import re
from datetime import datetime, timezone, timedelta

client = storage.Client()
bucket = client.get_bucket('aiqa_storage')

def upload_blob_from_string(data: str, destination_blob_name: str) -> None:
    """
    Uploads data as a blob to the bucket
    """
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_string(data)
    print(f"Data uploaded to {destination_blob_name}.")

def download_blob_to_string(source_blob_name: str):
    """
    Downloads a blob from the bucket and returns it as a string
    """
    blob = bucket.blob(source_blob_name)
    try:
        return blob.download_as_text()
    except Exception as e:
        print(f"Error downloading blob {source_blob_name}: {e}")
        return None
    
def upload_blob_from_bytes(data: bytes, destination_blob_name: str) -> None:
    """
    Uploads binary data as a blob to the bucket.
    """
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_string(data)
    print(f"Data uploaded to {destination_blob_name}.")
    
def delete_blobs_with_prefix(prefix: str) -> None:
    """
    Deletes all blobs from the bucket that start with the given prefix.
    """
    blobs = bucket.list_blobs(prefix=prefix)
    for blob in blobs:
        try:
            blob.delete()
            print(f"Blob {blob.name} deleted.")
        except Exception as e:
            print(f"Error deleting blob {blob.name}: {e}")

def getTranscriptFromBucket(key):
    '''
    redacts all numbers. Also removes them from the transcript in the bucket.
    '''
    content = download_blob_to_string(key.replace('aiqa_storage/',''))
    if content:
        if 'cleaned' in key:
            return content
        content = json.loads(content)
        for result in content['results']:
            if not isinstance(result, dict):
                continue
            for alternative in result.get('alternatives', []):
                alternative['transcript'] = re.sub(r'\d', '#', alternative['transcript'])
        content = json.dumps(content)
        upload_blob_from_string(content,key.replace('aiqa_storage/','').replace('.json','cleaned.json'))
        return content
    else:
        raise Exception("no content in transcript.")

def list_blobs(prefix=None):
    """
    Lists all the blobs in the bucket that start with the prefix.
    
    :param prefix: Prefix to filter the blobs. If None, lists all blobs.
    :return: List of blob names
    """
    blobs = bucket.list_blobs(prefix=prefix)  # Fetch blobs with the given prefix
    blob_names = []
    for blob in blobs:
        blob_names.append(blob.name)
    return blob_names

def delete_blob(blob):
    blob = bucket.blob(blob)
    blob.delete()

def delete_old_blobs(prefix, days_old) -> None:
    """
    Deletes blobs from the bucket that are older than a specified number of days.

    :param days_old: The age of the blob in days to qualify for deletion.
    """

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
    blobs = bucket.list_blobs(prefix=prefix)  # List all blobs in the bucket
    for blob in blobs:
        if blob.time_created < cutoff_date:
            try:
                blob.delete()
                print(f"Deleted blob {blob.name} created on {blob.time_created}")
            except Exception as e:
                print(f"Error deleting blob {blob.name}: {e}")

