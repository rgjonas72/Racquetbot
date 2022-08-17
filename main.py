# Rank 1 role

# 1200 elo start, 500 for shitter

# log score, avg point differential, winrate vs player, point dif vs player

# rated, unrated queue

import discord
import os
import math
import mysql.connector

mydb = mysql.connector.connect(
    host = "localhost",
    user = "racquetbot",
    password = "racquet",
    database = "racquetbot"
)

mydb.autocommit = True
cursor = mydb.cursor()


'''

p1_k = 32
p2_k = 50

#transformed values, used for calculating probability 
p1_trating = 10 ** (p1_rating/400)
p2_trating = 10 ** (p2_rating/400)

#win = 1, loss = 0
p1_score = 1
p2_score = 0

print(f"P1 rating = {p1_rating}, P2 rating = {p2_rating} \n")

#probabilities
p1_expected_outcome = p1_trating / (p1_trating + p2_trating)
p2_expected_outcome = p2_trating / (p1_trating + p2_trating)

print(f"P1 has a {p1_expected_outcome * 100:.3f}% chance of winning")
print(f"P1 has a {p2_expected_outcome * 100:.3f}% chance of winning\n\n")


p1_delta = p1_k * (p1_score - p1_expected_outcome)
p1_new_rating = str(p1_rating + p1_delta )

p2_delta = p2_k * (p2_score - p2_expected_outcome)
p2_new_rating = str(p2_rating + p2_delta)

print("If P1 wins: \n")
print(f"P1 new elo: {float(p1_new_rating):.3f}")
print(f"P2 new elo: {float(p2_new_rating):.3f}\n")

p1_score = 0
p2_score = 1

p1_new_rating = str(p1_rating + p1_k * (p1_score - p1_expected_outcome))
p2_new_rating = str(p2_rating + p2_k * (p2_score - p2_expected_outcome))

print("If P2 wins: \n")
print(f"P1 new elo: {float(p1_new_rating):.3f}")
print(f"P2 new elo: {float(p2_new_rating):.3f}")
'''

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
    cursor.execute('select count(*) from game_history where discord_id=%s and season=%s', (winner, season,))
    winner_games = cursor.fetchone()[0]
    cursor.execute('select count(*) from game_history where discord_id=%s and season=%s', (loser, season,))
    loser_games = cursor.fetchone()[0]
    # Set k values ### Will be based off # of games
    winner_k = 32
    loser_k = 32
    # Calculate probability
    winner_expected_outcome = winner_elo / (winner_elo + loser_elo)
    loser_expected_outcome = loser_elo / (winner_elo + loser_elo)
    # Calculate post game deltas and elos
    winner_delta = winner_k * (1 - winner_expected_outcome)
    winner_new_elo = winner_elo + winner_delta

    loser_delta = loser_k * (0 - loser_expected_outcome)
    loser_new_elo = loser_elo + loser_delta

    # Insert game into database
    cursor.execute('update `' + season + '` set elo=%s, wins=wins+1 where discord_id=%s', (winner_new_elo, winner,))
    cursor.execute('update `' + season + '` set elo=%s, losses=losses+1 where discord_id=%s', (loser_new_elo, loser,))
    winner_name = get_player_name(winner)
    loser_name = get_player_name(loser)
    cursor.execute('insert into game_history values (NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), %s, %s, %s, %s, %s, %s, %s, %s, %s,)', \
                   (winner, winner_name, winner_elo, winner_delta, winner_new_elo, loser, loser_name, loser_elo, loser_delta, loser_new_elo, \
                    winner, winner_name, winner_score, loser_score, season,))


# Initiate discord client
intents = discord.Intents.all()
client = discord.Client(intents=intents)


# Parameters: ID of winner and loser, and string of queue type
# Queue type either 'Ranked' or 'Friendly'
async def input_win(winner, loser, season):
    await check_player_status(winner, season);
    await check_player_status(loser, season);

    winner_elo, loser_elo = await EloRating(winner, loser, season)
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


async def add_high_tier_player(id):
    cursor.execute('select * from HighTierPlayers where discord_id=%s', (id,))
    if cursor.fetchone() is not None:
        return 'Already a high tier player.'
    name = await get_player_name(id)
    cursor.execute('insert into HighTierPlayers values (%s, %s)', (name, id,))
    ### Give them +700 elo here in current season?
    return 'Player added'


async def get_player_name(id):
    n = await client.fetch_user(str(id))
    # , n.discriminator
    return n.display_name


async def get_current_ranked_season():
    cursor.execute('select season_name from seasons where primary_ranked = 1')
    season = cursor.fetchone()
    return season[0]


async def get_stats(discord_id, season=await get_current_ranked_season()):
    print(season)


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

    if message.content.lower().startswith('.ranked'):
        mentions = message.mentions
        if len(mentions) != 2:
            await message.channel.send("Must mention two players.")
            return
        # Winner is first player mentioned, loser is second
        winner, loser = mentions
        current_season = await get_current_ranked_season()
        await input_win(str(winner.id), str(loser.id), current_season)

    if message.content.lower().startswith('.stats'):
        mentions = message.mentions
        if len(mentions) > 1:
            await message.channel.send('Can only mention one player.')
        elif len(mentions) == 1:
            id = str(mentions[0].id)
        else:
            id = str(message.author.id)
        await get_stats(id)

        ### Get stats function here


    if message.content.lower().startswith('.addhightierplayer'):
        if not auth_user:
            await message.channel.send('Not allowed to use this command.')
        mentions = message.mentions
        if len(mentions) != 1:
            await message.channel.send('Can only mention one player.')
        result = await add_high_tier_player(str(mentions[0].id))
        await message.channel.send(result)

    if message.content.lower().startswith('.addseason'):
        season = str(msg.split('.addseason', 1)[1]).strip()
        await add_season(season)
        await message.channel.send('Season added. Type .primaryranked or .primaryunranked followed by the season name to set it as the current season.')

    if message.content.lower().startswith('.primaryranked'):
        season = str(msg.split('.primaryranked', 1)[1]).strip()
        await set_primary_season_ranked(season)
        await message.channel.send(f'{season} set as current ranked season.')


# keep_alive()
# client.run(os.environ['TOKEN'])
TOKEN = open("/repo/discord_token.txt", "r").read()
client.run(TOKEN)
