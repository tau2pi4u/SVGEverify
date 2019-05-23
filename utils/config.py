import logging
import json
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import sys

# Loads variables from a config file
def LoadConfig(configPath):
    with open(configPath, "r") as configJson:
        cfg = json.load(configJson)
    with open(cfg['gmail']['template'], "r") as template:
        cfg['gmail']['template'] = template.read()
    return cfg

def LoadUsers(cfg):
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(cfg['sheets']['secret'], scope)
        gClient = gspread.authorize(creds)
        sheet = gClient.open("verify_backup").sheet1
        data = sheet.get_all_records()
        userInfo = {row["email_hash"] : {"id" : int(row["id"]), "level" : int(row["level"])} for row in data}
        return userInfo
    except Exception as e:
        logging.warning(f"Failed to authorise with gmail with reason {e}")