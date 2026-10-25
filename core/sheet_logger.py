import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os

def log_trade(sheet_name, headers, row_data):
    try:
        creds_json = os.getenv("GCP_CREDENTIALS")
        if not creds_json:
            print("ERROR: GCP_CREDENTIALS not found in environment. If running locally, you must set this variable.")
            return
            
        creds_dict = json.loads(creds_json)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        sheet = client.open(sheet_name).sheet1
        
        # AUTOMATIC HEADER SETUP: Failsafe in case headers are deleted
        if not sheet.row_values(1):
            print(f"Headers missing. Setting up headers for {sheet_name}...")
            sheet.append_row(headers)
            
        sheet.append_row(row_data)
        print(f"✅ Successfully logged trade to {sheet_name}.")
        
    except Exception as e:
        print(f"❌ Google Sheets logging failed for {sheet_name}: {e}")