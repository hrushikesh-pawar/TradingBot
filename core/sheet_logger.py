import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import logging

logger = logging.getLogger("SheetLogger")

def log_trade(date, action, entry, sl, tp, win_prob, final_call):
    try:
        creds_json = os.getenv("GCP_CREDENTIALS")
        if not creds_json:
            print("GCP_CREDENTIALS not found in environment.")
            return
            
        creds_dict = json.loads(creds_json)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        sheet = client.open("XAU_USD_Trade_Log").sheet1
        
        # AUTOMATIC HEADER SETUP: If row 1 is completely empty, set it up.
        if not sheet.row_values(1):
            print("Headers missing. Setting up headers automatically...")
            sheet.append_row(["Date", "Action", "Entry", "Stop Loss", "Take Profit", "Win Probability", "Final Call"])
            
        row_data = [date, action, entry, sl, tp, win_prob, final_call]
        sheet.append_row(row_data)
        print("✅ Successfully logged trade to Google Sheets.")
        
    except Exception as e:
        logger.error(f"Google Sheets logging failed: {e}")