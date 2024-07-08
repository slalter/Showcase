
import json
import os
from googleapiclient.discovery import build
from google.oauth2 import service_account
from flask import make_response
from models import Product
import traceback
if os.environ.get('ENVIRONMENT','').lower()=='local' or os.environ.get('TESTING', 'false').lower() == 'true':
    projPath = os.environ.get('DRIVE_PROJECT_PATH_TESTING')
    propPath = os.environ.get('DRIVE_PROPOSAL_PATH_TESTING')
else:
    projPath = os.environ.get('DRIVE_PROJECT_PATH')
    propPath = os.environ.get('DRIVE_PROPOSAL_PATH')

credentials = service_account.Credentials.from_service_account_info(
        json.loads(os.environ.get('DRIVE_APPLICATION_CREDENTIALS') or "{}"),
        scopes=['https://www.googleapis.com/auth/drive','https://www.googleapis.com/auth/drive.file']
    )
drive_service = build('drive', 'v3', credentials=credentials)
    

def make_project_folder(project_num, prod_type, address, db):
    products = db.session.query(Product).order_by(Product.name.asc()).all()    
    # List folders in the specified directory
    proj_list = []
    pageToken = None
    while True:
        query=f"'{projPath}' in parents and trashed=false"
        response = drive_service.files().list(
            q=query,
            fields="nextPageToken, files(id, name, createdTime)",
            pageToken=pageToken,
            pageSize = 20,
            includeItemsFromAllDrives = True,
            supportsAllDrives = True
        ).execute()
        proj_list.append(response["files"])
        pageToken = response.get('nextPageToken')
        if not pageToken:
            break
    print(proj_list)
    projNums = []
    for projectL in proj_list:
        for project in projectL:
            projNums.append(project["name"].split(" - ")[0])
    
    if project_num in projNums:
        #get the path to the folder
        for projectL in proj_list:
            for project in projectL:
                if project["name"].split(" - ")[0] == project_num:
                    raise AlreadyExistsException(f"https://drive.google.com/drive/folders/{project['id']}")

    
    #create main folder
    folder_metadata = {
        'name': f"{project_num} - {address.replace(', USA','')}",
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [projPath]
    }
    mainFolder = drive_service.files().create(body=folder_metadata, fields='id',supportsAllDrives=True).execute()
    id = mainFolder.get('id')

    #find current product in products.json
    currentProduct = None
    for product in products:
        if product.name == prod_type:
            currentProduct = product
    if currentProduct:
        print(currentProduct.name)
        for subfolder in currentProduct.folders:
            print(subfolder)
            folder_metadata = {
                'name': subfolder,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [id]
            }
            mainFolder = drive_service.files().create(body=folder_metadata, fields='id', supportsAllDrives=True).execute()

    else:
        raise Exception(f"Product {prod_type} not found in products.json")


    return f"https://drive.google.com/drive/folders/{id}"

def make_proposal_folder(proposal_num, address) -> str:
    '''
    The folder is named PXXXX - Address
    returns a url.
    '''

    #make sure that the proposal number is unique and conforms to the naming convention
    if not proposal_num.startswith("P") or not proposal_num[1:].isnumeric():
        raise Exception("Proposal number must start with P and be followed by numbers")

    # List folders in the specified directory
    print(f"Checking for {proposal_num}")
    prop_num_list = []
    pageToken = None
    while True:
        query=f"'{propPath}' in parents and trashed=false"
        response = drive_service.files().list(
            q=query,
            fields="nextPageToken, files(id, name, createdTime)",
            pageToken=pageToken,
            pageSize = 20,
            includeItemsFromAllDrives = True,
            supportsAllDrives = True
        ).execute()
        prop_num_list.append(response["files"])
        pageToken = response.get('nextPageToken')
        if not pageToken:
            break

    prompt_nums = [p[:5] for p in prop_num_list]
    if proposal_num in prompt_nums:
        raise Exception("Proposal number already exists")
    
    print("Creating folder")
    #create main folder
    folder_metadata = {
        'name': f"{proposal_num} - {address.replace(', USA','')}",
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [propPath]
    }

    mainFolder = drive_service.files().create(body=folder_metadata, fields='id',supportsAllDrives=True).execute()
    id = mainFolder.get('id')
    #make an upload-only folder
    upload_only_url = create_upload_only_folder("Client Uploads", id)
    print(f"Created folder with id {id}. urls: {upload_only_url}, https://drive.google.com/drive/folders/{id}")
    return f"https://drive.google.com/drive/folders/{id}", upload_only_url

def create_upload_only_folder(name, parent_id):
    '''
    Creates a folder that allows anyone with the link to upload files. Doesn't allow any other operations.
    '''
    folder_metadata = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    mainFolder = drive_service.files().create(body=folder_metadata, fields='id',supportsAllDrives=True).execute()
    id = mainFolder.get('id')
    permissions = {
        'type': 'anyone',
        'role': 'writer'
    }

    drive_service.permissions().create(
        fileId=id,
        body=permissions,
        fields='id'
    ).execute()
    return f"https://drive.google.com/drive/folders/{id}"

class AlreadyExistsException(Exception):
    def __init__(self, url):
        self.url = url