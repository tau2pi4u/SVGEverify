import logging
from oauth2client.service_account import ServiceAccountCredentials
import gspread

# Updates the user info for a given user 
async def UpdateUserInfo(ctx, userId, emailHash, bot, db, cfg):
    try:
        mLevel = GetLevelFromString("student")
        if(emailHash in db['user_info'].keys() and db['user_info'][emailHash]["id"] != 0): # user already exists
            return False
        if(emailHash in db['user_info'].keys()):
            if(db['user_info'][emailHash]["level"] == -1):
                logging.info(f"User ID {userId} was previously banned")
                return False
        db['user_info'][emailHash] = {"id" : userId, "level" : int(mLevel)}
        await UpdateMemberInfo(ctx, emailHash, bot, db, cfg)
        return True
    except Exception as e:  
        logging.warning(f"Failed update user info with reason {e}")
        return False

# Returns the membership level of a user
def GetLevelFromUser(discordID, db):
    for email, info in db['user_info'].items():
        if(info["id"] == discordID):
            return info["level"]
    return 0

# Returns the membership level integer value of a given role string
def GetLevelFromString(levelString):
    try:
        return cfg['discord']['membership_level'].index(levelString)
    except:
        return 0

async def UpdateMemberInfo(ctx, emailHash, bot, db, cfg):
    try:
        guild = bot.get_guild(cfg['discord']['guild'])
        member = guild.get_member(db['user_info'][emailHash]["id"])
        info = db['user_info'][emailHash]
        guildRoles = {role.id : role for role in guild.roles}
        userRoleIds = [role.id for role in member.roles]
        guestID = cfg['discord']['role_ids']['guest']
        try: 
            if(guestID in userRoleIds):
                logging.info(f"Attempting to remove role guest")
                await member.remove_roles(guildRoles[guestID])
        except Exception as e:
            logging.warning(f"Failed to remove role guest with reason {e}")
        for i, level in enumerate(cfg["discord"]["membership_level"][1:]):
            if(info["level"] > i and info["id"] != 0):
                if(i == "committee"): 
                    print(f"User {member.name} is commitee")
                    break
                try:
                    roleID = cfg['discord']['role_ids'][level]
                    userRoleIds = [role.id for role in member.roles]
                    mutedRoleId = cfg['discord']['role_ids']["muted"]
                    if(roleID not in userRoleIds and mutedRoleId not in userRoleIds):
                        logging.info(f"Attempting to apply role {level} to user {member.name}")
                        await member.add_roles(guildRoles[roleID])
                except Exception as e:
                    logging.warning(f"Failed to add role {level} to user {member.name} for reason {e}")
            elif(info["id"] !=0):
                if(i == "committee"): 
                    break
                try:
                    roleID = int(cfg['discord']['role_ids'][level])
                    userRoleIds = [role.id for role in member.roles]
                    if(roleID in userRoleIds):
                        logging.info(f"Attempting to remove role {level}")
                        await member.remove_roles(guildRoles[roleID])
                except Exception as e:
                    logging.warning(f"Failed to remove role {level} from user {member.name} for reason {e}")
    except Exception as e:
        logging.warning(f"Failed to update member info for reason {e}\n")

async def BackupMembershipInfo(bot, db, cfg):
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(cfg['sheets']['secret'], scope)
        gClient = gspread.authorize(creds)
        backupCSV = "email_hash,id,level"
        for emailHash, info in db['user_info'].items():
            backupCSV += f"\n{str(emailHash)},{int(info['id'])},{int(info['level'])}"
        gClient.import_csv(cfg['sheets']['backup_id'], backupCSV)
    except Exception as e:
        logging.warning(f"Failed to backup for reason {e}")

# Updates the membership data for all members and backs up
async def UpdateMembershipInfo(bot, db, cfg):
    import hashlib
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(cfg['sheets']['secret'], scope)
        gClient = gspread.authorize(creds)
        sheet = gClient.open("member_data").sheet1
        data = sheet.get_all_records()
        for row in data:
            hash = hashlib.sha256(row["email"].encode('utf-8')).hexdigest()
            if(hash in db['user_info'].keys()):
                if(db['user_info'][hash]["level"] != -1):
                    db['user_info'][hash]["level"] = int(GetLevelFromString(row["level"]))
            else:
                db['user_info'][hash] = {"level" : int(GetLevelFromString(row["level"])), "id": 0}
        try:
            backupCSV = "email_hash,id,level"
            for emailHash, info in db['user_info'].items():
                backupCSV += f"\n{str(emailHash)},{int(info['id'])},{int(info['level'])}"
            gClient.import_csv(cfg['sheets']['backup_id'], backupCSV)
        except Exception as e:
            logging.warning(f"Failed to backup for reason {e}")
        guild = bot.get_guild(cfg['discord']['guild'])
        idToHashMap = {int(info["id"]) : emailHash for emailHash, info in db['user_info'].items()}
        for member in guild.members:
            if(member.id in idToHashMap.keys()):
                info = db['user_info'][idToHashMap[member.id]]
                guestID = cfg['discord']['role_ids']["guest"]
                guildRoles = {role.id : role for role in guild.roles}
                try: 
                    userRoleIds = [role.id for role in member.roles]
                    if(guestID in userRoleIds):
                        logging.info(f"Attempting to remove role guest")
                        await member.remove_roles(guildRoles[guestID])
                except Exception as e:
                    logging.warning(f"Failed to remove role guest with reason {e}")
                for i, level in enumerate(cfg['discord']['membership_level'][1:]):
                    if(info["level"] > i and info["id"] != 0):
                        if(level == "committee"): 
                            print(f"User {member.name} is commitee")
                            break
                        try:
                            roleID = int(cfg['discord']['role_ids'][level])
                            userRoleIds = [role.id for role in member.roles]
                            mutedRoleId = cfg['discord']['role_ids']["muted"]
                            if(roleID not in userRoleIds and mutedRoleId not in userRoleIds):
                                logging.info(f"Attempting to apply role {level} to user {member.name}")
                                await member.add_roles(guildRoles[roleID])
                        except Exception as e:
                            logging.warning(f"Failed to add role {level} to user {member.name} for reason {e}")
                    elif(info["id"] !=0):
                        if(level == "committee"): 
                            break
                        try:
                            roleID = int(cfg['discord']['role_ids'][level])
                            userRoleIds = [role.id for role in member.roles]
                            if(roleID in userRoleIds):
                                logging.info(f"Attempting to remove role {level}")
                                await member.remove_roles(guildRoles[roleID])
                        except Exception as e:
                            logging.warning(f"Failed to remove role {level} from user {member.name} for reason {e}")
            elif not member.bot:
                guestID = cfg['discord']['role_ids']["guest"]
                userRoleIds = [role.id for role in member.roles]
                guildRoles = {role.id : role for role in guild.roles}
                try: 
                    if(guestID not in userRoleIds):
                        logging.info(f"Attempting to apply role guest")
                        await member.add_roles(guildRoles[guestID])
                except Exception as e:
                    logging.warning(f"Failed to add guest role for {member.name} for reason {e}")
                for i, level in enumerate(cfg['discord']['membership_level'][1:]):
                    if(level == "committee"):
                        break
                    roleID = cfg['discord']['role_ids'][level]
                    try: 
                        if(roleID in userRoleIds):
                            logging.info(f"Attempting to apply role {level}")
                            await member.remove_roles(guildRoles[roleID])
                    except Exception as e:
                        logging.warning(f"Failed to remove non guest roles for user {member.name} for reason {e}")
        
    except Exception as e:
        logging.warning(f"Failed to authorise with gmail with reason {e}")
        return
    

async def MassMessageNonVerified(ctx, bot, db, cfg):
    verified = [member["id"] for hash, member in db['user_info'].items()]
    guild = bot.get_guild(cfg['discord']['guild'])
    for member in guild.members:
        if(int(member.id) not in int(verified)):
            try:
                logging.info(f"Reminded {member.name}\n")
                await member.send(f"Hi, I'm the {cfg['uni']['society']} verification bot. You haven't yet verified your {cfg['uni']['name']} email with me. If you're a member of the university, please send `!email youremail@{cfg['uni']['domain']}` and then `!verify [code]` where code is the code I emailed to you. If you're not, then sorry for the spam!")
            except Exception as e:
                logging.warning(f"Failed to remind {member.name} for reason{e}\n")

def banUser(userId, db):
    if(userId == "0"):
        return False
    idToHashMap = {int(info['id']): hash for hash, info in db['user_info'].items()}
    if(userId not in idToHashMap.keys()):
        return False
    db['user_info'][idToHashMap[userId]]["level"] = -1
    return True

def unbanUser(userId, db):
    if(userId == "0"):
        return False
    idToHashMap = {int(info['id']): hash for hash, info in db['user_info'].items()}
    if(userId not in idToHashMap.keys()):
        return False
    if(db['user_info'][idToHashMap[userId]]["level"] < 0):
        db['user_info'][idToHashMap[userId]]["level"] = 1
        return True
    return False