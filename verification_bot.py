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

parser = argparse.ArgumentParser()
parser.add_argument("-c", "--config", default="config.cfg")
args = parser.parse_args()

logging.basicConfig(filename='log.txt', level = logging.INFO)

#databases
db = { \
    'user_info' : {},
    'verif_temp' : {},
    'req_count' : {},
    'votes' : {}
    }

try:
    cfg = utils.config.LoadConfig(args.config)
except Exception as e:
    logging.warning(f"Failed to load config with reason {e}")
    sys.exit(1)

try:
    db['user_info'] = utils.config.LoadUsers(cfg)
    logging.info(f"Loaded {len(db['user_info'])} users.")
except Exception as e:
    logging.warning(f"Failed to load users, error\n{e}")

bot = commands.Bot(command_prefix = '*')

@bot.event
async def on_member_join(member):
    guestID = cfg['discord']['role_ids']["guest"]
    guild = bot.get_guild(cfg['discord']['guild'])
    userRoleIds = [role.id for role in member.roles]
    guildRoles = {role.id : role for role in guild.roles}
    try: 
        if(guestID not in userRoleIds):
            logging.info(f"Attempting to apply role guest")
            await member.add_roles(guildRoles[guestID])
    except Exception as e:
        logging.warning(f"Failed to add guest role for {member.name} for reason {e}")
    await member.send_message(f"""Welcome to the {cfg['uni']['society']} discord server! If you are a student, please verify this by sending:
    `!email myemail@{cfg['uni']['domain']}`.
    You should then receive a code via email, which you can use to verify your account by sending:
    `!verify [code]`.
    This will give you access to student only areas as well as any perks given by your membership status.
    GDPR information: 
    %s""" % (cfg['gdpr']))
    logging.info(f"Sent welcome message to user {member.name}\n")

@bot.event
async def on_ready():
    logging.info('Logged in as')
    logging.info(bot.user.name)
    logging.info(bot.user.id)
    logging.info('------')

@bot.event
async def on_message(msg):
    if type(msg.channel) is discord.DMChannel and msg.author != bot.user:
        await bot.process_commands(msg)

@bot.command(name = 'email', help = f"{bot.command_prefix}email youremail@{cfg['uni']['domain']}")
async def EmailCmd(ctx):
    
    try:
        guild = bot.get_guild(cfg['discord']['guild'])
        userId = ctx.author.id
        if(userId not in [user.id for user in guild.members]):
            await ctx.send(f"You are not in the {cfg['uni']['society']} server, please join before trying to verify")
            return
        count = 0 if userId not in db['req_count'].keys() else db['req_count'][userId]
        if count > 3:
            await ctx.send(f"You've made too many requests, please speak to a committee member to sort this out")
            return
        email = ctx.message.content.split(' ')[1].lower()
        try:
            domain = email.split('@')[1]
        except:
            await ctx.send(f"That wasn't a valid {cfg['uni']['name']} email, please make sure to include {cfg['uni']['domain']}")
            return
        if(domain != cfg['uni']['domain']):
            await ctx.send(f"Invalid domain {domain}, please make sure it's an {cfg['uni']['domain']} email address")
            return
        randomString = utils.mail.GenerateRandomString()
        emailText = utils.mail.GenerateEmailText(cfg['gmail']['user'], email, randomString, cfg)
        await utils.mail.SendMail(cfg['gmail']['user'], cfg['gmail']['pw'], email, emailText)
        emailHash = hashlib.sha256(email.encode('utf-8')).hexdigest()
        db['verif_temp'][userId] = {"email": emailHash, "randomString": randomString}
        db['req_count'][userId] = count + 1
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
        if(userId not in db['verif_temp'].keys() and False):
            await ctx.send(f"You haven't yet requested a code. You can do so by messaging this bot !email [email] where [email] is a valid {cfg['uni']['name']} email")
            return
        inputCode = ctx.message.content.split(commandStr)[1]
        trueCode = db['verif_temp'][userId]["randomString"]
        if(inputCode == trueCode):
            try:
                await ctx.send("Thanks, that's the correct code - I'll let you know when I've successfully updated all my databases!")
                verified = await UpdateUserInfo(ctx, userId, db['verif_temp'][userId]["email"])
                if(not verified):
                    await ctx.send("You were not verified. If you've previously signed up and would like to link your email to a different account, please contact a member of committee")
                    return
            except:
                await ctx.send(f"Something went wrong, please try again. If it continues to fail, please contact a member of committee.")
                return
            del db['verif_temp'][userId]
            await ctx.send("Congratulations, you're verified. You should see your permissions adjusted to become correct soon.")
        else:
            await ctx.send("Sorry, that's not right. Please check the code you entered.")
        return
    except Exception as e:
        await ctx.send(f"Something went wrong, please try again. If the problem persists, contact a system administrator.")
        return

@bot.command(name = 'update', hidden = True)
async def UpdateCmd(ctx):
    try:
        userLevel = utils.guild.GetLevelFromUser(ctx.author.id, db)
        if(userLevel < utils.guild.GetLevelFromString('committee')):
            await ctx.send("Please ask a committee member to do this")
            return
        await utils.guild.UpdateMembershipInfo(bot, db, cfg)
        await ctx.send("Updated membership info\n")
    except Exception as e:
        await ctx.send("Failed to update with error {e}")

@bot.command(name = 'gdpr', help = "Displays gdpr message")
async def GdprCmd(ctx):
    await ctx.send(cfg['gdpr'])

@bot.command(name = 'exit', hidden = True)
async def ExitCmd(ctx):
    if(ctx.author.id != cfg['owner']):
        await ctx.send("You do not have permission to use this command")
        return
    await ctx.send("Shutting down, goodbye! :wave:")
    bot.close()

@bot.command(name = 'remind', hidden = True)
async def RemindCmd(ctx):
    userLevel = utils.guild.GetLevelFromUser(ctx.author.id, db)
    if(userLevel != utils.guild.GetLevelFromString("committee")):
        await ctx.send("You do not have permission to use this command")
        return
    await utils.guild.MassMessageNonVerified(ctx, bot, db, cfg)
    await ctx.send("Reminded users")

@bot.command(name = 'startvote', hidden = True)
async def StartVoteCmd(ctx):
    userLevel = utils.guild.GetLevelFromUser(ctx.author.id, db)
    if(userLevel < utils.guild.GetLevelFromString('committee')):
        await ctx.send("You do not have permission to use this command")
        return
    commandStr = bot.command_prefix + ctx.command.name + ' '
    input = ctx.message.content.split(commandStr)[1]
    await utils.voting.CreateVote(ctx, input, db)

@bot.command(name = 'endvote', hidden = True)
async def EndVoteCmd(ctx):
    userLevel = utils.guild.GetLevelFromUser(ctx.author.id, db)
    if(userLevel < utils.guild.GetLevelFromString('committee')):
        await ctx.send("You do not have permission to use this command")
        return
    commandStr = bot.command_prefix + ctx.command.name + ' '
    input = ctx.message.content.split(commandStr)[1]
    await utils.voting.EndVote(ctx, input, bot, db, cfg)

@bot.command(name = 'votefor', help = f"{bot.command_prefix}votefor VoteTitle Candidate")
async def VoteForCmd(ctx):
    userLevel = utils.guild.GetLevelFromUser(ctx.author.id, db)
    if(userLevel < utils.guild.GetLevelFromString('member')):
        await ctx.send("You must be a member to vote")
        return
    commandStr = bot.command_prefix + ctx.command.name + ' '
    input = ctx.message.content.split(commandStr)[1]
    await utils.voting.Vote(ctx, input, ctx.author.id, bot, db, cfg)

@bot.command(name = 'getvotes', help = f"Prints current votes")
async def GetVotesCmd(ctx):
    try:
        userLevel = utils.guild.GetLevelFromUser(ctx.author.id, db)
        if(userLevel < utils.guild.GetLevelFromString('member')):
            await ctx.send("You must be a member to see votes")
            return
        await utils.voting.GetVotes(ctx, db)
    except Exception as e:
        await ctx.send("Something went wrong, please try again. If the problem persists, contact committee")

@bot.command(name = 'reset', hidden = True)
async def ResetCmd(ctx):
    try:
        userLevel = utils.guild.GetLevelFromUser(ctx.author.id, db)
        if(userLevel < utils.guild.GetLevelFromString('committee')):
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

@bot.command(name = 'ban', hidden = True)
async def BanCmd(ctx):
    try:
        userLevel = utils.guild.GetLevelFromUser(ctx.author.id, db)
        if(userLevel < utils.guild.GetLevelFromString('committee')):
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

@bot.command(name = 'unban', hidden = True)
async def UnbanCmd(ctx):
    try:
        userLevel = utils.guild.GetLevelFromUser(ctx.author.id, db)
        if(userLevel < utils.guild.GetLevelFromString('committee')):
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

bot.run(cfg['discord']['token'])


