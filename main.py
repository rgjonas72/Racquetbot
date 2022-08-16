#Rank 1 role

#1200 elo start, 500 for shitter

#log score, avg point differential, winrate vs player, point dif vs player

#rated, unrated queue

import discord
import os
from replit import db
from keep_alive import keep_alive
import math

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

# Parameters: Discord ID, queue type
# Queue type either 'Ranked' or 'Friendly'
async def add_player(discord_id, queue):
    # Create database entry for user's stats in specified queue in the current season
    user = await client.fetch_user(discord_id)
    elo = 500
    if discord_id in db['HighTierPlayers']:
      elo = 1200
    # Database format: Name, Elo, Wins, Losses
    ###db[queue + str(discord_id) + db['season']] = [user.display_name, elo, 0, 0]
    # Create database entry to keep history of games for user
    ###db[queue + str(discord_id) + db['season'] + 'history'] = []
    

# Parameters: ID of winner and loser, and string of queue type
# Queue type either 'Ranked' or 'Friendly'
async def input_win(winner, loser, queue):
    winner_db_string = await get_db_string(winner, queue)
    loser_db_string = await get_db_string(loser, queue)
    if winner_db_string not in db.keys():
      await add_player(winner, queue)
    if loser_db_string not in db.keys():
      await add_player(loser, queue)
    winner_elo, loser_elo = await EloRating(winner, loser, queue)
    # Leaderboard update function here probably
    
async def get_db_string(id, queue, season=db['season']):
  return queue + str(id) + season

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
      await input_win(str(winner.id), str(loser.id), 'Ranked')

    if message.content.lower().startswith('.stats'):
      mentions = message.mentions
      if len(mentions) > 1:
        await message.channel.send('Can only mention one player.')
      elif len(mentions) == 1:
        id = mentions[0].id
      else:
        id = message.author.id
      db_vals =  db[await get_db_string(id, 'Ranked')]
      await message.channel.send(db_vals[1])

#db['season'] = 'Fall 2022 Racquetball League'
#db['HighTierPlayers'] = ['196404822063316992', '231554084782604288', '562366102013870092', '164281046039265281']

#keep_alive()
client.run(os.environ['TOKEN'])

