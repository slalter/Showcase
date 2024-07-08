from google.auth import default
from googleapiclient.discovery import build
from packages.retreaver import getCampaignById
from packages.models.numbers import getNumberName
from datetime import datetime, timedelta, timezone
from guru.GLLM.log import Log
import traceback
import time
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
sheetId = '1_ThRyw3OosCt_-2ZPFZCRJT-_iG7v6XgD6TMEd_lO68'

def logCallInSheets(call, call_logs=None):
    from packages.models.campaign import Category
    attempts = []
    cost = 0
    if call_logs:
        for log in call_logs:
            attempts += log.attempts
        if attempts:
            for attempt in attempts:
                cost += attempt.cost
    results = []
    #tags['affiliate_id']
    row = [
        'timestamp',
        'CID',
        'CampaignName',
        'PubID',
        'Number',
        'NumberName',
        'TotalDurationSecs',
        'IVRDurationSecs',
        'HoldDurationSecs',
        'ConnectedSecs',
        'ConnectedTo',
        'BillableMinutes',
        'Charged',
        'Caller',
        'CallUUID',
        'Vertical',
        'Auditor',
        'Billable?',
        'Notes',
        'Category',
        'Description',
        'Questions',
        'Summary'
    ]
    try:
        total_time = (datetime.strptime(call.end_time, '%Y-%m-%dT%H:%M:%S.%fZ') - datetime.strptime(call.start_time, '%Y-%m-%dT%H:%M:%S.%fZ')).total_seconds()
    except Exception as e:
        total_time = f"error: {e}"
    try:
        campaign = getCampaignById(call.cid)
        numberName = getNumberName(call.number)
        if not numberName:
            numberName = f"**{campaign['name']}"
            call.error_log.append(f"unable to find numbername!")
        results.append(prettify_date(call.created_at))
        results.append(call.cid)
        results.append(campaign['name']) 
        results.append(call.afid)
        results.append(call.number)
        results.append(numberName)
        results.append(total_time) 
        results.append(call.ivr_duration)
        results.append(call.hold_duration)
        results.append(total_time - call.ivr_duration - call.hold_duration)
        results.append(call.connected_to)
        results.append(call.billable_minutes)
        results.append(call.charge_total)
        results.append(call.caller)
        results.append(call.uuid)
        results.append(call.getCampaign().name)
        results.append(call.billable)
        results.append('')  
        if isinstance(call.category, Category):
            results.append(call.category.name)
        else:
            results.append(call.category)

        results.append(call.subcategory)
        results.append(call.summary)
        results.append(call.ai_status)
        results.append(str(call.flags) if call.flags else '')
        results.append(cost)
        for q in call.questions:
            results.append(f'q: {q[0]}\na: {q[1]}')
        if call.transcript:
            results.append(call.transcript)
    except Exception as e:
        call.error_log.append(f"an error occured while compiling data for sheets: {traceback.format_exception(e)}")
    if call.error_log:
        while len(results) < 24:
            results.append('error')
        results.append(f"errors: {call.error_log}")
    today = extract_date(call.created_at)
    append_row(sheetId,today,results)


def get_sheets_service():
    creds, _ = default(scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    return service.spreadsheets()


def append_row(spreadsheet_id, sheet_name, values):
    """
    Append a row to the next empty row at the bottom of the specified sheet in a Google Sheet.
    """
    tries = 0
    max_tries = 6
    while True:
        tries +=1
        try:
            print(f"Appending row: {values}")
            range_name = f'{sheet_name}'
            body = {'values': [values]}
            
            service = get_sheets_service()
            result = service.values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body).execute()
            
            return result
        except Exception as e:
            if tries <= max_tries:
                print(f"exception appending row: {e} try {tries} of {max_tries}")
                time.sleep(3**tries)
            else:
                raise e



def update_row(spreadsheet_id, range_name, values):
    """
    Update a specific row in a Google Sheet.
    :param spreadsheet_id: The ID of the spreadsheet
    :param range_name: The specific range to update in A1 notation
    :param values: List of new values for the row
    """
    service = get_sheets_service()
    body = {
        'values': [values]
    }
    result = service.values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption='RAW',
        body=body).execute()
    return result

def delete_row(spreadsheet_id, sheet_id, row_index):
    """
    Delete a row from a Google Sheet.
    :param spreadsheet_id: The ID of the spreadsheet
    :param sheet_id: The ID of the sheet within the spreadsheet
    :param row_index: The index of the row to delete
    """
    service = get_sheets_service()
    batch_update_spreadsheet_request_body = {
        "requests": [
            {
                "deleteDimension": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": row_index,
                        "endIndex": row_index + 1
                    }
                }
            }
        ]
    }
    result = service.batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=batch_update_spreadsheet_request_body).execute()
    return result

def get_sheet_data(spreadsheet_id, range_name):
    """
    Retrieves data from a specified range in a Google Sheet.
    
    :param spreadsheet_id: The ID of the spreadsheet.
    :param range_name: The range to retrieve data from, in A1 notation.
    :return: A list of lists where each sublist represents a row of data.
    """
    tries = 0
    max_tries = 10
    while True:
        try:
            service = get_sheets_service()
            result = service.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
            values = result.get('values', [])

            if not values:
                print('No data found.')
            else:
                return values
        except Exception as e:
            print(f"failed to get {spreadsheet_id}:{range_name} due to {e}")
            if tries<max_tries:
                tries+=1
                print(f"retry {tries}/{max_tries}")
                time.sleep(1.66**tries)
            else:
                raise Exception("Unable to get sheet.")
    


def ensureSheetExistence(sheet_name):
    """
    Checks if a sheet exists within a spreadsheet by name. If it does not exist, creates a copy of the 'Template' sheet with the new name.
    :param sheet_name: The name of the sheet to check for existence and create as a copy of 'Template' if not present.
    """
    spreadsheet_id = sheetId  # Use the global variable sheetId
    service = get_sheets_service()
    
    # Get the spreadsheet's existing sheets and titles
    
    spreadsheet = service.get(spreadsheetId=spreadsheet_id).execute()
    sheets = spreadsheet.get('sheets', [])
    sheet_titles = [sheet['properties']['title'] for sheet in sheets]
    template_sheet_id = None
    
    # Find the 'Template' sheet ID
    for sheet in sheets:
        if sheet['properties']['title'].lower() == 'template':
            template_sheet_id = sheet['properties']['sheetId']
            break
    
    if template_sheet_id is None:
        print("Template sheet not found.")
        return
    
    # Check if the target sheet already exists
    if sheet_name not in sheet_titles:
        # Sheet does not exist, create it by duplicating the 'Template' sheet
        body = {
            'requests': [
                {
                    'duplicateSheet': {
                        'sourceSheetId': template_sheet_id,
                        'newSheetName': sheet_name,
                    }
                }
            ]
        }
        service.batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
        print(f"Sheet '{sheet_name}' created by duplicating 'Template'.")
    else:
        print(f"Sheet '{sheet_name}' already exists.")


def extract_date(date_str):
    utc_time = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%fZ")

# Convert to PST (UTC-8)
    pst_time = utc_time.replace(tzinfo=timezone.utc).astimezone(tz=timezone(timedelta(hours=-8)))

    # Converting the date part to the desired format (mm/dd/yyyy)
    formatted_date = pst_time.strftime("%m/%d/%Y")
    
    return formatted_date

def prettify_date(utc_time_str):
    utc_time = datetime.strptime(utc_time_str, "%Y-%m-%dT%H:%M:%S.%fZ")

# Convert to PST (UTC-8)
    pst_time = utc_time.replace(tzinfo=timezone.utc).astimezone(tz=timezone(timedelta(hours=-8)))

    # Format the time in the desired format
    pst_time_str = pst_time.strftime("%d %b %I:%M %p")
    return pst_time_str