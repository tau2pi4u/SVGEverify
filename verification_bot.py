import discord
from discord.ext import commands
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
import time

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
	return ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(N))

# Generates email text 
def GenerateEmailText(user, to, rand):
	msg = MIMEMultipart('alternative')
	msg['Subject'] = f"{societyName} Email Verification"
	msg['From'] = user
	msg['To'] = to
	html = emailTemplate
	html = html.replace("[code]", rand, 2)
	html = MIMEText(html, 'html')
	msg.attach(html)
	return msg.as_string()
	

# Logs into an smtp server, sends an email and then logs out
async def SendMail(user, pw, to, text):
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
	except Exception as e:  
		log.LogMessage(f"Failed to send email with reason {e}")

# Updates the user info for a given user 
async def UpdateUserInfo(ctx, userId, emailHash):
	try:
		mLevel = membershipLevel.index("student")
		if(emailHash in userInfo.keys() and userInfo[emailHash]["id"] != 0): # user already exists
			return False
		if(emailHash in userInfo.keys()):
			if(userInfo[emailHash]["level"] == -1):
				log.LogMessage(f"User ID {userId} was previously banned")
				return False
		userInfo[emailHash] = {"id" : userId, "level" : int(mLevel)}
		await UpdateMemberInfo(ctx, emailHash)
		return True
	except Exception as e:  
		log.LogMessage(f"Failed update user info with reason {e}")
		return False

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

async def UpdateMemberInfo(ctx, emailHash):
	try:
		guild = bot.get_guild(societyGuild)
		member = guild.get_member(userInfo[emailHash]["id"])
		info = userInfo[emailHash]
		guildRoles = {role.id : role for role in guild.roles}
		userRoleIds = [role.id for role in member.roles]
		guestID = roleIds["guest"]
		try: 
			if(guestID in userRoleIds):
				log.LogMessage(f"Attempting to remove role guest")
				await member.remove_roles(guildRoles[guestID])
		except Exception as e:
			log.LogMessage(f"Failed to remove role guest with reason {e}")
		for i, level in enumerate(membershipLevel[1:]):
			if(info["level"] > i and info["id"] != 0):
				if(i == "committee"): 
					print(f"User {member.name} is commitee")
					break
				try:
					roleID = roleIds[level]
					userRoleIds = [role.id for role in member.roles]
					mutedRoleId = roleIds["muted"]
					if(roleID not in userRoleIds and mutedRoleId not in userRoleIds):
						log.LogMessage(f"Attempting to apply role {level} to user {member.name}")
						await member.add_roles(guildRoles[roleID])
				except Exception as e:
					log.LogMessage(f"Failed to add role {level} to user {member.name} for reason {e}")
			elif(info["id"] !=0):
				if(i == "committee"): 
					break
				try:
					roleID = int(roleIds[level])
					userRoleIds = [role.id for role in member.roles]
					if(roleID in userRoleIds):
						log.LogMessage(f"Attempting to remove role {level}")
						await member.remove_roles(guildRoles[roleID])
				except Exception as e:
					log.LogMessage(f"Failed to remove role {level} from user {member.name} for reason {e}")
	except Exception as e:
		log.LogMessage(f"Failed to update member info for reason {e}\n")


# Updates the membership data for all members and backs up
async def UpdateMembershipInfo():
	try:
		scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
		creds = ServiceAccountCredentials.from_json_keyfile_name(clientSecret, scope)
		gClient = gspread.authorize(creds)
		sheet = gClient.open("member_data").sheet1
		data = sheet.get_all_records()
		for row in data:
			hash = hashlib.sha256(row["email"].encode('utf-8')).hexdigest()
			if(hash in userInfo.keys()):
				if(userInfo[hash]["level"] != -1):
					userInfo[hash]["level"] = int(GetLevelFromString(row["level"]))
			else:
				userInfo[hash] = {"level" : int(GetLevelFromString(row["level"])), "id": 0}
		try:
			backupCSV = "email_hash,id,level"
			for emailHash, info in userInfo.items():
				backupCSV += f"\n{str(emailHash)},{int(info['id'])},{int(info['level'])}"
			gClient.import_csv(sheetID, backupCSV)
		except Exception as e:
			log.LogMessage(f"Failed to backup for reason {e}")
		guild = bot.get_guild(societyGuild)
		idToHashMap = {int(info["id"]) : emailHash for emailHash, info in userInfo.items()}
		for member in guild.members:
			if(member.id in idToHashMap.keys()):
				info = userInfo[idToHashMap[member.id]]
				guestID = roleIds["guest"]
				guildRoles = {role.id : role for role in guild.roles}
				try: 
					userRoleIds = [role.id for role in member.roles]
					if(guestID in userRoleIds):
						log.LogMessage(f"Attempting to remove role guest")
						await member.remove_roles(guildRoles[guestID])
				except Exception as e:
					log.LogMessage(f"Failed to remove role guest with reason {e}")
				for i, level in enumerate(membershipLevel[1:]):
					if(info["level"] > i and info["id"] != 0):
						if(level == "committee"): 
							print(f"User {member.name} is commitee")
							break
						try:
							roleID = int(roleIds[level])
							userRoleIds = [role.id for role in member.roles]
							mutedRoleId = roleIds["muted"]
							if(roleID not in userRoleIds and mutedRoleId not in userRoleIds):
								log.LogMessage(f"Attempting to apply role {level} to user {member.name}")
								await member.add_roles(guildRoles[roleID])
						except Exception as e:
							log.LogMessage(f"Failed to add role {level} to user {member.name} for reason {e}")
					elif(info["id"] !=0):
						if(level == "committee"): 
							break
						try:
							roleID = int(roleIds[level])
							userRoleIds = [role.id for role in member.roles]
							if(roleID in userRoleIds):
								log.LogMessage(f"Attempting to remove role {level}")
								await member.remove_roles(guildRoles[roleID])
						except Exception as e:
							log.LogMessage(f"Failed to remove role {level} from user {member.name} for reason {e}")
			elif not member.bot:
				guestID = roleIds["guest"]
				userRoleIds = [role.id for role in member.roles]
				guildRoles = {role.id : role for role in guild.roles}
				try: 
					if(guestID not in userRoleIds):
						log.LogMessage(f"Attempting to apply role guest")
						await member.add_roles(guildRoles[guestID])
				except Exception as e:
					log.LogMessage(f"Failed to add guest role for {member.name} for reason {e}")
				for i, level in enumerate(membershipLevel[1:]):
					if(level == "committee"):
						break
					roleID = roleIds[level]
					try: 
						if(roleID in userRoleIds):
							log.LogMessage(f"Attempting to apply role {level}")
							await member.remove_roles(guildRoles[roleID])
					except Exception as e:
						log.LogMessage(f"Failed to remove non guest roles for user {member.name} for reason {e}")
		
	except Exception as e:
		log.LogMessage(f"Failed to authorise with gmail with reason {e}")
		return
	

async def MassMessageNonVerified(ctx):
	verified = [member["id"] for hash, member in userInfo.items()]
	guild = bot.get_guild(societyGuild)
	for member in guild.members:
		if(int(member.id) not in int(verified)):
			try:
				log.LogMessage(f"Reminded {member.name}\n")
				await member.send(f"Hi, I'm the {societyName} verification bot. You haven't yet verified your {uniName} email with me. If you're a member of the university, please send `!email youremail@{uniDomain}` and then `!verify [code]` where code is the code I emailed to you. If you're not, then sorry for the spam!")
			except Exception as e:
				log.LogMessage(f"Failed to remind {member.name} for reason{e}\n")

async def CreateVote(ctx, msg):
	try:
		voteTitle = msg[0] 
		voteChannel = msg[1]
		candidates = []
		currentCandidate = ""
		for s in msg[2:]:
			if(s[-1] == ','):
				currentCandidate += s[0:-1]
				candidates.append(currentCandidate)
				currentCandidate = ""
			else:
				currentCandidate += s + " "
		candidates.append(currentCandidate[:-1])
		votes[voteTitle] = {"candidates" : {candidate.lower(): {"name": candidate, "count": 0} for candidate in candidates}, "voterids": [], "channelid": int(voteChannel)}
		await ctx.send(f"Created vote {voteTitle} with candidates {candidates}")
	except Exception as e:
		await ctx.send(f"Failed to create vote with reason {e}")

async def Vote(ctx, msg, id):
	try:
		voteTitle = msg[0]
		voteForU = ' '.join(msg[1:])
		voteFor = voteForU.lower()
		if(voteTitle in votes.keys()):
			if(id in votes[voteTitle]["voterids"]):
				await ctx.send("You've already voted.")
				return
			channel = bot.get_channel(votes[voteTitle]["channelid"])
			validVoters = [member.id for member in channel.members]
			if(id not in validVoters):
				await ctx.send("You're not attending the relevant meeting")
				return
			if(voteFor in votes[voteTitle]["candidates"].keys()):
				votes[voteTitle]["candidates"][voteFor]["count"] += 1
				votes[voteTitle]["voterids"].append(id)
				await ctx.send(f"You voted for {votes[voteTitle]['candidates'][voteFor]['name']} in the vote for {voteTitle}.")
			else:
				await ctx.send(f"{voteForU} is not a candidate for {voteTitle} - are you sure you spelled everything correctly?")
		else:
			await ctx.send(f"{voteTitle} is not currently an active vote - are you sure you spelled everything correctly? Vote titles are case sensitive.")
	except Exception as e:
		await ctx.send("Something went wrong, please try again. If this persists, contact a committee member")

async def EndVote(ctx, msg):
	try:
		voteTitle = msg[0]
		if(voteTitle in votes.keys()):
			winnerName = []
			winnerVotes = 0
			res = f"There were {len(votes[voteTitle]['voterids'])} for the position of {voteTitle}.\n"
			for candidate, info in votes[voteTitle]['candidates'].items():
				candidateName = info["name"]
				count = info["count"]
				res += f"{candidateName}: {count}\n"
				if(count > winnerVotes):
					winnerName = [candidateName]
					winnerVotes = count
				elif(count == winnerVotes):
					winnerName.append(candidateName)
			if len(winnerName) == 1:
				res += f"{winnerName} won with {winnerVotes} votes"
			else:
				res += f"There was a tie between the candidates {winnerName} with {winnerVotes} votes"
			del votes[voteTitle]
			await ctx.send(res)
		else:
			await ctx.send(f"Vote {voteTitle} does not exist")
	except Exception as e:
		await ctx.send(f"Something went wrong - try again. Error: {e}")

async def GetVotes(ctx):
	res = "Currently active votes:\n"
	for title, info in votes.items():
		candidates = ', '.join([candidate["name"] for candidate in info["candidates"].values()])
		res += f"Vote: `{title}`\nCandidates: `{candidates}`\n\n"
	await ctx.send(res)


# Loads variables from a config file
def LoadConfig(configPath):
	#uni info
	global uniDomain
	global uniName
	global societyName
	#discord info
	global discordToken
	global societyGuild
	global owner
	global membershipLevel
	global roleIds
	#gmail info
	global gmailUser
	global gmailPw
	#sheet info
	global sheetID
	config = {}
	with open(configPath, "r") as configJson:
		config = json.load(configJson)
	gmailUser = config["gmail"]["user"]
	gmailPw = config["gmail"]["pw"]
	discordToken = config["discord"]["token"]
	societyGuild = int(config["discord"]["server"])
	owner = config["owner"]
	uniDomain = config["uni"]["domain"]
	uniName = config["uni"]["name"]
	societyName = config["uni"]["society"]
	roleIds = config["discord"]["roleIds"]
	membershipLevel = config["discord"]["membershipLevel"]
	sheetID = config["sheets"]["backupID"]


def LoadUsers():
	global userInfo
	try:
		scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
		creds = ServiceAccountCredentials.from_json_keyfile_name(clientSecret, scope)
		gClient = gspread.authorize(creds)
		sheet = gClient.open("verify_backup").sheet1
		data = sheet.get_all_records()
		userInfo = {row["email_hash"] : {"id" : int(row["id"]), "level" : int(row["level"])} for row in data}
	except Exception as e:
		log.LogMessage(f"Failed to authorise with gmail with reason {e}")
	
def banUser(userId):
	if(userId == "0"):
		return False
	idToHashMap = {int(info['id']): hash for hash, info in userInfo.items()}
	if(userId not in idToHashMap.keys()):
		return False
	userInfo[idToHashMap[userId]]["level"] = -1
	return True

def unbanUser(userId):
	if(userId == "0"):
		return False
	idToHashMap = {int(info['id']): hash for hash, info in userInfo.items()}
	if(userId not in idToHashMap.keys()):
		return False
	if(userInfo[idToHashMap[userId]]["level"] < 0):
		userInfo[idToHashMap[userId]]["level"] = 1
		return True
	return False

global log
if(len(sys.argv) > 1):
	log = logger(sys.argv[1])
else:
	log = logger()

global gdprMessage
gdprMessage = """We use your information to verify your membership status. By giving us your email address, you agree to us sending you a verification email and processing it for the purpose of this bot.
On the pi running the bot, the email is hashed and the plaintext version overwritten as soon as possible. We also store your unique discord ID on the pi and in a google drive spreadsheet.
If you'd like these removed, please contact a committee member, however you will lose access to any discord based benefits of your membership status.
You also agree to our privacy policy which can be found here: https://drive.google.com/file/d/1uGbnFqTkMdIOkDgjbhk3JkSL-c2jRaLe/view"""

#databases
global currentData
currentData = {}
global emailRequestsCount
emailRequestsCount = {}
global currentUpdates
currentUpdates = 0
global votes
votes = {}

global emailTemplate
with open(str(sys.argv[4]), "r") as template:
	emailTemplate = template.read()

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

bot = commands.Bot(command_prefix = '*')

@bot.event
async def on_member_join(member):
	guestID = roleIds["guest"]
	guild = bot.get_guild(societyGuild)
	userRoleIds = [role.id for role in member.roles]
	guildRoles = {role.id : role for role in guild.roles}
	try: 
		if(guestID not in userRoleIds):
			log.LogMessage(f"Attempting to apply role guest")
			await member.add_roles(guildRoles[guestID])
	except Exception as e:
		log.LogMessage(f"Failed to add guest role for {member.name} for reason {e}")
	await member.send_message(f"""Welcome to the {soceityName} discord server! If you are a student, please verify this by sending:
	`!email myemail@{uniDomain}`.
	You should then receive a code via email, which you can use to verify your account by sending:
	`!verify [code]`.
	This will give you access to student only areas as well as any perks given by your membership status.
	GDPR information: 
	%s""" % (gdprMessage))
	log.LogMessage(f"Sent welcome message to user {member.name}\n")

@bot.event
async def on_ready():
	log.LogMessage('Logged in as')
	log.LogMessage(bot.user.name)
	log.LogMessage(bot.user.id)
	log.LogMessage('------')

@bot.event
async def on_message(msg):
	if type(msg.channel) is discord.DMChannel and msg.author != bot.user:
		await bot.process_commands(msg)

@bot.command(name = 'email', help = f"{bot.command_prefix}email youremail@{uniDomain}")
async def EmailCmd(ctx):
	
	try:
		guild = bot.get_guild(societyGuild)
		userId = ctx.author.id
		if(userId not in [user.id for user in guild.members]):
			await ctx.send(f"You are not in the {societyName} server, please join before trying to verify")
			return
		count = 0 if userId not in emailRequestsCount.keys() else emailRequestsCount[userId]
		if count > 3:
			await ctx.send(f"You've made too many requests, please speak to a committee member to sort this out")
			return
		email = ctx.message.content.split(' ')[1].lower()
		try:
			domain = email.split('@')[1]
		except:
			await ctx.send(f"That wasn't a valid {uniName} email, please make sure to include {uniDomain}")
			return
		if(domain != uniDomain):
			await ctx.send(f"Invalid domain {domain}, please make sure it's an {uniDomain} email address")
			return
		randomString = GenerateRandomString()
		emailText = GenerateEmailText(gmailUser, email, randomString)
		await SendMail(gmailUser, gmailPw, email, emailText)
		emailHash = hashlib.sha256(email.encode('utf-8')).hexdigest()
		currentData[userId] = {"email": emailHash, "randomString": randomString}
		emailRequestsCount[userId] = count + 1
		await ctx.send(f"We have sent an email to {email} with your code. Please reply with !verify [code] to link your email to your discord account. By performing this command you agree to our GDPR policy. Please send !gdpr to read our policy.")
		email = ""
		return
	except Exception as e:
		await ctx.send(f"Something went wrong, please try again. If the problem persists, contact a system administrator.")
		return

@bot.command(name = 'verify', help = f"{bot.command_prefix}verify y0uRc0d3")
async def VerifCmd(ctx):
	try:
		commandStr = bot.command_prefix + ctx.command.name + ' '
		userId = ctx.author.id
		if(userId not in currentData.keys() and False):
			await ctx.send(f"You haven't yet requested a code. You can do so by messaging this bot !email [email] where [email] is a valid {uniName} email")
			return
		inputCode = ctx.message.content.split(commandStr)[1]
		trueCode = currentData[userId]["randomString"]
		if(inputCode == trueCode):
			try:
				await ctx.send("Thanks, that's the correct code - I'll let you know when I've successfully updated all my databases!")
				verified = await UpdateUserInfo(ctx, userId, currentData[userId]["email"])
				if(not verified):
					await ctx.send("You were not verified. If you've previously signed up and would like to link your email to a different account, please contact a member of committee")
					return
			except:
				await ctx.send(f"Something went wrong, please try again. If it continues to fail, please contact tau")
				return
			del currentData[userId]
			await ctx.send("Congratulations, you're verified. You should see your permissions adjusted to become correct soon")
		else:
			await ctx.send("Sorry, that's not right. Please check the code you entered")
		return
	except Exception as e:
		await ctx.send(f"Something went wrong, please try again. If the problem persists, contact a system administrator.")
		return

@bot.command(name = 'update', hidden = True)
async def UpdateCmd(ctx):
	try:
		userLevel = GetLevelFromUser(ctx.author.id)
		if(userLevel < membershipLevel.index('committee')):
			await ctx.send("Please ask a committee member to do this")
			return
		await UpdateMembershipInfo()
		await ctx.send("Updated membership info\n")
	except Exception as e:
		await ctx.send("Failed to update with error {e}")

@bot.command(name = 'gdpr', help = "Displays gdpr message")
async def GdprCmd(ctx):
	await ctx.send(gdprMessage)

@bot.command(name = 'exit', hidden = True)
async def ExitCmd(ctx):
	if(ctx.author.id != owner):
		await ctx.send("You do not have permission to use this command")
		return
	await ctx.send("Shutting down, goodbye! :wave:")
	bot.close()

@bot.command(name = 'remind', hidden = True)
async def RemindCmd(ctx):
	if(ctx.author.id != owner):
		await ctx.send("You do not have permission to use this command")
		return
	await MassMessageNonVerified()
	await ctx.send("Reminded users")

@bot.command(name = 'startvote', hidden = True)
async def StartVoteCmd(ctx):
	userLevel = GetLevelFromUser(ctx.author.id)
	if(userLevel < membershipLevel.index('committee')):
		await ctx.send("You do not have permission to use this command")
		return
	commandStr = bot.command_prefix + ctx.command.name + ' '
	input = ctx.message.content.split(commandStr)[1].split(' ')
	await CreateVote(ctx, input)

@bot.command(name = 'endvote', hidden = True)
async def EndVoteCmd(ctx):
	userLevel = GetLevelFromUser(ctx.author.id)
	if(userLevel < membershipLevel.index('committee')):
		await ctx.send("You do not have permission to use this command")
		return
	commandStr = bot.command_prefix + ctx.command.name + ' '
	input = ctx.message.content.split(commandStr)[1].split(' ')
	await EndVote(ctx, input)

@bot.command(name = 'votefor', help = f"{bot.command_prefix}votefor VoteTitle Candidate")
async def VoteForCmd(ctx):
	userLevel = GetLevelFromUser(ctx.author.id)
	if(userLevel < membershipLevel.index('member')):
		ctx.send("You must be a member to vote")
		return
	commandStr = bot.command_prefix + ctx.command.name + ' '
	input = ctx.message.content.split(commandStr)[1].split(' ')
	await Vote(ctx, input, ctx.author.id)

@bot.command(name = 'getvotes', help = f"Prints current votes")
async def VoteForCmd(ctx):
	try:
		userLevel = GetLevelFromUser(ctx.author.id)
		if(userLevel < membershipLevel.index('member')):
			await ctx.send("You must be a member to see votes")
			return
		await GetVotes(ctx)
	except Exception as e:
		await ctx.send("Something went wrong, please try again. If the problem persists, contact committee")

@bot.command(name = 'reset', hidden = True)
async def ResetCmd(ctx):
	try:
		userLevel = GetLevelFromUser(ctx.author.id)
		if(userLevel < membershipLevel.index('committee')):
			await ctx.send("You do not have permission to use this command")
			return
		commandStr = bot.command_prefix + ctx.command.name + ' '
		input = ctx.message.content.split(commandStr)[1]
		if(int(input) in emailRequestsCount.keys()):
			del emailRequestsCount[int(input)]
			await ctx.send(f"Reset user {input}'s email count")
		else:
			await ctx.send("Could not find this user in the email count list")
	except Exception as e:
		await ctx.send(f"Something went wrong, error: {e}")

@bot.command(name = 'ban', hidden = True)
async def BanCmd(ctx):
	try:
		userLevel = GetLevelFromUser(ctx.author.id)
		if(userLevel < membershipLevel.index('committee')):
			await ctx.send("You do not have permission to use this command")
			return
		commandStr = bot.command_prefix + ctx.command.name + ' '
		input = ctx.message.content.split(commandStr)[1]
		if(banUser(int(input))):
			await ctx.send(f"Banned user {input}")
		else:
			await ctx.send(f"Failed to ban user {input}")
	except Exception as e:
		await ctx.send(f"Something went wrong, error: {e}")

@bot.command(name = 'unban', hidden = True)
async def UnbanCmd(ctx):
	try:
		userLevel = GetLevelFromUser(ctx.author.id)
		if(userLevel < membershipLevel.index('committee')):
			await ctx.send("You do not have permission to use this command")
			return
		commandStr = bot.command_prefix + ctx.command.name + ' '
		input = ctx.message.content.split(commandStr)[1]
		if(unbanUser(int(input))):
			await ctx.send(f"Unbanned user {input}")
		else:
			await ctx.send(f"Failed to unban user {input}")
	except Exception as e:
		await ctx.send(f"Something went wrong, error: {e}")

bot.run(discordToken)


