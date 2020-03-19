import discord
from discord.ext import commands
import hashlib
from enum import Enum
import sys
import asyncio
import time
import logging
import utils.mail 
import utils.guild 
import utils.voting
import utils.config
import argparse

# Arguments:
# -c PATH_TO_CONFIG.json 
# -d (changes the command character to *)
parser = argparse.ArgumentParser()
parser.add_argument("-c", "--config", default="config.json")
parser.add_argument("-d", "--debug", default = False, action='store_true')
args = parser.parse_args()

# Create a log file
logging.basicConfig(filename='log.txt', level = logging.INFO)

# Create the local database
db = { \
    'user_info' : {},
    'verif_temp' : {},
    'req_count' : {},
    'votes' : {}
    }

# Load the config
try:
    cfg = utils.config.LoadConfig(args.config)
except Exception as e:
    logging.warning(f"Failed to load config with reason {e}")
    sys.exit(-1)

# Load the user database from the online backup
try:
    db['user_info'] = utils.config.LoadUsers(cfg)
    logging.info(f"Loaded {len(db['user_info'])} users.")
except Exception as e:
    logging.warning(f"Failed to load users, error\n{e}")

# Spawn the bot
bot = commands.Bot(command_prefix = '*' if args.debug else '!')

# When a member joins, let them know that they need to verify
@bot.event
async def on_member_join(member):
    # Attempt to give them guest if guest exists
    if 'guest' in cfg['discord']['role_ids'].keys():
        guestID = cfg['discord']['role_ids']['guest']
        guild = bot.get_guild(cfg['discord']['guild'])
        userRoleIds = [role.id for role in member.roles]
        guildRoles = {role.id : role for role in guild.roles}
        try: 
            if(guestID not in userRoleIds):
                logging.info(f"Attempting to apply role guest")
                await member.add_roles(guildRoles[guestID])
        except Exception as e:
            logging.warning(f"Failed to add guest role for {member.name} for reason {e}")
    
    # Send the welcome message
    await member.send_message(f"""Welcome to the {cfg['uni']['society']} discord server! If you are a student, please verify this by sending:
    `!email myemail@{cfg['uni']['domain']}`.
    You should then receive a code via email, which you can use to verify your account by sending:
    `!verify [code]`.
    This will give you access to student only areas as well as any perks given by your membership status.
    GDPR information: 
    {cfg['gdpr']}""")
    logging.info(f"Sent welcome message to user {member.name}\n")

# Log that the bot logs in successfully
@bot.event
async def on_ready():
    logging.info('Logged in as')
    logging.info(bot.user.name)
    logging.info(bot.user.id)
    logging.info('------')

# Only respond to dm messages which weren't from the bot
@bot.event
async def on_message(msg):
    if type(msg.channel) is discord.DMChannel and msg.author != bot.user:
        await bot.process_commands(msg)

# Syntax of input should be !email anemail@domain
# Rejects emails which don't end in @ domain
# Will send a code to any email which matches the domain
# Maximum number of requests is 3 before it needs resetting by committee
# This is to prevent spam
@bot.command(name = 'email', help = f"{bot.command_prefix}email youremail@{cfg['uni']['domain']}")
async def EmailCmd(ctx):
    try:
        # Check user is in the society server
        guild = bot.get_guild(cfg['discord']['guild'])
        userId = ctx.author.id
        if(userId not in [user.id for user in guild.members]):
            await ctx.send(f"You are not in the {cfg['uni']['society']} server, please join before trying to verify")
            return

        # Check user doesn't have previous requests
        count = 0 if userId not in db['req_count'].keys() else db['req_count'][userId]
        if count > 3:
            await ctx.send(f"You've made too many requests, please speak to a committee member to sort this out")
            return
        elif count > 0:
            await ctx.send(f"I'm sending another email, but this will invalidate your previous code. You have used {count}/3 requests.")
        
        # Get their email address and check it has the correct domain
        email = ctx.message.content.split(' ')[1].lower()
        try:
            domain = email.split('@')[1]
        except:
            await ctx.send(f"That wasn't a valid {cfg['uni']['name']} email, please make sure to include {cfg['uni']['domain']}")
            return
        if(domain != cfg['uni']['domain']):
            await ctx.send(f"Invalid domain {domain}, please make sure it's an {cfg['uni']['domain']} email address")
            return

        # Generate their codee, insert it into the email and send it
        randomString = utils.mail.GenerateRandomString()
        emailText = utils.mail.GenerateEmailText(cfg['gmail']['user'], email, randomString, cfg)
        await utils.mail.SendMail(cfg['gmail']['user'], cfg['gmail']['pw'], email, emailText)

        # Hash their email and store it into the database
        emailHash = hashlib.sha256(email.encode('utf-8')).hexdigest()
        db['verif_temp'][userId] = {"email": emailHash, "randomString": randomString}
        db['req_count'][userId] = count + 1

        # Let them know it's sent!
        await ctx.send(f"We have sent an email to {email} with your code. Please reply with !verify [code] to link your email to your discord account. By performing this command you agree to our GDPR policy. Please send !gdpr to read our policy.")
        
        # Clear their email so it's not stored any more
        email = ""
        return
    except Exception as e:
        # If something goes wrong here, let them know. The error will appear in the log.
        await ctx.send(f"Something went wrong, please try again. If the problem persists, contact a system administrator.")
        logging.error(f"Failed to send email with reason {e}.")
        return

# Users with codes send this command to complete verification
# command format: 
# !verify thec0d3
@bot.command(name = 'verify', help = f"{bot.command_prefix}verify y0uRc0d3")
async def VerifCmd(ctx):
    try:
        commandStr = bot.command_prefix + ctx.command.name + ' '

        # Check the user has asked for an email before this
        userId = ctx.author.id
        if(userId not in db['verif_temp'].keys() and False):
            await ctx.send(f"You haven't yet requested a code. You can do so by messaging this bot !email [email] where [email] is a valid {cfg['uni']['name']} email")
            return
        
        # Get the code and check that it matches the correct code
        inputCode = ctx.message.content.split(commandStr)[1]
        trueCode = db['verif_temp'][userId]["randomString"]
        if(inputCode == trueCode):
            try:
                # Send them confirmation it was correct so they don't spam
                await ctx.send("Thanks, that's the correct code - I'll let you know when I've successfully updated all my databases!")
                # Try to verify them - this will fail in cases like them being banned 
                # or having another account already linked to this email
                verified = await utils.guild.UpdateUserInfo(ctx, userId, db['verif_temp'][userId]["email"], bot, db, cfg)
                if(not verified):
                    await ctx.send("You were not verified. If you've previously signed up and would like to link your email to a different account, please contact a member of committee")
                    return
            except Exception as e:
                # something went wrong, so let them know and log it
                await ctx.send(f"Something went wrong, please try again. If it continues to fail, please contact a member of committee.")
                logging.error(f"Failed to verify user {ctx.author.name} for reason {e}.")
                return
            
            # Remove them from the db and verify them
            del db['verif_temp'][userId]
            await ctx.send("Congratulations, you're verified. You should see your permissions adjusted to become correct soon.")
            await utils.guild.BackupMembershipInfo(bot, db, cfg)
        else: # incorrect code
            await ctx.send("Sorry, that's not right. Please check the code you entered.")
        return
    except Exception as e:
        await ctx.send(f"Something went wrong, please try again. If the problem persists, contact a system administrator.")
        logging.error(f"Failed to verify email with reason {e}.")
        return

# This updates all users n the server and backs up the database
# Command can take a while to run, especailly at first
# because of rate limiting. 
@bot.command(name = 'update', hidden = True)
async def UpdateCmd(ctx):
    try:
        # Only do it for committee members
        userLevel = utils.guild.GetLevelFromUser(ctx.author.id, db)
        if(ctx.author.id != cfg['owner'] and userLevel < utils.guild.GetLevelFromString('committee', cfg)):
            await ctx.send("Please ask a committee member to do this")
            return
        await utils.guild.UpdateMembershipInfo(bot, db, cfg)
        await ctx.send("Updated membership info\n")
    except Exception as e:
        await ctx.send(f"Failed to update with error {e}")

# This backs up the current database to the google sheet 
# it does not change current roles, so is quicker 
@bot.command(name = 'backup', hidden = True)
async def BackupCmd(ctx):
    try:
        # Only do this for committee
        userLevel = utils.guild.GetLevelFromUser(ctx.author.id, db)
        if(ctx.author.id != cfg['owner'] and userLevel < utils.guild.GetLevelFromString('committee', cfg)):
            await ctx.send("Please ask a committee member to do this")
            return
        await utils.guild.BackupMembershipInfo(bot, db, cfg)
        await ctx.send("Backed-up membership info\n")
    except Exception as e:
        await ctx.send(f"Failed to back-up with error {e}")

# this sends the gdpr notice from the config
@bot.command(name = 'gdpr', help = "Displays gdpr message")
async def GdprCmd(ctx):
    await ctx.send(cfg['gdpr'])

# This causes the bot to shut down
@bot.command(name = 'exit', hidden = True)
async def ExitCmd(ctx):
    if(ctx.author.id != cfg['owner']):
        await ctx.send("You do not have permission to use this command")
        return
    await ctx.send("Shutting down, goodbye! :wave:")
    await bot.close()

# This sends a message to everyone in the server who isn't verified
# telling them to verify.
# Use with caution, it'll take a long time if there are many non verified
# people. 
# Reps of other orgs will get one. Probably best to only do once.
@bot.command(name = 'remind', hidden = True)
async def RemindCmd(ctx):
    userLevel = utils.guild.GetLevelFromUser(ctx.author.id, db)
    if(userLevel != utils.guild.GetLevelFromString("committee", cfg)):
        await ctx.send("You do not have permission to use this command")
        return
    await utils.guild.MassMessageNonVerified(ctx, bot, db, cfg)
    await ctx.send("Reminded users")

# This starts a vote
# Command syntax:
# !startvote name = [role_name], type = [fptp/ranked], \
# roles = [role1 : role2 : ... : roleN], channel = [channel_id], \
# candidates = [candidate1 : candidate2 : ... : candidate3]
#
# Note it should be all on one line, only split here to make it easier to read
# Replace [role_name] with, e.g. president
# fptp runs a first regular fptp vote, ranked runs an instant runoff vote system
# if the role ids 42227 and 55333 could vote, then roles would be
# 42227 : 55333
# (optional) Channel id only allows people to vote if they are also in a chosen voice chat
# Candidate lists are made similarly to the role list
# Only committee can do this
@bot.command(name = 'startvote', hidden = True)
async def StartVoteCmd(ctx):
    try:
        userLevel = utils.guild.GetLevelFromUser(ctx.author.id, db)
        if(userLevel < utils.guild.GetLevelFromString('committee', cfg)):
            await ctx.send("You do not have permission to use this command")
            return
        commandStr = bot.command_prefix + ctx.command.name + ' '
        input = ctx.message.content.split(commandStr)[1]
        await utils.voting.CreateVote(ctx, input, db)
    except Exception as e:
        logging.error(f"Failed to start vote for reason {e}.")
        await ctx.send(f"Error: {e}")

# This ends the vote and sends the results (destroying them in the process)
# Only committee can do this.
# Syntax is:
# !endvote [votename]
@bot.command(name = 'endvote', hidden = True)
async def EndVoteCmd(ctx):
    try:
        userLevel = utils.guild.GetLevelFromUser(ctx.author.id, db)
        if(userLevel < utils.guild.GetLevelFromString('committee', cfg)):
            await ctx.send("You do not have permission to use this command")
            return
        commandStr = bot.command_prefix + ctx.command.name + ' '
        input = ctx.message.content.split(commandStr)[1]
        await utils.voting.EndVote(ctx, input, bot, db, cfg)
    except Exception as e:
        logging.error(f"Failed to end vote for reason {e}.")
        await ctx.send(f"Error: {e}")

# This destroys the vote results and removes it from the list of votes
# Only committee can do this.
# Syntax is:
# !deletevote [votename]
@bot.command(name = 'deletevote', hidden = True)
async def DeleteVoteCmd(ctx):
    try:
        userLevel = utils.guild.GetLevelFromUser(ctx.author.id, db)
        if(userLevel < utils.guild.GetLevelFromString('committee', cfg)):
            await ctx.send("You do not have permission to use this command")
            return
        commandStr = bot.command_prefix + ctx.command.name + ' '
        input = ctx.message.content.split(commandStr)[1]
        await utils.voting.DeleteVote(ctx, input, bot, db, cfg)
    except Exception as e:
        logging.error(f"Failed to delete vote for reason {e}.")
        await ctx.send(f"Error: {e}")

# This allows users to vote for someone. 
# Command syntax for fptp:
# !votefor President, Bernie
# Command syntax for ranked choice:
# !votefor President, Bernie, Ron
@bot.command(name = 'votefor', help = f"{bot.command_prefix}votefor VoteTitle Candidate")
async def VoteForCmd(ctx):
    try:
        userLevel = utils.guild.GetLevelFromUser(ctx.author.id, db)
        if(userLevel < utils.guild.GetLevelFromString('member', cfg)):
            await ctx.send("You must be a member to vote")
            return
        commandStr = bot.command_prefix + ctx.command.name + ' '
        input = ctx.message.content.split(commandStr)[1]
        await utils.voting.Vote(ctx, input, ctx.author.id, bot, db, cfg)
    except Exception as e:
        logging.error(f"command {commandStr} failed to vote for reason {e}.")
        await ctx.send(f"Vote failed. Please try again. If it says your vote has already been counted then you're probably fine.")

# This shows a list of all the active votes and the candidates
@bot.command(name = 'getvotes', help = f"Prints current votes")
async def GetVotesCmd(ctx):
    try:
        userLevel = utils.guild.GetLevelFromUser(ctx.author.id, db)
        if(userLevel < utils.guild.GetLevelFromString('member', cfg)):
            await ctx.send("You must be a member to see votes")
            return
        await utils.voting.GetVotes(ctx, db)
    except Exception as e:
        logging.error(f"Failed to get votes for reason {e}.")
        await ctx.send("Something went wrong, please try again. If the problem persists, contact committee")

# This resets the email count on a user
# Command syntax:
# !reset [user_id] 
# e.g. !reset 983492389198
@bot.command(name = 'reset', hidden = True)
async def ResetCmd(ctx):
    try:
        userLevel = utils.guild.GetLevelFromUser(ctx.author.id, db)
        if(userLevel < utils.guild.GetLevelFromString('committee', cfg)):
            await ctx.send("You do not have permission to use this command")
            return
        commandStr = bot.command_prefix + ctx.command.name + ' '
        input = ctx.message.content.split(commandStr)[1]
        if(int(input) in db['req_count'].keys()):
            del db['req_count'][int(input)]
            await ctx.send(f"Reset user {input}'s email count")
        else:
            await ctx.send("Could not find this user in the email count list")
    except Exception as e:
        await ctx.send(f"Something went wrong, error: {e}")

# To ban a user, send 
# !ban [user_id]
# e.g. !ban 09821020190
# This will prevent them from reverifying and remove their student role
@bot.command(name = 'ban', hidden = True)
async def BanCmd(ctx):
    try:
        userLevel = utils.guild.GetLevelFromUser(ctx.author.id, db)
        if(userLevel < utils.guild.GetLevelFromString('committee', cfg)):
            await ctx.send("You do not have permission to use this command")
            return
        commandStr = bot.command_prefix + ctx.command.name + ' '
        input = ctx.message.content.split(commandStr)[1]
        if(utils.guild.banUser(int(input), db)):
            await ctx.send(f"Banned user {input}")
        else:
            await ctx.send(f"Failed to ban user {input}")
    except Exception as e:
        await ctx.send(f"Something went wrong, error: {e}")

# To unban a user, send 
# !unban [user_id]
# e.g. !unban 09821020190

@bot.command(name = 'unban', hidden = True)
async def UnbanCmd(ctx):
    try:
        userLevel = utils.guild.GetLevelFromUser(ctx.author.id, db)
        if(userLevel < utils.guild.GetLevelFromString('committee', cfg)):
            await ctx.send("You do not have permission to use this command")
            return
        commandStr = bot.command_prefix + ctx.command.name + ' '
        input = ctx.message.content.split(commandStr)[1]
        if(utils.guild.unbanUser(int(input), db)):
            await ctx.send(f"Unbanned user {input}")
        else:
            await ctx.send(f"Failed to unban user {input}")
    except Exception as e:
        await ctx.send(f"Something went wrong, error: {e}")

bot.loop.create_task(utils.guild.regular_backup_task(bot, db, cfg))

# Start the bot
bot.run(cfg['discord']['token'])


