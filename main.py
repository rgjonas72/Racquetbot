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

cursor = mydb.cursor()


async def Probability(rating1, rating2):
    return 1.0 * 1.0 / (1 + 1.0 * math.pow(10, 1.0 * (rating1 - rating2) / 400))


# Function to calculate Elo rating
# K is a constant.
# d determines whether
# Player A wins or Player B.
async def EloRating(winner, loser, queue, K=5):
    winner_db_string = await get_db_string(winner, queue)
    loser_db_string = await get_db_string(loser, queue)
    # Ra for winner, Rb for loser
    ###Ra = db[winner_db_string][1]
    ###Rb = db[loser_db_string][1]

    # To calculate the Winning
    # Probability of Player B
    Pb = await Probability(Ra, Rb)

    # To calculate the Winning
    # Probability of Player A
    Pa = await Probability(Rb, Ra)

    # Calculate new ratings
    Ra_new = Ra + K * (1 - Pa)
    Rb_new = Rb + K * (0 - Pb)

    ###db[winner_db_string][1] = Ra_new
    ###db[loser_db_string][1] = Rb_new

    # Return value changes in ratings
    return Ra_new - Ra, Rb_new - Rb


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
    cursor.execute('select discord_id from `' + season + '` where id = %s', (id,))
    if cursor.fetchone() is None:
        await add_player(id, season)


async def add_player(id, season):
    name = await get_player_name(id)
    cursor.execute('select * from HighTierPlayers where id=%s', (id,))
    elo = 500
    if cursor.fetchone() is not None:
        elo = 1200
    cursor.execute('insert into `' + season + '` values (%s, %s, %s, 0, 0)', (name, id, elo))


async def add_season(season):
    print(season)
    cursor.execute('insert into seasons (season_name, primary_ranked, primary_unranked) values (%s, 0, 0)', (season,))
    cursor.execute('create table `' + season + '` (player_name varchar(50), discord_id int, elo int, wins int, losses int)')


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
    cursor.execute('select season_name from season where primary_ranked == 1')
    season = cursor.fetchone()
    print(season)
    return season


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
