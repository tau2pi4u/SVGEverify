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
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import asyncio

global emailWait
emailWait = False

global updateWait 
updateWait = False

global backupWait
backupWait = False

# data logger class to produce text logs
class logger():
	def __init__(self, path = 'log.txt'):
		self.log = open(path, "w")
	def LogMessage(self, message):
		try:
			self.log.write(f"{message}\n")
		except:
			self.log.write("Invalid log message input\n")
		print(message)

# Generates and returns a random 10 character string of letters, numbers and punctuation
def GenerateRandomString():
	N = 10 # number of characters
	return ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits + string.punctuation) for _ in range(N))

# Generates email text 
def GenerateEmailText(user, to, rand):
	msg = MIMEMultipart('alternative')
	msg['Subject'] = "SVGE Email Verification"
	msg['From'] = user
	msg['To'] = to

	html = """\
<html>
	<head></head>
	<body>
		<p>This is an automated email sent by the SVGEVerify bot.<br>
		If you did not request this then please ignore it and if you continue to receive them, please contact svge@soton.ac.uk<br>
		Your verification code is:<br>
		<b>%s</b><br>
		Please reply <b>!verify %s</b> to the bot<br>
		Kind regards,<br>
		Southampton Video Games and Esports Society (SVGE)
		</p>
	</body>
</html>""" % (rand, rand)
	html = MIMEText(html, 'html')
	msg.attach(html)
	return msg.as_string()
	

# Logs into an smtp server, sends an email and then logs out
async def SendMail(user, pw, to, text):
	global emailWait
	while emailWait:
		await asyncio.sleep(1)
	emailWait = True
	try:  
		server_ssl = smtplib.SMTP_SSL('smtp.gmail.com', 465)
		server_ssl.ehlo()   # optional
		log.LogMessage(f"Connected to {user}")
		server_ssl.login(user, pw)
		log.LogMessage("Login successful")
		server_ssl.sendmail(user, to, text)
		log.LogMessage(f"Sent message")
		server_ssl.close()
		log.LogMessage("Disconnected")
		# ...send emails
		emailWait = False
	except Exception as e:  
		log.LogMessage(f"Failed to send email with reason {e}")
		emailWait = False

# Updates the user info for a given user 
async def UpdateUserInfo(userId, emailHash):
	global updateWait
	while updateWait:
		await asyncio.sleep(1)
	try:
		updateWait = True
		mLevel = membershipLevel.index("student")
		if(emailHash in userInfo.keys()):
			mLevel = max(mLevel, userInfo[emailHash]["level"])
		userInfo[emailHash] = {"id" : userId, "level" : int(mLevel)}
		#await UpdateMembershipInfo()
		updateWait = False
	except Exception as e:  
		log.LogMessage(f"Failed to send email with reason {e}")
		updateWait = False

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
	global backupWait
	while backupWait:
		await asyncio.sleep(1)
	backupWait = True
	try:
		scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
		creds = ServiceAccountCredentials.from_json_keyfile_name(clientSecret, scope)
		gClient = gspread.authorize(creds)
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
		idToHashMap = {str(info["id"]) : emailHash for emailHash, info in userInfo.items()}
		for member in server.members:
			if(str(member.id) in idToHashMap.keys()):
				info = userInfo[idToHashMap[member.id]]
				for i, level in enumerate(membershipLevel[1:]):
					if(info["level"] > i and info["id"] != 0):
						if(level == "committee"): 
							print(f"User {member.name} is commitee")
							break
						try:
							roleID = str(roleIds[level])
							userRoleIds = [role.id for role in member.roles]
							serverRoles = {role.id : role for role in server.roles}
							if(roleID not in userRoleIds):
								log.LogMessage(f"Attempting to apply role {level} to user {member.name}")
								await client.add_roles(member, serverRoles[roleID])
						except Exception as e:
							log.LogMessage(f"Failed to add role {level} to user {member.name} for reason {e}")
					elif(info["id"] !=0):
						if(level == "committee"): 
							break
						try:
							roleID = str(roleIds[level])
							userRoleIds = [role.id for role in member.roles]
							serverRoles = {role.id : role for role in server.roles}
							if(roleID in userRoleIds):
								log.LogMessage(f"Attempting to remove role {level}")
								await client.remove_roles(member, serverRoles[roleID])
						except Exception as e:
							log.LogMessage(f"Failed to remove role {level} from user {member.name} for reason {e}")
			elif not member.bot:
				guestID = roleIds["guest"]
				userRoleIds = [role.id for role in member.roles]
				serverRoles = {role.id : role for role in server.roles}
				try: 
					if(guestID not in userRoleIds):
						log.LogMessage(f"Attempting to apply role guest")
						await client.add_roles(member, serverRoles[guestID])
				except Exception as e:
					log.LogMessage(f"Failed to add guest role for {member.name} for reason {e}")
				for i, level in enumerate(membershipLevel[1:]):
					if(level == "committee"):
						break
					roleID = roleIds[level]
					try: 
						if(roleID in userRoleIds):
							log.LogMessage(f"Attempting to apply role {level}")
							await client.remove_roles(member, serverRoles[roleID])
					except Exception as e:
						log.LogMessage(f"Failed to remove non guest roles for user {member.name} for reason {e}")
			backupWait = False
		
	except Exception as e:
		backupWait = False
		log.LogMessage(f"Failed to authorise with gmail with reason {e}")
		return
	

async def MassMessageNonVerified():
	verified = [member["id"] for hash, member in userInfo.items()]
	server = client.get_server(svgeServer)
	for member in server.members:
		if(str(member.id) not in str(verified)):
			try:
				log.LogMessage(f"Reminded {member.name}\n")
				await client.send_message(member, "Hi, I'm the SVGE verification bot. You haven't yet verified your Southampton email with me. If you're a member of the university, please send `!email youremail@soton.ac.uk` and then `!verify [code]` where code is the code I emailed to you. If you're not, then sorry for the spam!")
			except Exception as e:
				log.LogMessage(f"Failed to remind {member.name} for reason{e}\n")

# Loads variables from a config file
def LoadConfig(configPath):
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
	with open(configPath, "r") as configJson:
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
	try:
		scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
		creds = ServiceAccountCredentials.from_json_keyfile_name(clientSecret, scope)
		gClient = gspread.authorize(creds)
		sheet = gClient.open("verify_backup").sheet1
		data = sheet.get_all_records()
		userInfo = {row["email_hash"] : {"id" : row["id"], "level" : row["level"]} for row in data}
	except Exception as e:
		log.LogMessage(f"Failed to authorise with gmail with reason {e}")
	

global log
if(len(sys.argv) > 1):
	log = logger(sys.argv[1])
else:
	log = logger()

global gdprMessage
gdprMessage = """We use your information to verify your membership status. By giving us your email address, you agree to us sending you a verification email where it will be stored.
On the pi running the bot, the email is hashed and overwritten as soon as possible. We also store your unique discord ID on the pi and in a google drive spreadsheet.
If you'd like these removed, please contact a committee member, however you will lose access to any discord based benefits of your membership status.
You also agree to our privacy policy which can be found here: https://drive.google.com/file/d/1uGbnFqTkMdIOkDgjbhk3JkSL-c2jRaLe/view"""

#databases
global currentData
currentData = {}
global emailRequestsCount
emailRequestsCount = {}
global currentUpdates
currentUpdates = 0



try:
	LoadConfig(sys.argv[2])
except Exception as e:
	log.LogMessage(f"Failed to load config with reason {e}")
	sys.exit(1)

global clientSecret
clientSecret = sys.argv[3]

try:
	LoadUsers()
except Exception as e:
	log.LogMessage(f"Failed to read user_info.json, error\n{e}")

client = discord.Client()

@client.event
async def on_member_join(member):
	guestID = roleIds["guest"]
	server = client.get_server(svgeServer)
	userRoleIds = [role.id for role in member.roles]
	serverRoles = {role.id : role for role in server.roles}
	try: 
		if(guestID not in userRoleIds):
			log.LogMessage(f"Attempting to apply role guest")
			await client.add_roles(member, serverRoles[guestID])
	except Exception as e:
		log.LogMessage(f"Failed to add guest role for {member.name} for reason {e}")
	await client.send_message(member, """Welcome to the SVGE discord server! If you are a student, please verify this by sending:
	`!email myemail@soton.ac.uk`.
	You should then receive a code via email, which you can use to verify your account by sending:
	`!verify [code]`.
	This will give you access to student only areas as well as any perks given by your membership status.
	GDPR information: 
	%s""" % (gdprMessage))
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
		try:
			log.LogMessage(f"Message received from user {message.author.name} ")
			senderId = message.author.id
			if(message.content[0] == '!'):
				command = message.content[1:].split(' ')
				log.LogMessage(f"Command: {command[0]}\n")
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
	`!verify [code]` - this will link that email to your discord account
	`!gdpr` this will give you our gdpr policy""")
					return
				elif(command[0] == "gdpr"):
					await client.send_message(message.channel, gdprMessage)
					return
				elif(command[0] == "updateCount" and (GetLevelFromUser(message.author.id) == membershipLevel.index("committee") or message.author.id == owner)):
					await client.send_message(message.channel, f"There are currently {currentUpdates} pending updates")
				elif(command[0] == "exit" and message.author.id == owner):
					await client.send_message(message.channel, "Shutting down, goodbye :wave:")
					log.LogMessage("Shutdown command given, goodbye")
					client.close()
					exit(0)
				elif(command[0] == "remind" and message.author.id == owner):
					await MassMessageNonVerified()
					await client.send_message(message.channel, "Reminded users")
					return
				if(len(command) != 2):
					await client.send_message(message.channel, f"Invalid command {command}")
					return
				if(command[0] == "email"):
					server = client.get_server(svgeServer)
					if(message.author.id not in [user.id for user in server.members]):
						await client.send_message(message.channel, f"You are not in the SVGE server, please join before trying to verify")
						return
					count = 0
					if(senderId in emailRequestsCount.keys()):
						count = emailRequestsCount[senderId]
					if(count > 3 and GetLevelFromUser(message.author.id) != membershipLevel.index("committee")):
						await client.send_message(message.channel, f"You've made too many requests, please speak to a committee member to sort this out")
						return
					emailRequestsCount[senderId] = count + 1
					email = command[1]
					try:
						domain = email.split('@')[1]
					except:
						await client.send_message(message.channel, f"That wasn't a valid southampton email, please make sure to include @soton.ac.uk")
						return
					if(domain != "soton.ac.uk"):
						await client.send_message(message.channel, f"Invalid domain {domain}, please make sure it's an @soton.ac.uk email address")
						return
					randomString = GenerateRandomString()
					emailHash = hashlib.sha256(email.encode('utf-8'))
					currentData[senderId] = {"email": emailHash.hexdigest(), "randomString": randomString}
					text = GenerateEmailText(gmailUser, email, currentData[senderId]["randomString"])
					await SendMail(gmailUser, gmailPw, email, text)
					await client.send_message(message.channel, f"We have sent an email to {email} with your code. Please reply with !verify [code] to link your email to your discord account. Please send !gdpr to read our policy")
					email = ""
					return
				elif(command[0] == "verify"):
					if(senderId not in currentData.keys()):
						await client.send_message(message.channel, "You haven't yet requested a code. You can do so by messaging this bot !email [email] where [email] is a valid Southampton email")
						return
					inputCode = command[1]
					trueCode = currentData[senderId]["randomString"]
					if(inputCode == trueCode):
						try:
							await client.send_message(message.channel, "Thanks, that's the correct code - I'll let you know when I've successfully updated all my databases!")
							await UpdateUserInfo(senderId, currentData[senderId]["email"])
						except:
							await client.send_message(message.channel, f"Something went wrong, please try again. If it continues to fail, please contact tau")
							return
						del currentData[senderId]
						await client.send_message(message.channel, "Congratulations, you're verified. You should see your permissions adjusted to become correct soon")
					else:
						await client.send_message(message.channel, "Sorry, that's not right. Please check the code you entered")
					return

				await client.send_message(message.channel, "Unrecognised command {command}")
		except Exception as e:
			log.LogMessage("Something went wrong with a command, error message: {e}")
			await client.send_message(message.channel, "Something went wrong, please try again and if this persists, contact tau")
			

client.run(discordToken)




