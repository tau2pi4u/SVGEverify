import discord
import smtplib
import random
import string
import json
import hashlib
import gspread
from enum import Enum
from oauth2client.service_account import ServiceAccountCredentials
import sys


# data logger class to produce text logs
class logger():
	def __init__(self):
		self.log = open("log.txt", "w")
	def LogMessage(self, message):
		self.log.write(message)
		print(message)

# Generates and returns a random 10 character string of letters, numbers and punctuation
def GenerateRandomString():
	N = 10 # number of characters
	return ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits + string.punctuation) for _ in range(N))

# Generates email text 
def GenerateEmailText(user, to, rand):
	return """\
From: %s
To: %s
Subject: SVGE Email Verification

This is an automated email sent by the SVGEVerify bot. 
If you did not request this then please ignore it and if you continue to receive them, please contact svge@soton.ac.uk
Your verification code is:
<b>%s</b>
Please reply !verify <b>%s</b> to the bot

SVGE""" % (user, to, rand, rand)

# Logs into an smtp server, sends an email and then logs out
def SendMail(user, pw, to, text):
	try:  
		server_ssl = smtplib.SMTP_SSL('smtp.gmail.com', 465)
		server_ssl.ehlo()   # optional
		log.LogMessage(f"Connected to {user}")
		server_ssl.login(user, pw)
		log.LogMessage("Login successful")
		server_ssl.sendmail(user, to, text)
		log.LogMessage(f"Sent to {to}")
		server_ssl.close()
		log.LogMessage("Disconnected")
		# ...send emails
	except Exception as e:  
		log.LogMessage(f"Failed to send email with reason {e}")

# Updates the user info for a given user 
async def UpdateUserInfo(userId, emailHash):
	mLevel = membershipLevel.index("student")
	if(emailHash in userInfo.keys()):
		mLevel = max(mLevel, userInfo[emailHash]["level"])
	userInfo[emailHash] = {"id" : userId, "level" : int(mLevel)}
	await UpdateMembershipInfoForUser(userId, emailHash)

# Returns the membership level of a user
def GetLevelFromUser(discordID):
	for email, info in userInfo.items():
		if(info["id"] == discordID):
			return info["level"]
	return 0

# Returns the membership level integer value of a given role string
def GetLevelFromString(levelString):
	try:
		return membershipLevel.index(levelString)
	except:
		return 0

# Updates the membership data for all members and backs up
async def UpdateMembershipInfo():
	sheet = gClient.open("member_data").sheet1
	data = sheet.get_all_records()
	for row in data:
		hash = hashlib.sha256(row["email"].encode('utf-8')).hexdigest()
		if(hash in userInfo.keys()):
			userInfo[hash]["level"] = int(GetLevelFromString(row["level"]))
		else:
			userInfo[hash] = {"level" : int(GetLevelFromString(row["level"])), "id": 0}
	try:
		backup = gClient.open("verify_backup").sheet1
		backup.clear()
		backup.append_row(['email_hash', 'id', 'level'])
		for emailHash, info in userInfo.items():
			backup.append_row([str(emailHash), str(info["id"]), int(info["level"])])
	except Exception as e:
		log.LogMessage(f"Failed to backup for reason {e}")

	server = client.get_server(svgeServer)
	for emailHash, info in userInfo.items():
		log.LogMessage(f"Updating roles for user {info['id']} with level {info['level']}")
		for i, level in enumerate(membershipLevel[1:]):
			if(info["level"] > i and info["id"] != 0):
				if(level == "committee"): 
					print("User is commitee")
					break
				try:
					user = server.get_member(str(info["id"]))
					roleID = str(roleIds[level])
					userRoleIds = [role.id for role in user.roles]
					serverRoles = {role.id : role for role in server.roles}
					if(roleID not in userRoleIds):
						log.LogMessage(f"Attempting to apply role {level}")
						await client.add_roles(user, serverRoles[roleID])
				except Exception as e:
					log.LogMessage(f"Failed to update user {info['id']} for reason {e}")

# updates the membership info of a given member and backs it up
async def UpdateMembershipInfoForUser(userID, emailHash):
	sheet = gClient.open("member_data").sheet1
	data = sheet.get_all_records()
	for row in data:
		hash = hashlib.sha256(row["email"].encode('utf-8')).hexdigest()
		if(hash != emailHash):
			continue
		if(hash in userInfo.keys()):
			userInfo[hash]["level"] = int(GetLevelFromString(row["level"]))
		else:
			userInfo[hash] = {"level" : int(GetLevelFromString(row["level"])), "id": 0}
	try:
		backup = gClient.open("verify_backup").sheet1
		backup.clear()
		backup.append_row(['email_hash', 'id', 'level'])
		for emailHash, info in userInfo.items():
			backup.append_row([str(emailHash), str(info["id"]), int(info["level"])])
	except Exception as e:
		log.LogMessage(f"Failed to backup for reason {e}")

	server = client.get_server(svgeServer)
	info = userInfo[emailHash]
	log.LogMessage(f"Updating roles for user {info['id']} with level {info['level']}")
	for i, level in enumerate(membershipLevel[1:]):
		if(info["level"] > i and info["id"] != 0):
			if(level == "committee"): 
				print("User is commitee")
				break
			try:
				user = server.get_member(str(info["id"]))
				roleID = str(roleIds[level])
				userRoleIds = [role.id for role in user.roles]
				serverRoles = {role.id : role for role in server.roles}
				if(roleID not in userRoleIds):
					log.LogMessage(f"Attempting to apply role {level}")
					await client.add_roles(user, serverRoles[roleID])
			except Exception as e:
				log.LogMessage(f"Failed to update user {info['id']} for reason {e}")

# Loads variables from a config file
def LoadConfig():
	#discord info
	global discordToken
	global svgeServer
	global owner
	global membershipLevel
	global roleIds
	#gmail info
	global gmailUser
	global gmailPw
	config = {}
	with open("config.json", "r") as configJson:
		config = json.load(configJson)
	gmailUser = config["gmail"]["user"]
	gmailPw = config["gmail"]["pw"]
	discordToken = config["discord"]["token"]
	svgeServer = config["discord"]["server"]
	owner = config["owner"]
	roleIds = config["discord"]["roleIds"]
	membershipLevel = config["discord"]["membershipLevel"]


def LoadUsers():
	global userInfo
	sheet = gClient.open("verify_backup").sheet1
	data = sheet.get_all_records()
	userInfo = {row["email_hash"] : {"id" : row["id"], "level" : row["level"]} for row in data}

global log
log = logger()


global gClient
try:
	scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
	creds = ServiceAccountCredentials.from_json_keyfile_name('client_secret.json', scope)
	gClient = gspread.authorize(creds)
except Exception as e:
	log.LogMessage(f"Failed to authorise with gmail with reason {e}")

#databases
global currentData
currentData = {}
global emailRequestsCount
emailRequestsCount = {}
global currentUpdates
currentUpdates = 0

try:
	LoadConfig()
except Exception as e:
	log.LogMessage(f"Failed to load config with reason {e}")
	sys.exit(1)

try:
	LoadUsers()
except Exception as e:
	log.LogMessage(f"Failed to read user_info.json, error\n{e}")

client = discord.Client()

@client.event
async def on_member_join(member):
	await client.send_message(member, """Welcome to the SVGE discord server! If you are a student, please verify this by sending:
	`!email myemail@soton.ac.uk`.
	You should then receive a code via email, which you can use to verify your account by sending:
	`!verify [code]`.
	This will give you access to student only areas as well as any perks given by your membership status.""")
	log.LogMessage(f"Sent welcome message to user {member.name}\n")

@client.event
async def on_ready():
	global HELP
	log.LogMessage('Logged in as')
	log.LogMessage(client.user.name)
	log.LogMessage(client.user.id)
	log.LogMessage('------')

@client.event
async def on_message(message):
	if message.channel.is_private and message.author != client.user:
		log.LogMessage(f"Message received from user {message.author.name}")
		senderId = message.author.id
		if(message.content[0] == '!'):
			command = message.content[1:].split(' ')
			if(command[0] == "update"): 
				if (GetLevelFromUser(message.author.id) == membershipLevel.index("committee") or message.author.id == owner):
					await UpdateMembershipInfo()
					await client.send_message(message.channel, "Updated membership info\n")
				else:
					await client.send_message(message.channel, "Please ask a committe member to do this\n")
				return
			elif(command[0] == "help"):
				await client.send_message(message.channel, """Commands are: 
`!help` - gives this messsage
`!update` - (committee only) updates user info
`!email [email]` - this will send an email to that address with a verification code
`!verify [code]` - this will link that email to your discord account""")
				return
			elif(command[0] == "updateCount" and (GetLevelFromUser(message.author.id) == membershipLevel.index("committee") or message.author.id == owner)):
				await client.send_message(message.channel, f"There are currently {currentUpdates} pending updates")
			if(len(command) != 2):
				await client.send_message(message.channel, f"Invalid command {command}")
				return
			if(command[0] == "email"):
				count = 0
				if(senderId in emailRequestsCount.keys()):
					count = emailRequestsCount[senderId]
				if(count > 5 and GetLevelFromUser(message.author.id) != membershipLevel.index("committee")):
					await client.send_message(message.channel, f"You've made too many requests, please speak to a committee member to sort this out")
					return
				emailRequestsCount[senderId] = count + 1
				email = command[1]
				domain = email.split('@')[1]
				if(domain != "soton.ac.uk"):
					await client.send_message(message.channel, f"Invalid domain {domain}")
					return
				randomString = GenerateRandomString()
				emailHash = hashlib.sha256(email.encode('utf-8'))
				currentData[senderId] = {"email": emailHash.hexdigest(), "randomString": randomString}
				text = GenerateEmailText(gmailUser, email, currentData[senderId]["randomString"])
				log.LogMessage(text)
				SendMail(gmailUser, gmailPw, email, text)
				await client.send_message(message.channel, f"We have sent an email to {email} with your code. Please reply with !verify [code] to link your email to your discord account")
				return
			elif(command[0] == "verify"):
				if(senderId not in currentData.keys()):
					await client.send_message(message.channel, "You haven't yet requested a code. You can do so by messaging this bot !email [email] where [email] is a valid Southampton email")
					return
				inputCode = command[1]
				trueCode = currentData[senderId]["randomString"]
				if(inputCode == trueCode):
					await UpdateUserInfo(senderId, currentData[senderId]["email"])
					del currentData[senderId]
					await client.send_message(message.channel, "Congratulations, you're verified. You should see your permissions adjusted to become correct soon")
				else:
					await client.send_message(message.channel, "Sorry, that's not right. Please check the code you entered")
				return

			await client.send_message(message.channel, "Unrecognised command {command}")
			

client.run(discordToken)




