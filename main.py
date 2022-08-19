import discord
import os
import math
import mysql.connector
import pandas as pd
import numpy as np

mydb = mysql.connector.connect(
    host = "localhost",
    user = "racquetbot",
    password = "racquet",
    database = "racquetbot"
)

mydb.autocommit = True

# Initiate discord client
intents = discord.Intents.all()
client = discord.Client(intents=intents)


async def get_k_value(elo, ngames):
    # K value gradation based on elo
    k_valuea, k_valueb, k_valuec, k_valued = [50, 32, 24, 16]

    # elo thresholds
    k_thresholda, k_thresholdb = [2400, 2100]

    # number of games to get noob K value
    noob_game_count = 5

    k = 32

    # check what elo range player 1 is in
    if elo >= k_thresholda:
        k = k_valued

    if k_thresholdb <= elo < k_thresholda:
        k = k_valuec

    if elo < k_thresholdb:
        k = k_valueb

    # If the player has less than x number of noob game count, make them earn more
    if ngames <= noob_game_count:
        k = k_valuea

    return k


# Function to calculate Elo rating
# K is a constant.
# d determines whether
# Player A wins or Player B.
async def EloRating(winner, loser, season, winner_score, loser_score, update=None):
    cursor = mydb.cursor()
    # Get elo for both players
    cursor.execute('select elo from `' + season + '` where discord_id=%s', (winner,))
    winner_elo = cursor.fetchone()[0]
    cursor.execute('select elo from `' + season + '` where discord_id=%s', (loser,))
    loser_elo = cursor.fetchone()[0]
    # Get both players number of games played
    cursor.execute('select count(*) from game_history where (player1_id=%s or player2_id=%s) and season=%s and invalid=0', (winner, winner, season,))
    winner_games = cursor.fetchone()[0]
    cursor.execute('select count(*) from game_history where (player1_id=%s or player2_id=%s) and season=%s and invalid=0', (loser, loser, season,))
    loser_games = cursor.fetchone()[0]
    # Set k values ### Will be based off # of games
    winner_k = await get_k_value(winner_elo, winner_games)
    loser_k = await get_k_value(loser_elo, loser_games)

    # Calculate probability
    winner_expected_outcome = winner_elo / (winner_elo + loser_elo)
    loser_expected_outcome = loser_elo / (winner_elo + loser_elo)
    # Calculate post game deltas and elos
    winner_delta = math.ceil(winner_k * (1 - winner_expected_outcome))
    winner_new_elo = winner_elo + winner_delta

    loser_delta = math.ceil(loser_k * (0 - loser_expected_outcome))
    if loser_score == 0:
        loser_delta = loser_delta * 3
    loser_new_elo = loser_elo + loser_delta

    # Insert game into database
    cursor.execute('update `' + season + '` set elo=%s, wins=wins+1 where discord_id=%s', (winner_new_elo, winner,))
    cursor.execute('update `' + season + '` set elo=%s, losses=losses+1 where discord_id=%s', (loser_new_elo, loser,))

    winner_name = await get_player_name(winner)
    loser_name = await get_player_name(loser)
    if update is not None:
        cursor.execute('update game_history set player1_id=%s, player1_name=%s, player1_elo=%s, player1_elo_delta=%s, player1_elo_after=%s, player2_id=%s, player2_name=%s, player2_elo=%s, player2_elo_delta=%s, player2_elo_after=%s, winner_id=%s, winner_name=%s, player1_score=%s, player2_score=%s where gameid=%s',
                       (winner, winner_name, winner_elo, winner_delta, winner_new_elo, loser, loser_name, loser_elo, loser_delta, loser_new_elo,
                         winner, winner_name, winner_score, loser_score, update,))
        game_id = update
    else:
        cursor.execute('insert into game_history values (NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), %s, %s, %s, %s, %s, 0)',
                   (winner, winner_name, winner_elo, winner_delta, winner_new_elo, loser, loser_name, loser_elo, loser_delta, loser_new_elo,
                    winner, winner_name, winner_score, loser_score, season,))
        game_id = cursor.lastrowid
    cursor.close()
    #embed = await output_game(game_id, winner, winner_elo, winner_delta, winner_new_elo, loser, loser_elo, loser_delta, loser_new_elo, winner_score, loser_score, season)
    embed = await output_game(game_id)
    return embed


async def output_game(game_id):
    cursor = mydb.cursor()
    cursor.execute('select * from game_history where gameid=%s', (game_id,))
    result = cursor.fetchone()
    if result is None:
         return None
    print(result)
    gameid, player1, player1_name, player1_elo, player1_elo_delta, player1_elo_after, player2, player2_name, player2_elo, player2_elo_delta, player2_elo_after, \
        date, winner, winner_name, player1_score, player2_score, season, invalid = result
    embed = discord.Embed(title=f"Racquetball game id #{game_id}",
                          description=f'Score: <@{player1}> {player1_score}-{player2_score} <@{player2}>',
                          color=0x70ac64)
    if season != await get_current_unranked_season():
        player1_rank = await get_player_rank(player1, season)
        player2_rank = await get_player_rank(player2, season)
        embed.add_field(name=f"__Elo Changes__", value=f"<@{player1}> {player1_elo} --> {player1_elo_after} **(+{player1_elo_delta})** | #{player1_rank}\n<@{player2}> {player2_elo} --> {player2_elo_after} **({player2_elo_delta})** | #{player2_rank}", inline=False)
        if invalid == 1:
           embed.set_footer(text=':x: Game invalid :x:')
    cursor.close()
    return embed

'''
async def output_game(game_id, winner, winner_elo, winner_delta, winner_new_elo, loser, loser_elo, loser_delta, loser_new_elo, winner_score, loser_score, season):
    embed = discord.Embed(title=f"Racquetball game id #{game_id}", description=f'Score: <@{winner}> {winner_score}-{loser_score} <@{loser}>', color=0x70ac64)
    winner_rank = await get_player_rank(winner, season)
    loser_rank = await get_player_rank(loser, season)
    embed.add_field(name=f"__Elo Changes__", value=f"<@{winner}> {winner_elo} --> {winner_new_elo} **(+{winner_delta})** | #{winner_rank}\n<@{loser}> {loser_elo} --> {loser_new_elo} **({loser_delta})** | #{loser_rank}", inline=False)

    return embed
'''

'''
async def output_game_unranked(game_id, winner, loser, winner_score, loser_score, season):
    embed = discord.Embed(title=f"Racquetball game id #{game_id}", description=f'Score: <@{winner}> {winner_score}-{loser_score} <@{loser}>', color=0x70ac64)
    return embed
'''


async def validate_game(game_id):
    cursor = mydb.cursor()
    cursor.execute('select player1, player1_elo_delta, player2, player2_elo_delta, winner, season from game_history where gameid=%s and invalid=1', (game_id,))
    result = cursor.fetchone()
    if result is None:
        return 'Game not found or already valid.'
    player1, player1_elo_delta, player2, player2_elo_delta, winner, season = result
    if winner != player1:
        loser = player2
        loser_delta = player2_elo_delta
        winner_delta = player1_elo_delta
    else:
        loser = player1
        loser_delta = player1_elo_delta
        winner_delta = player2_elo_delta

    cursor.execute('update `' + season + '` set elo=elo+%s, wins=wins+1 where discord_id=%s', (winner_delta, winner))
    cursor.execute('update `' + season + '` set elo=elo+%s, losses=losses+1 where discord_id=%s', (loser_delta, loser))
    cursor.execute('update game_history set invalid=0 where gameid=%s', (game_id,))
    cursor.close()
    return 'Game validated.'


async def invalidate_game(game_id):
    cursor = mydb.cursor()
    cursor.execute('select player1, player1_elo_delta, player2, player2_elo_delta, winner, season from game_history where gameid=%s and invalid=0', (game_id,))
    result = cursor.fetchone()
    if result is None:
        return 'Game not found or already invalid.'
    player1, player1_elo_delta, player2, player2_elo_delta, winner, season = result
    if winner != player1:
        loser = player2
        loser_delta = player2_elo_delta
        winner_delta = player1_elo_delta
    else:
        loser = player1
        loser_delta = player1_elo_delta
        winner_delta = player2_elo_delta
        
    cursor.execute('update `' + season + '` set elo=elo-%s, wins=wins-1 where discord_id=%s', (winner_delta, winner))
    cursor.execute('update `' + season + '` set elo=elo-%s, losses=losses-1 where discord_id=%s', (loser_delta, loser))
    cursor.execute('update game_history set invalid=1 where gameid=%s', (game_id,))
    cursor.close()
    return 'Game invalidated.'

async def reverse_game(game_id, winner_score, loser_score):
    cursor = mydb.cursor()
    cursor.execute('select * from game_history where gameid=%s and invalid=0', (game_id,))
    result = cursor.fetchone()
    if result is None:
        return None
    gameid, player1, player1_name, player1_elo, player1_elo_delta, player1_elo_after, player2, player2_name, player2_elo, player2_elo_delta, player2_elo_after, \
    date, winner, winner_name, player1_score, player2_score, season = result
    new_winner = player1 if player1 != winner else player2
    new_loser = player1 if player1 == winner else player2
    new_winner_elo_delta = player1_elo_delta if player1 == new_winner else player2_elo_delta
    new_loser_elo_delta = player1_elo_delta if player1 != new_winner else player2_elo_delta
    # 1. Subtract elo deltas per user
    cursor.execute('update `' + season + '` set elo=elo-%s, wins=wins-1 where discord_id=%s', (new_loser_elo_delta, new_loser))
    cursor.execute('update `' + season + '` set elo=elo-%s, losses=losses-1 where discord_id=%s', (new_winner_elo_delta, new_winner))
    # 2. Run through Elo Rating function with new elo
    cursor.close()
    embed = await EloRating(new_winner, new_loser, season, winner_score, loser_score, update=game_id)
    return embed


# Parameters: ID of winner and loser, and string of queue type
# Queue type either 'Ranked' or 'Friendly'
async def input_unranked_win(winner, loser, season, winner_score, loser_score):
    await check_player_status_unranked(winner, season);
    await check_player_status_unranked(loser, season);
    cursor = mydb.cursor()
    cursor.execute('update `' + season + '` set wins=wins+1 where discord_id=%s', (winner,))
    cursor.execute('update `' + season + '` set losses=losses+1 where discord_id=%s', (loser,))
    winner_name = await get_player_name(winner)
    loser_name = await get_player_name(loser)
    cursor.execute('insert into game_history values (NULL, %s, %s, 0, 0, 0, %s, %s, 0, 0, 0, now(), %s, %s, %s, %s, %s, 0)',
                   (winner, winner_name, loser, loser_name, winner, winner_name, winner_score, loser_score, season,))
    game_id = cursor.lastrowid
    cursor.close()
    #embed = await output_game_unranked(game_id, winner, loser, winner_score, loser_score, season)
    embed = await output_game(game_id)
    return embed

async def check_player_status_unranked(id, season):
    cursor = mydb.cursor()
    cursor.execute('select discord_id from `' + season + '` where discord_id = %s', (id,))
    if cursor.fetchone() is None:
        await add_player_unranked(id, season)
    cursor.close()


async def add_player_unranked(id, season):
    name = await get_player_name(id)
    cursor = mydb.cursor()
    cursor.execute('insert into `' + season + '` values (%s, %s, 0, 0, 0)', (name, id))
    cursor.close()


# Parameters: ID of winner and loser, and string of queue type
# Queue type either 'Ranked' or 'Friendly'
async def input_win(winner, loser, season, winner_score, loser_score):
    await check_player_status(winner, season);
    await check_player_status(loser, season);

    embed = await EloRating(winner, loser, season, winner_score, loser_score)

    return embed


async def check_player_status(id, season):
    cursor = mydb.cursor()
    cursor.execute('select discord_id from `' + season + '` where discord_id = %s', (id,))
    if cursor.fetchone() is None:
        await add_player(id, season)
    cursor.close()


async def add_player(id, season):
    name = await get_player_name(id)
    cursor = mydb.cursor()
    cursor.execute('select * from HighTierPlayers where discord_id=%s', (id,))
    elo = 500
    if cursor.fetchone() is not None:
        elo = 1200
    cursor.execute('insert into `' + season + '` values (%s, %s, %s, 0, 0)', (name, id, elo))
    cursor.close()


async def add_season(season):
    cursor = mydb.cursor()
    cursor.execute('insert into seasons (season_name, primary_ranked, primary_unranked) values (%s, 0, 0)', (season,))
    cursor.execute('create table `' + season + '` (player_name varchar(50), discord_id varchar(18), elo int, wins int, losses int)')
    cursor.close()


async def set_primary_season_ranked(season):
    cursor = mydb.cursor()
    # End the current season
    cursor.execute('update seasons set primary_ranked = 0, end_date = now() where primary_ranked = 1')
    # Set primary ranked season to specified season
    cursor.execute('update seasons set primary_ranked = 1, start_date = now() where season_name = %s', (season,))
    cursor.close()


async def set_primary_season_unranked(season):
    cursor = mydb.cursor()
    # End the current season
    cursor.execute('update seasons set primary_unranked = 0, end_date = now() where primary_unranked = 1')
    # Set primary ranked season to specified season
    cursor.execute('update seasons set primary_unranked = 1, start_date = now() where season_name = %s', (season,))
    cursor.close()


async def add_high_tier_player(id):
    cursor = mydb.cursor()
    cursor.execute('select * from HighTierPlayers where discord_id=%s', (id,))
    if cursor.fetchone() is not None:
        return 'Already a high tier player.'
    name = await get_player_name(id)
    cursor.execute('insert into HighTierPlayers values (%s, %s)', (name, id,))
    ### Give them +500 elo here in current season?
    elo_boost = 500
    season = await get_current_ranked_season()
    cursor.execute('update `' + season + '` set elo=elo+%s where discord_id=%s', (elo_boost, id,))
    cursor.close()
    return f'Player added and granted {elo_boost} elo.'


async def get_player_rank(discord_id, season):
    cursor = mydb.cursor()
    cursor.execute('select count(*) from `' + season + '` where elo >= (select elo from `' + season + '` where discord_id=%s)', (discord_id,))
    rank_num = cursor.fetchone()[0]
    cursor.close()
    return rank_num


async def get_player_name(id):
    n = await client.fetch_user(str(id))
    # , n.discriminator
    return n.display_name


async def get_current_ranked_season():
    cursor = mydb.cursor()
    cursor.execute('select season_name from seasons where primary_ranked = 1')
    season = cursor.fetchone()
    cursor.close()
    return season[0]

async def get_current_unranked_season():
    cursor = mydb.cursor()
    cursor.execute('select season_name from seasons where primary_unranked = 1')
    season = cursor.fetchone()
    cursor.close()
    return season[0]


async def get_versus_stats(id1, id2):
    season = await get_current_ranked_season()
    df = pd.read_sql(f'select player1_id, player2_id, winner_id, player1_score, player2_score from game_history where (player1_id={id1} and player2_id={id2}) or (player1_id={id2} and player2_id={id1}) and invalid=0', mydb)
    print(df)
    counts = df['winner_id'].value_counts()
    id1_wins = counts[id1]
    id2_wins = counts[id2]
    # Get df's of
    df_id1_wins_p1 = df.loc[(df['winner_id'] == id1) & (df['player1_id'] == id1)]
    df_id2_wins_p1 = df.loc[(df['winner_id'] == id2) & (df['player1_id'] == id2)]
    df_id1_wins_p2 = df.loc[(df['winner_id'] == id1) & (df['player2_id'] == id1)]
    df_id2_wins_p2 = df.loc[(df['winner_id'] == id2) & (df['player2_id'] == id2)]
    print(df_id1_wins_p1)
    print(df_id2_wins_p1)
    print(df_id1_wins_p2)
    print(df_id2_wins_p2)
    #id1_winning_scores = df.loc[(df['winner_id'] ==  id1)]
    id1_total_points = df_id1_wins_p1['player1_score'].sum() + df_id1_wins_p2['player2_score'].sum() + df_id2_wins_p1['player2_score'].sum() + df_id2_wins_p2['player1_score'].sum()
    id2_total_points = df_id1_wins_p1['player2_score'].sum() + df_id1_wins_p2['player1_score'].sum() + df_id2_wins_p1['player1_score'].sum() + df_id2_wins_p2['player2_score'].sum()
    id1_average_points = round(id1_total_points / len(df.index), 2)
    id2_average_points = round(id2_total_points / len(df.index), 2)

    #embed = discord.Embed(color=0x70ac64, description=f"```{header}``` ```\n{data}```")
    id1_name = await get_player_name(id1)
    id2_name = await get_player_name(id2)
    embed = discord.Embed(color=0x70ac64, title=f'Stats between {id1_name} and {id2_name}')
    embed.add_field(name="Wins per player", value=f'{id1_name}: {id1_wins}, {id2_name}: {id2_wins}')
    embed.add_field(name="Score per player", value=f'{id1_name}: {id1_total_points}, {id2_name}: {id2_total_points}')
    embed.add_field(name="Average score per player", value=f'{id1_name}: {id1_average_points}, {id2_name}: {id2_average_points}')
    del [df, df_id1_wins_p1, df_id2_wins_p1, df_id1_wins_p2, df_id2_wins_p2]
    return embed


async def get_stats(discord_id):
    season = await get_current_ranked_season()
    rank = await get_player_rank(discord_id, season)
    df = pd.read_sql(f'select player_name, elo, wins, losses from `{season}` where discord_id={discord_id}', mydb)
    df.insert(0, 'Rank', rank)
    df.columns = ['Rank', 'Name', 'Elo', 'W', 'L']

    name = await get_player_name(discord_id)
    cols = df.columns
    ar = df.to_numpy()
    out = ["{: <5} {: <25} {: <4} {: <4} {: <4}".format(*cols)]
    for row in ar:
        out.append("{: <5} {: <20} {: <4} {: <4} {: <4}".format(*row))
    header, data = '\n'.join(out).split('\n', 1)

    embed = discord.Embed(color=0x70ac64, description=f"```{header}``` ```\n{data}```")
    user = await client.fetch_user(str(discord_id))
    embed.set_author(name=user.display_name, icon_url=user.avatar_url)
    del df
    return embed


async def get_ladder(season):
    #df = pd.read_sql(f'select player_name, elo, wins, losses from `{season}` order by elo desc', mydb)
    df = pd.read_sql(f'select row_number() over (order by elo desc, wins desc, losses asc) as rank, player_name, elo, wins, losses from `{season}`', mydb)
    df.columns = ['Rank', 'Name', 'Elo', 'W', 'L']

    cols = df.columns
    ar = df.to_numpy()
    out = ["{: <5} {: <20} {: <4} {: <4} {: <4}".format(*cols)]
    for row in ar:
        out.append("{: <5} {: <20} {: <4} {: <4} {: <4}".format(*row))
    header, data = '\n'.join(out).split('\n', 1)

    embed = discord.Embed(color=0x70ac64, description=f"```{header}``` ```\n{data}```")
    user = await client.fetch_user("1008939447439609907")
    embed.set_author(name=f"{season} Ladder", icon_url=user.avatar_url)
    del df
    return embed


async def check_score(winner_score, loser_score):
    winner_score = abs(int(winner_score))
    loser_score = abs(int(loser_score))
    if winner_score < 11:
        return "Winner must have at least 11 points."

    if winner_score < loser_score:
        return "Winner must have a higher score."

    if winner_score > 11 and winner_score - loser_score != 2:
        return "Invalid score. Must win by 2."

    if winner_score == 11 and winner_score - loser_score < 2:
        return "Invalid score. Must win by 2."

    return None

@client.event
async def on_ready():
    print('Logged in as {0.user}'.format(client))
    game = discord.Game(".help | RacquetBot")
    await client.change_presence(status=discord.Status.online, activity=game)



@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # Authorized users are Ryan and TJ
    auth_user = False
    if message.author.id == 196404822063316992 or message.author.id == 164281046039265281:
        auth_user = True

    msg = str(message.content)
    try:
        n = await client.fetch_user(str(message.author.id))
        print(message.author.id, f"{n.display_name}#{n.discriminator}")
    except:
        print(message.author.id)

    if message.content.lower().startswith('.normal') or message.content.lower().startswith('.unranked'):
        # Make it so user can't @ themselves twice...
        mentions = message.mentions
        if len(mentions) != 2:
            await message.channel.send("Must mention two players.")
            return
        score = msg.split('>')[-1].strip()
        try:
            winner_score, loser_score = score.split('-')
            winner_score = int(winner_score)
            loser_score = int(loser_score)
        except:
            await message.channel.send('Error reading score. Provide score in format: 11-3')
            return

        check = await check_score(winner_score, loser_score)
        if check is not None:
            await message.channel.send(check)
            return

        # Winner is first player mentioned, loser is second
        winner, loser = mentions
        current_season = await get_current_unranked_season()
        embed = await input_unranked_win(str(winner.id), str(loser.id), current_season, int(winner_score), int(loser_score))
        if embed is None:
            await message.channel.send('Game id does not exist.')
        else:
            await message.channel.send(embed=embed)

    if message.content.lower().startswith('.ranked'):
        # Make it so user can't @ themselves twice...
        mentions = message.mentions
        if len(mentions) != 2:
            await message.channel.send("Must mention two players.")
            return
        score = msg.split('>')[-1].strip()
        try:
            winner_score, loser_score = score.split('-')
            winner_score = int(winner_score)
            loser_score = int(loser_score)
        except:
            await message.channel.send('Error reading score. Provide score in format: 11-3')
            return

        check = await check_score(winner_score, loser_score)
        if check is not None:
            await message.channel.send(check)
            return

        # Winner is first player mentioned, loser is second
        winner, loser = mentions
        current_season = await get_current_ranked_season()
        embed = await input_win(str(winner.id), str(loser.id), current_season, int(winner_score), int(loser_score))
        if embed is None:
            await message.channel.send('Game id does not exist.')
        else:
            await message.channel.send(embed=embed)

    if message.content.lower().startswith('.stats'):
        mentions = message.mentions
        if len(mentions) > 2:
            await message.channel.send('Can only mention one player.')
        elif len(mentions) == 2:
            player1 = str(mentions[0].id)
            player2 = str(mentions[1].id)
            embed = await get_versus_stats(player1, player2)
            await message.channel.send(embed=embed)
            return
        elif len(mentions) == 1:
            id = str(mentions[0].id)
        else:
            id = str(message.author.id)
        embed = await get_stats(id)
        await message.channel.send(embed=embed)
        ### Get stats function here

    if message.content.lower().startswith('.ladder'):
        season = await get_current_ranked_season()
        embed = await get_ladder(season)
        await message.channel.send(embed=embed)
        ### Get stats function here

    if message.content.lower().startswith('.addhightierplayer'):
        if not auth_user:
            await message.channel.send('Not allowed to use this command.')
            return
        mentions = message.mentions
        if len(mentions) != 1:
            await message.channel.send('Can only mention one player.')
        result = await add_high_tier_player(str(mentions[0].id))
        await message.channel.send(result)

    if message.content.lower().startswith('.addseason'):
        if not auth_user:
            await message.channel.send('Not allowed to use this command.')
            return
        season = str(msg.split('.addseason', 1)[1]).strip()
        if len(season) < 1:
            await message.channel.send('Provide a name for the season.')
            return
        await add_season(season)
        await message.channel.send('Season added. Type .primaryranked followed by the season name to set it as the current season.')

    if message.content.lower().startswith('.primaryranked'):
        if not auth_user:
            await message.channel.send('Not allowed to use this command.')
            return
        season = str(msg.split('.primaryranked', 1)[1]).strip()
        if len(season) < 1:
            await message.channel.send('Provide a name for the season.')
            return
        await set_primary_season_ranked(season)
        await message.channel.send(f'{season} set as current ranked season.')

    if message.content.lower().startswith('.primaryunranked'):
        await message.channel.send('Command disabled.')
        return
        if not auth_user:
            await message.channel.send('Not allowed to use this command.')
            return
        season = str(msg.split('.primaryunranked', 1)[1]).strip()
        if len(season) < 1:
            await message.channel.send('Provide a name for the season.')
            return
        await set_primary_season_unranked(season)
        await message.channel.send(f'{season} set as current unranked season.')

    if message.content.lower().startswith('.changewin'):
        if not auth_user:
            await message.channel.send('Not allowed to use this command.')
            return
        try:
            input = str(msg.lower().split('.changewin', 1)[1]).replace(" ", "")
            game_id, score = input.split(',')
            winner_score, loser_score = score.split('-')
            winner_score = int(winner_score)
            loser_score = int(loser_score)
        except:
            await message.channel.send('Error reading input. Provide: <game id>,<score>')
            return

        check = await check_score(winner_score, loser_score)
        if check is not None:
            await message.channel.send(check)
            return

        embed = await reverse_game(game_id, winner_score, loser_score)
        if embed is None:
            await message.channel.send('Game id does not exist.')
        else:
            await message.channel.send(embed=embed)

    if message.content.lower().startswith('.game'):
        try:
            game_id = int(msg.lower().split('.game')[1].replace(" ", ""))
        except:
            await message.channel.send('Error reading input. Provide a game id number.')
            return

        embed = await output_game(game_id)
        if embed is None:
            await message.channel.send('Game id does not exist.')
        else:
            await message.channel.send(embed=embed)

    if message.content.lower().startswith('.invalidgame'):
        try:
            game_id = int(msg.lower().split('.invalidgame')[1].replace(" ", ""))
        except:
            await message.channel.send('Error reading input. Provide a game id number.')
            return

        result = await invalidate_game(game_id)
        await message.channel.send(result)
        
        
    if message.content.lower().startswith('.validgame'):
        try:
            game_id = int(msg.lower().split('.invalidgame')[1].replace(" ", ""))
        except:
            await message.channel.send('Error reading input. Provide a game id number.')
            return

        result = await validate_game(game_id)
        await message.channel.send(result)

# client.run(os.environ['TOKEN'])
TOKEN = open("/repo/discord_token.txt", "r").read()
client.run(TOKEN)
