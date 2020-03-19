import logging
import json
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import sys

# Loads variables from a config file
def LoadConfig(configPath):
    # load the config file
    with open(configPath, "r") as configJson:
        cfg = json.load(configJson)
    # Load the email template
    with open(cfg['gmail']['template'], "r") as template:
        cfg['gmail']['template'] = template.read()
    # make the membership levels a list of the role_ids
    cfg['discord']['membership_level'] = list(cfg['discord']['role_ids'].keys())
    logging.info(f"Membership levels: {list(enumerate(cfg['discord']['membership_level']))}")
    return cfg

# Loads the user database backup from a sheet in the top level
# of the drive with the name "verify_backup"
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
        return {}