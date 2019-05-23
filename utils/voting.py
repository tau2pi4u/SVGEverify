async def CreateVote(ctx, msg, db):
    try:
        vote_opts=msg.split(',')
        vote_cfg = {}
        for opt in vote_opts:
            opt_name, opt_val = opt.split('=')
            opt_name, opt_val = opt_name.strip(), opt_val.strip()
            vote_cfg[opt_name] = opt_val
        assert(all(key in vote_cfg.keys() for key in ('name', 'candidates', 'type', 'roles'))), "CreateVote: Missing a required option"
        assert(vote_cfg['type'] in ['fptp', 'ranked'])
        if ':' not in vote_cfg['candidates']:
            await ctx.send("No separator found in candidates")
            return
        vote_cfg['candidates'] = [c.strip() for c in vote_cfg['candidates'].split(':')]
        vote_cfg['candidate_map'] = {c.lower() : c for c in vote_cfg['candidates']}
        if ':' in vote_cfg['roles']:
            vote_cfg['roles'] = [r.strip() for r in vote_cfg['roles'].split(':')]
        else:
            vote_cfg['roles'] = [vote_cfg['roles'].strip()]
        if vote_cfg['type'] == 'fptp':
            vote_cfg['voter_ids'] = []
            vote_cfg['count'] = {}
            for candidate in vote_cfg['candidates']:
                vote_cfg['count'][candidate] = 0
        else:
            vote_cfg['voter_ids'] = []
            vote_cfg['voter_rankings'] = []
        if 'channel' in vote_cfg.keys():
            vote_cfg['channel'] = int(vote_cfg['channel'])
        db['votes'][vote_cfg['name'].lower()] = vote_cfg
        await ctx.send(f"Created vote {vote_cfg['name']} with candidates {vote_cfg['candidates']}")
    except Exception as e:
        await ctx.send("Failed to create vote, exception: {e}")
    

async def Vote(ctx, msg, id, bot, db, cfg):
    from random import shuffle
    try:
        vote_title = msg.split(',')[0]
        vote_candidates = msg.split(vote_title + ',')[1].strip()
        vote_candidates = [vote_candidates.strip().lower()] if ',' not in vote_candidates else [candidate.strip().lower() for candidate in vote_candidates.split(',')]
        vote_title = vote_title.lower().strip()
        if(vote_title not in db['votes'].keys()):
            await ctx.send(f"{vote_title} is not a valid vote title")
            return
        vote_type = db['votes'][vote_title]['type']
        if('channel' in db['votes'][vote_title].keys()):
            channel = bot.get_channel(db['votes'][vote_title]["channel"])
            valid_voters = [member.id for member in channel.members]
            if(id not in valid_voters):
                await ctx.send("You're not attending the relevant meeting")
                return
        if('roles' in db['votes'][vote_title].keys()):
            guild = bot.get_guild(cfg['discord']['guild'])
            req_roles = [int(role) for role in db['votes'][vote_title]['roles']]
            voter_roles = [role.id for role in guild.roles if id in [user.id for user in role.members]]
            if(not all(req_role in voter_roles for req_role in req_roles)):
                await ctx.send("You are missing a required role.")
                return
        if vote_type == 'fptp':
            if id in db['votes'][vote_title]['voter_ids']:
                await ctx.send(f"You have already participated in this vote.")
                return
            if len(vote_candidates) != 1:
                await ctx.send(f"Please vote for exactly one candidate")
                return
            vote_candidates = vote_candidates[0]
            if vote_candidates not in db['votes'][vote_title]['candidate_map']:
                await ctx.send(f"{vote_candidates} not found in candidate list: {db['votes'][vote_title]['candidates']}\nNote: This is not case sensitive.")
                return
            db['votes'][vote_title]['count'][db['votes'][vote_title]['candidate_map'][vote_candidates]] += 1
            db['votes'][vote_title]['voter_ids'].append(id)
            await ctx.send(f"You successfully voted for: {vote_candidates} in the vote: {vote_title}.")
        else:
            if id in db['votes'][vote_title]['voter_ids']:
                await ctx.send(f"You have already participated in this vote.")
                return
            for candidate in vote_candidates:
                if candidate not in db['votes'][vote_title]['candidate_map']:
                    await ctx.send(f"{vote_candidates} not found in candidate list: {db['votes'][vote_title]['candidates']}\nNote: This is not case sensitive.")
                    return
            db['votes'][vote_title]['voter_rankings'].append(vote_candidates)
            db['votes'][vote_title]['voter_ids'].append(id) 
            shuffle(db['votes'][vote_title]['voter_ids'])
            await ctx.send(f"You successfully voted for: {vote_candidates} in the vote: {db['votes'][vote_title]['name']}.")
    except Exception as e:
        await ctx.send(f"Something went wrong, please try again. Error: {e}")

async def EndVote(ctx, msg, bot, db, cfg):
    import operator
    try:
        vote_title = msg.strip().lower()
        if vote_title not in db['votes'].keys():
            await ctx.send(f"{vote_title} not a valid vote")
        vote_cfg = db['votes'][vote_title]
        vote_type = vote_cfg['type']
        if vote_type == 'fptp':
            result = dict(sorted(vote_cfg['count'].items(), key=operator.itemgetter(1), reverse=True))
            await ctx.send(f"Results for vote: {vote_cfg['name']}\n{result}")
            del db['votes'][vote_title]
            return
        else:
            rankings = vote_cfg['voter_rankings']
            # fix to be in line with candidate name in dictionary
            for i, voter_rank in enumerate(rankings):
                rankings[i] = [vote_cfg['candidate_map'][c.lower()] for c in rankings[i]]			
            candidate_list = vote_cfg['candidates']
            while len(candidate_list) > 1:
                round_votes = {candidate: 0 for candidate in candidate_list}
                for voter in rankings:
                    if len(voter) == 0:
                        continue
                    first_choice = voter[0]
                    round_votes[first_choice] += 1
                round_result = dict(sorted(round_votes.items(), key=operator.itemgetter(1), reverse=True))
                total_votes = sum(round_votes.values())
                top_perc = 100.0 * list(round_result.values())[0] / total_votes
                if(top_perc > 50.0):
                    winner = list(round_result.keys())[0]
                    await ctx.send(f"Vote was won by {winner} with {top_perc:.2f}% of the vote.\nFinal result: {round_result}")
                    del db['votes'][vote_title]
                    return
                else:
                    if len(candidate_list) == 2:
                        break
                    last_place = list(round_result.keys())[-1]
                    candidate_list.remove(last_place)
                    for i in range(len(rankings)):
                        if last_place in rankings[i]:
                            rankings[i].remove(last_place)
                    await ctx.send(f"Round results: {round_result}\nRemoved candidate: {last_place}")
            await ctx.send(f"Exited without a majority. Remaining vote list: {rankings}")
            del db['votes'][vote_title]
    except Exception as e:
        await ctx.send(f"Something went wrong, please try again. Error: {e}")

async def GetVotes(ctx, db):
    if not db['votes']:
        await ctx.send("No active votes.")
    else:
        res = "Currently active votes:\n"
        for vote in db['votes'].values():
            candidates = ', '.join([candidate for candidate in vote["candidates"]])
            res += f"Vote: `{vote['name']}`\nCandidates: `{candidates}`\nType: `{vote['type']}`\n\n"
        await ctx.send(res)