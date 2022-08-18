# Rank 1 role

# 1200 elo start, 500 for shitter

# log score, avg point differential, winrate vs player, point dif vs player

# rated, unrated queue

import discord
import os
import math
import mysql.connector
import pandas as pd
from table2ascii import table2ascii as t2a, PresetStyle

mydb = mysql.connector.connect(
    host = "localhost",
    user = "racquetbot",
    password = "racquet",
    database = "racquetbot"
)

mydb.autocommit = True
cursor = mydb.cursor()


'''
#K value gradation based on elo
k_valuea = 50
k_valueb = 32
k_valuec = 24
k_valued = 16

#elo thresholds 
k_thresholda = 2400
k_thresholdb = 2100

#number of games to get noob K value
noob_game_count = 5

p1_k = 32
p2_k = 50

#number of games played to calculate variable K value
#test numbers
p1_ngames = 10
p2_ngames = 2

#check what elo range player 1 is in
if p1_rating >= k_thresholda:
  p1_k = k_valued

if p1_rating >= k_thresholdb and p1_rating < k_thresholda:
  p1_k = k_valuec

if p1_rating < k_thresholdb:
  p1_k = k_valueb
  
#check what elo range player 2 is in
if p2_rating >= k_thresholda:
  p2_k = k_valued

if p2_rating >= k_thresholdb and p1_rating < k_thresholda:
  p2_k = k_valuec

if p1_rating < k_thresholdb:
  p2_k = k_valueb

#if the player has less than x number of games, make them earn more 
if p1_ngames <= noob_game_count:
  p1_k = k_valuea

if p2_ngames <= noob_game_count:
  p2_k = k_valuea
'''

async def get_k_value(elo, ngames):
    # K value gradation based on elo
    k_valuea, k_valueb, k_valuec, k_valued = [50, 32, 24, 16]

    # elo thresholds
    k_thresholda, k_thresholdb = [2400, 2100]

    # number of games to get noob K value
    noob_game_count = 5

    k = 32

    # number of games played to calculate variable K value
    # test numbers
    noob_games = 10

    # check what elo range player 1 is in
    if elo >= k_thresholda:
        k = k_valued

    if k_thresholdb <= elo < k_thresholda:
        k = k_valuec

    if elo < k_thresholdb:
        k = k_valueb

    # If the player has less than x number of noob game count, make them earn more
    if ngames <= noob_games:
        k = k_valuea

    return k


# Function to calculate Elo rating
# K is a constant.
# d determines whether
# Player A wins or Player B.
async def EloRating(winner, loser, season, winner_score, loser_score):
    # Get elo for both players
    cursor.execute('select elo from `' + season + '` where discord_id=%s', (winner,))
    winner_elo = cursor.fetchone()[0]
    cursor.execute('select elo from `' + season + '` where discord_id=%s', (loser,))
    loser_elo = cursor.fetchone()[0]
    # Get both players number of games played
    cursor.execute('select count(*) from game_history where (player1_id=%s or player2_id=%s) and season=%s', (winner, winner, season,))
    winner_games = cursor.fetchone()[0]
    cursor.execute('select count(*) from game_history where (player1_id=%s or player2_id=%s) and season=%s', (loser, loser, season,))
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
    loser_new_elo = loser_elo + loser_delta

    # Insert game into database
    cursor.execute('update `' + season + '` set elo=%s, wins=wins+1 where discord_id=%s', (winner_new_elo, winner,))
    cursor.execute('update `' + season + '` set elo=%s, losses=losses+1 where discord_id=%s', (loser_new_elo, loser,))
    winner_name = await get_player_name(winner)
    loser_name = await get_player_name(loser)
    cursor.execute('insert into game_history values (NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), %s, %s, %s, %s, %s)',
                   (winner, winner_name, winner_elo, winner_delta, winner_new_elo, loser, loser_name, loser_elo, loser_delta, loser_new_elo,
                    winner, winner_name, winner_score, loser_score, season,))

    print(cursor.lastrowid)




# Initiate discord client
intents = discord.Intents.all()
client = discord.Client(intents=intents)


async def reverse_game(game_id, winner_score, loser_score):
    pass


# Parameters: ID of winner and loser, and string of queue type
# Queue type either 'Ranked' or 'Friendly'
async def input_unranked_win(winner, loser, season, winner_score, loser_score):
    await check_player_status_unranked(winner, season);
    await check_player_status_unranked(loser, season);
    cursor.execute('update `' + season + '` set wins=wins+1 where discord_id=%s', (winner,))
    cursor.execute('update `' + season + '` set losses=losses+1 where discord_id=%s', (loser,))
    winner_name = await get_player_name(winner)
    loser_name = await get_player_name(loser)
    cursor.execute('insert into game_history values (NULL, %s, %s, 0, 0, 0, %s, %s, 0, 0, 0, now(), %s, %s, %s, %s, %s)',
                   (winner, winner_name, loser, loser_name, winner, winner_name, winner_score, loser_score, season,))


async def check_player_status_unranked(id, season):
    cursor.execute('select discord_id from `' + season + '` where discord_id = %s', (id,))
    if cursor.fetchone() is None:
        await add_player_unranked(id, season)


async def add_player_unranked(id, season):
    name = await get_player_name(id)
    cursor.execute('insert into `' + season + '` values (%s, %s, 0, 0, 0)', (name, id))


# Parameters: ID of winner and loser, and string of queue type
# Queue type either 'Ranked' or 'Friendly'
async def input_win(winner, loser, season, winner_score, loser_score):
    await check_player_status(winner, season);
    await check_player_status(loser, season);

    await EloRating(winner, loser, season, winner_score, loser_score)
    # Leaderboard update function here probably


async def check_player_status(id, season):
    cursor.execute('select discord_id from `' + season + '` where discord_id = %s', (id,))
    if cursor.fetchone() is None:
        await add_player(id, season)


async def add_player(id, season):
    name = await get_player_name(id)
    cursor.execute('select * from HighTierPlayers where discord_id=%s', (id,))
    elo = 500
    if cursor.fetchone() is not None:
        elo = 1200
    cursor.execute('insert into `' + season + '` values (%s, %s, %s, 0, 0)', (name, id, elo))


async def add_season(season):
    cursor.execute('insert into seasons (season_name, primary_ranked, primary_unranked) values (%s, 0, 0)', (season,))
    cursor.execute('create table `' + season + '` (player_name varchar(50), discord_id varchar(18), elo int, wins int, losses int)')


async def set_primary_season_ranked(season):
    # End the current season
    cursor.execute('update seasons set primary_ranked = 0, end_date = now() where primary_ranked = 1')
    # Set primary ranked season to specified season
    cursor.execute('update seasons set primary_ranked = 1, start_date = now() where season_name = %s', (season,))


async def set_primary_season_unranked(season):
    # End the current season
    cursor.execute('update seasons set primary_unranked = 0, end_date = now() where primary_unranked = 1')
    # Set primary ranked season to specified season
    cursor.execute('update seasons set primary_unranked = 1, start_date = now() where season_name = %s', (season,))


async def add_high_tier_player(id):
    cursor.execute('select * from HighTierPlayers where discord_id=%s', (id,))
    if cursor.fetchone() is not None:
        return 'Already a high tier player.'
    name = await get_player_name(id)
    cursor.execute('insert into HighTierPlayers values (%s, %s)', (name, id,))
    ### Give them +500 elo here in current season?
    elo_boost = 500
    season = await get_current_ranked_season()
    cursor.execute('update `' + season + '` set elo=elo+%s where discord_id=%s', (elo_boost, id,))
    return f'Player added and granted {elo_boost} elo.'


async def get_player_name(id):
    n = await client.fetch_user(str(id))
    # , n.discriminator
    return n.display_name


async def get_current_ranked_season():
    cursor.execute('select season_name from seasons where primary_ranked = 1')
    season = cursor.fetchone()
    return season[0]

async def get_current_unranked_season():
    cursor.execute('select season_name from seasons where primary_unranked = 1')
    season = cursor.fetchone()
    return season[0]


async def get_stats(discord_id):
    season = await get_current_ranked_season()
    df = pd.read_sql(f'select player_name, elo, wins, losses from `{season}` where discord_id={discord_id}', mydb)
    print(df.head())
    df.columns = ['Name', 'Elo', 'Wins', 'Losses']
    name = await get_player_name(discord_id)

    #embed = discord.Embed(title=f"{name}'s stats", color=0x70ac64)
    embed = discord.Embed(color=0x70ac64)

    cols, data = df.to_string(index=False, justify="center", col_space=10).split('\n', 1)

    embed.add_field(name=f"{name} stats", value=f"```{cols}``````\n{data}```", inline=False)
    return embed


async def get_ladder(season):
    df = pd.read_sql(f'select player_name, elo, wins, losses from `{season}` order by elo desc', mydb)
    df.columns = ['Name', 'Elo', 'Wins', 'Losses']
    embed = discord.Embed(color=0x70ac64)
    cols, data = df.to_string(index=False, justify='left', col_space=10).split('\n', 1)

    embed.add_field(name=f"{season} Ladder", value=f"```{cols}``````\n{data}```", inline=False)
    return embed


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

        if int(winner_score) < int(loser_score):
            await message.channel.send("Winner must have a higher score.")
            return
        # Winner is first player mentioned, loser is second
        winner, loser = mentions
        current_season = await get_current_unranked_season()
        await input_unranked_win(str(winner.id), str(loser.id), current_season, int(winner_score), int(loser_score))
        await message.channel.send('Game entered.')

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

        if int(winner_score) < int(loser_score):
            await message.channel.send("Winner must have a higher score.")
            return
        # Winner is first player mentioned, loser is second
        winner, loser = mentions
        current_season = await get_current_ranked_season()
        await input_win(str(winner.id), str(loser.id), current_season, int(winner_score), int(loser_score))
        await message.channel.send('Game input.')

    if message.content.lower().startswith('.stats'):
        mentions = message.mentions
        if len(mentions) > 1:
            await message.channel.send('Can only mention one player.')
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

        if int(winner_score) < int(loser_score):
            await message.channel.send("Winner must have a higher score.")
            return

        await reverse_game(game_id, winner_score, loser_score)


# keep_alive()
# client.run(os.environ['TOKEN'])
TOKEN = open("/repo/discord_token.txt", "r").read()
client.run(TOKEN)
