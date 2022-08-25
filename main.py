import discord
import os
import math
import mysql.connector
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import pymysql
import datetime as dt
import scipy


async def get_db():
    mydb = mysql.connector.connect(
            host="localhost",
            user="racquetbot",
            password="racquet",
            database="racquetbot")
    mydb.autocommit = True
    return mydb

engine = create_engine("mysql+pymysql://racquetbot:racquet@localhost/racquetbot?charset=utf8mb4")

# Initiate discord client
intents = discord.Intents.all()
client = discord.Client(intents=intents)

'''
winprob <- function(elo1,
                    elo2,
                    normprob = TRUE,
                    fac = NULL) {

  if (normprob) {
    # z score based on fixed SD=200 (see Elo 1978)
    z_score <- (elo1 - elo2) / (200 * sqrt(2))
    p_win <- pnorm(z_score)
  } else {
    if (is.null(fac)) {
      p_win <- 1 - 1/(1 + 10 ^ ((elo1 - elo2) / 400))
    } else {
      p_win <- 1 / (1 + exp(fac * (elo2 - elo1)))
      # Goffe's: p_win <- 1/(1 + exp(diff_f * (elo2 - elo1)))
    }
  }

  return(p_win)
}
'''
async def get_win_prob(elo1, elo2, normprob=True, fac=None):
    if normprob:
        z_score = (elo1 - elo2) / (200 * math.sqrt(2))
        p_win = scipy.stats.norm.cdf(z_score)
    else:
        if fac is None:
            p_win = 1 - 1 / (1 + 10 ** ((elo1 - elo2) / 400))
        else:
            p_win = 1 / (1 + math.exp(fac * (elo2 - elo1)))
    return p_win


async def get_k_value(elo, ngames):
    # K value gradation based on elo
    #k_valuea, k_valueb, k_valuec, k_valued = [60, 43, 35, 28]
    k_valuea, k_valueb, k_valuec, k_valued = [65, 65, 54, 40]

    # elo thresholds
    k_thresholda, k_thresholdb = [1600, 1000]

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
    mydb = await get_db()
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
    #             R(1) = 10r(1)/400
    #
    #             R(2) = 10r(2)/400
    #winner_adjusted_elo = 10**(winner_elo/400)
    #loser_adjusted_elo = 10**(loser_elo/400)
    winner_adjusted_elo = await get_win_prob(winner_elo, loser_elo)
    loser_adjusted_elo = await get_win_prob(loser_elo, winner_elo)
    print(winner_elo, loser_elo)
    print(winner_adjusted_elo, loser_adjusted_elo)
    winner_expected_outcome = winner_adjusted_elo / (winner_adjusted_elo + loser_adjusted_elo)
    loser_expected_outcome = loser_adjusted_elo / (winner_adjusted_elo + loser_adjusted_elo)
    print(winner_expected_outcome, loser_expected_outcome)
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
    mydb = await get_db()
    cursor = mydb.cursor()
    cursor.execute('select * from game_history where gameid=%s', (game_id,))
    result = cursor.fetchone()
    if result is None:
        cursor.close()
        return None
    print(result)
    gameid, player1, player1_name, player1_elo, player1_elo_delta, player1_elo_after, player2, player2_name, player2_elo, player2_elo_delta, player2_elo_after, \
        date, winner, winner_name, player1_score, player2_score, season, invalid = result
    embed = discord.Embed(title=f"Racquetball game id #{game_id}",
                          description=f'Score: <@{player1}> {player1_score}-{player2_score} <@{player2}>',
                          color=0x70ac64)
    if season != await get_current_unranked_season():
        embed.add_field(name=f"__Elo Changes__", value=f"<@{player1}> {player1_elo} --> {player1_elo_after} **(+{player1_elo_delta})**\n<@{player2}> {player2_elo} --> {player2_elo_after} **({player2_elo_delta})**", inline=False)
        if invalid == 1:
           embed.set_footer(text='❌ Game invalid')
    cursor.close()
    return embed


async def validate_game(game_id):
    mydb = await get_db()
    cursor = mydb.cursor()
    cursor.execute('select player1_id, player1_elo_delta, player2_id, player2_elo_delta, winner_id, season from game_history where gameid=%s and invalid=1', (game_id,))
    result = cursor.fetchone()
    if result is None:
        cursor.close()
        return 'Game not found or already valid.'
    player1, player1_elo_delta, player2, player2_elo_delta, winner, season = result
    if winner == player1:
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
    mydb = await get_db()
    cursor = mydb.cursor()
    cursor.execute('select player1_id, player1_elo_delta, player2_id, player2_elo_delta, winner_id, season from game_history where gameid=%s and invalid=0', (game_id,))
    result = cursor.fetchone()
    if result is None:
        cursor.close()
        return 'Game not found or already invalid.'
    player1, player1_elo_delta, player2, player2_elo_delta, winner, season = result
    if winner == player1:
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
    mydb = await get_db()
    cursor = mydb.cursor()
    cursor.execute('select * from game_history where gameid=%s and invalid=0', (game_id,))
    result = cursor.fetchone()
    if result is None:
        cursor.close()
        return None
    gameid, player1, player1_name, player1_elo, player1_elo_delta, player1_elo_after, player2, player2_name, player2_elo, player2_elo_delta, player2_elo_after, \
    date, winner, winner_name, player1_score, player2_score, season, invalid = result
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
    mydb = await get_db()
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
    mydb = await get_db()
    cursor = mydb.cursor()
    cursor.execute('select discord_id from `' + season + '` where discord_id = %s', (id,))
    if cursor.fetchone() is None:
        await add_player_unranked(id, season)
    cursor.close()


async def add_player_unranked(id, season):
    name = await get_player_name(id)
    mydb = await get_db()
    cursor = mydb.cursor()
    cursor.execute('insert into `' + season + '` values (%s, %s, 0, 0, 0)', (name, id))
    cursor.close()


# Parameters: ID of winner and loser, and string of queue type
# Queue type either 'Ranked' or 'Friendly'
async def input_win(winner, loser, season, winner_score, loser_score, update=None):
    await check_player_status(winner, season);
    await check_player_status(loser, season);

    embed = await EloRating(winner, loser, season, winner_score, loser_score, update)

    return embed


async def check_player_status(id, season):
    mydb = await get_db()
    cursor = mydb.cursor()
    cursor.execute('select discord_id from `' + season + '` where discord_id = %s', (id,))
    if cursor.fetchone() is None:
        await add_player(id, season)
    cursor.close()


async def add_player(id, season):
    name = await get_player_name(id)
    mydb = await get_db()
    cursor = mydb.cursor()
    cursor.execute('select * from HighTierPlayers where discord_id=%s', (id,))
    elo = 500
    if cursor.fetchone() is not None:
        elo = 1200
    cursor.execute('insert into `' + season + '` values (%s, %s, %s, 0, 0)', (name, id, elo))
    cursor.close()


async def add_season(season):
    mydb = await get_db()
    cursor = mydb.cursor()
    cursor.execute('insert into seasons (season_name, primary_ranked, primary_unranked) values (%s, 0, 0)', (season,))
    cursor.execute('create table `' + season + '` (player_name varchar(50), discord_id varchar(18), elo int, wins int, losses int)')
    cursor.close()


async def set_primary_season_ranked(season):
    mydb = await get_db()
    cursor = mydb.cursor()
    # End the current season
    cursor.execute('update seasons set primary_ranked = 0, end_date = now() where primary_ranked = 1')
    # Set primary ranked season to specified season
    cursor.execute('update seasons set primary_ranked = 1, start_date = now() where season_name = %s', (season,))
    cursor.close()


async def set_primary_season_unranked(season):
    mydb = await get_db()
    cursor = mydb.cursor()
    # End the current season
    cursor.execute('update seasons set primary_unranked = 0, end_date = now() where primary_unranked = 1')
    # Set primary ranked season to specified season
    cursor.execute('update seasons set primary_unranked = 1, start_date = now() where season_name = %s', (season,))
    cursor.close()


async def add_high_tier_player(id):
    mydb = await get_db()
    cursor = mydb.cursor()
    cursor.execute('select * from HighTierPlayers where discord_id=%s', (id,))
    if cursor.fetchone() is not None:
        cursor.close()
        return 'Already a high tier player.'
    name = await get_player_name(id)
    cursor.execute('insert into HighTierPlayers values (%s, %s)', (name, id,))
    ### Give them +600 elo here in current season?
    elo_boost = 700
    season = await get_current_ranked_season()
    cursor.execute('update `' + season + '` set elo=elo+%s where discord_id=%s', (elo_boost, id,))
    cursor.close()
    return f'Player added and granted {elo_boost} elo.'


async def get_player_rank(discord_id, season):
    mydb = await get_db()
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
    mydb = await get_db()
    cursor = mydb.cursor()
    cursor.execute('select season_name from seasons where primary_ranked = 1')
    season = cursor.fetchone()
    cursor.close()
    return season[0]

async def get_current_unranked_season():
    mydb = await get_db()
    cursor = mydb.cursor()
    cursor.execute('select season_name from seasons where primary_unranked = 1')
    season = cursor.fetchone()
    cursor.close()
    return season[0]


async def get_versus_stats(id1, id2):
    season = await get_current_ranked_season()
    df = pd.read_sql(f"select player1_id, player2_id, winner_id, player1_score, player2_score from game_history where season='{season}' and invalid=0 and ((player1_id={id1} and player2_id={id2}) or (player1_id={id2} and player2_id={id1}))", engine)

    counts = df['winner_id'].value_counts()
    if id1 in counts:
        id1_wins = counts[id1]
    else:
        id1_wins = 0
    if id2 in counts:
        id2_wins = counts[id2]
    else:
        id2_wins = 0

    if id1_wins == 0 and id2_wins == 0:
        return None

    df_id1_wins_p1 = df.loc[(df['winner_id'] == id1) & (df['player1_id'] == id1)]
    df_id2_wins_p1 = df.loc[(df['winner_id'] == id2) & (df['player1_id'] == id2)]
    df_id1_wins_p2 = df.loc[(df['winner_id'] == id1) & (df['player2_id'] == id1)]
    df_id2_wins_p2 = df.loc[(df['winner_id'] == id2) & (df['player2_id'] == id2)]

    #id1_winning_scores = df.loc[(df['winner_id'] ==  id1)]
    id1_total_points = df_id1_wins_p1['player1_score'].sum() + df_id1_wins_p2['player2_score'].sum() + df_id2_wins_p1['player2_score'].sum() + df_id2_wins_p2['player1_score'].sum()
    id2_total_points = df_id1_wins_p1['player2_score'].sum() + df_id1_wins_p2['player1_score'].sum() + df_id2_wins_p1['player1_score'].sum() + df_id2_wins_p2['player2_score'].sum()
    id1_average_points = round(id1_total_points / len(df.index), 2)
    id2_average_points = round(id2_total_points / len(df.index), 2)

    #embed = discord.Embed(color=0x70ac64, description=f"```{header}``` ```\n{data}```")
    id1_name = await get_player_name(id1)
    id2_name = await get_player_name(id2)
    embed = discord.Embed(color=0x70ac64, title=f'Stats between {id1_name} and {id2_name}')
    embed.add_field(name="__Wins per player__", value=f'<@{id1}> {id1_wins} - {id2_wins} <@{id2}>', inline=False)
    embed.add_field(name="__Total score per player__", value=f'<@{id1}> {id1_total_points} - {id2_total_points} <@{id2}>', inline=False)
    embed.add_field(name="__Average score per player__", value=f'<@{id1}> {id1_average_points} - {id2_average_points} <@{id2}>', inline=False)
    del [df, df_id1_wins_p1, df_id2_wins_p1, df_id1_wins_p2, df_id2_wins_p2]
    return embed


async def get_history(id1, id2=None):
    id1_name = await get_player_name(id1)
    if id2 is None:
        df = pd.read_sql(f"select player1_id, player1_name, player2_id, player2_name, winner_id, player1_score, player2_score, game_date from game_history where invalid=0 and (player1_id={id1} or player2_id={id1}) order by game_date desc limit 10", engine)

        title = f'History for {id1_name}'
        user = await client.fetch_user(id1)


    else:
        df = pd.read_sql(f"select player1_id, player1_name, player2_id, player2_name, winner_id, player1_score, player2_score, game_date from game_history where invalid=0 and ((player1_id={id1} and player2_id={id2}) or (player1_id={id2} and player2_id={id1})) order by game_date desc limit 10", engine)
        id2_name = await get_player_name(id2)
        title = f'History between {id1_name} and {id2_name}'
        user = await client.fetch_user("1008939447439609907")


    df[['player1_name', 'player2_name', 'player1_score', 'player2_score']] = df[['player2_name', 'player1_name', 'player2_score', 'player1_score']].where(df['player2_id'] == id1, df[['player1_name', 'player2_name', 'player1_score', 'player2_score']].values)
    #df['player1_score_string'] = df['player1_score'].astype(str).apply(lambda x: "{}{}{}".format('**', x, '**')).where(df['player1_score'] > df['player2_score'])
    #df['player1_score_string'] = df['player1_score'].astype(str).where(df['player1_score'] < df['player2_score'], df['player1_score_string'])
    #df['player2_score_string'] = df['player2_score'].astype(str).apply(lambda x: "{}{}{}".format('**', x, '**')).where(df['player1_score'] < df['player2_score'])
    #df['player2_score_string'] = df['player2_score'].astype(str).where(df['player1_score'] > df['player2_score'], df['player2_score_string'])
    #df.columns = ['Player 1 ID', 'Player 1', 'Player 2 ID', 'Player 2', 'Winner ID', 'Player 1 Score_old', 'Player 2 Score_old', 'Date', 'Player 1 Score', 'Player 2 Score']

    df.columns = ['Player 1 ID', 'Player 1', 'Player 2 ID', 'Player 2', 'Winner ID', 'Player 1 Score', 'Player 2 Score', 'Date']


    df['Score'] = df['Player 1 Score'].astype(str) + ' - ' + df['Player 2 Score'].astype(str)
    df['Date'] = pd.to_datetime(df.Date, format='%m/%d')
    df['Date'] = df['Date'].dt.strftime('%m/%d')

    df_final = df[['Player 1', 'Score', 'Player 2', 'Date']]
    name_max_length_p1 = str(max(8, df["Player 1"].str.len().max() + 1))
    name_max_length_p2 = str(max(8, df["Player 2"].str.len().max() + 1))

    cols = df_final.columns
    out = ['{: ^{p1_len}} {: ^8} {: ^{p2_len}} {: ^5}'.format(*cols, p1_len=name_max_length_p1, p2_len=name_max_length_p2)]

    num_rows = len(df.index)
    if num_rows == 0:
        out = out[0]
        embed = discord.Embed(color=0x70ac64, description=f"```{out}```")
        embed.set_author(name=title, icon_url=user.avatar_url)
        del [df, df_final]
        return embed

    ar = df_final.to_numpy()
    for row in ar:
        out.append('{: ^{p1_len}} {: ^8} {: ^{p2_len}} {: ^5}'.format(*row, p1_len=name_max_length_p1, p2_len=name_max_length_p2))
    header, data = '\n'.join(out).split('\n', 1)

    embed = discord.Embed(color=0x70ac64, description=f"```yaml\n{header}``` ```\n{data}```")
    embed.set_author(name=title, icon_url=user.avatar_url)
    del [df, df_final]
    return embed



async def get_versus_stats_all(id1, id2):
    df = pd.read_sql(f"select player1_id, player2_id, winner_id, player1_score, player2_score from game_history where invalid=0 and ((player1_id={id1} and player2_id={id2}) or (player1_id={id2} and player2_id={id1}))", engine)
    counts = df['winner_id'].value_counts()
    if id1 in counts:
        id1_wins = counts[id1]
    else:
        id1_wins = 0
    if id2 in counts:
        id2_wins = counts[id2]
    else:
        id2_wins = 0

    if id1_wins == 0 and id2_wins == 0:
        return None

    df_id1_wins_p1 = df.loc[(df['winner_id'] == id1) & (df['player1_id'] == id1)]
    df_id2_wins_p1 = df.loc[(df['winner_id'] == id2) & (df['player1_id'] == id2)]
    df_id1_wins_p2 = df.loc[(df['winner_id'] == id1) & (df['player2_id'] == id1)]
    df_id2_wins_p2 = df.loc[(df['winner_id'] == id2) & (df['player2_id'] == id2)]

    #id1_winning_scores = df.loc[(df['winner_id'] ==  id1)]
    id1_total_points = df_id1_wins_p1['player1_score'].sum() + df_id1_wins_p2['player2_score'].sum() + df_id2_wins_p1['player2_score'].sum() + df_id2_wins_p2['player1_score'].sum()
    id2_total_points = df_id1_wins_p1['player2_score'].sum() + df_id1_wins_p2['player1_score'].sum() + df_id2_wins_p1['player1_score'].sum() + df_id2_wins_p2['player2_score'].sum()
    id1_average_points = round(id1_total_points / len(df.index), 2)
    id2_average_points = round(id2_total_points / len(df.index), 2)

    #embed = discord.Embed(color=0x70ac64, description=f"```{header}``` ```\n{data}```")
    id1_name = await get_player_name(id1)
    id2_name = await get_player_name(id2)
    embed = discord.Embed(color=0x70ac64, title=f'All-time stats between {id1_name} and {id2_name}')
    embed.add_field(name="__Wins per player__", value=f'<@{id1}> {id1_wins} - {id2_wins} <@{id2}>', inline=False)
    embed.add_field(name="__Total score per player__", value=f'<@{id1}> {id1_total_points} - {id2_total_points} <@{id2}>', inline=False)
    embed.add_field(name="__Average score per player__", value=f'<@{id1}> {id1_average_points} - {id2_average_points} <@{id2}>', inline=False)
    del [df, df_id1_wins_p1, df_id2_wins_p1, df_id1_wins_p2, df_id2_wins_p2]
    return embed


async def get_stats(discord_id):
    season = await get_current_ranked_season()
    rank = await get_player_rank(discord_id, season)
    df = pd.read_sql(f'select player_name, elo, wins, losses from `{season}` where discord_id={discord_id}', engine)
    df.insert(0, 'Rank', rank)
    df.columns = ['Rank', 'Name', 'Elo', 'W', 'L']
    user = await client.fetch_user(str(discord_id))
    name = await get_player_name(discord_id)
    cols = df.columns
    ar = df.to_numpy()
    out = ["{: <5} {: <30} {: <4} {: <4} {: <4}".format(*cols)]
    if len(df.index) == 0:
        out = out[0]
        embed = discord.Embed(color=0x70ac64, description=f"```{out}```")
        embed.set_author(name=user.display_name, icon_url=user.avatar_url)
        return embed
    for row in ar:
        out.append("{: <5} {: <30} {: <4} {: <4} {: <4}".format(*row))
    header, data = '\n'.join(out).split('\n', 1)

    embed = discord.Embed(color=0x70ac64, description=f"```yaml\n{header}``` ```\n{data}```")

    embed.set_author(name=user.display_name, icon_url=user.avatar_url)

    del df
    ####
    df_history = pd.read_sql(f"select * from game_history where (player1_id={discord_id} or player2_id={discord_id}) and season='{season}' and invalid=0", engine)
    ngames = len(df_history.index)
    if ngames == 0:
        del df_history
        return embed

    nwins = len(df_history.loc[df_history['winner_id'] == discord_id].index)
    nlosses = ngames - nwins

    as_player1_sums = df_history.loc[df_history['player1_id'] == discord_id]['player1_score'].sum()
    as_player2_sums = df_history.loc[df_history['player2_id'] == discord_id]['player2_score'].sum()

    points_in_wins_p1 = df_history.loc[(df_history['winner_id'] == discord_id) & (df_history['player1_id'] == discord_id)]['player1_score'].sum()
    points_in_wins_p2 = df_history.loc[(df_history['winner_id'] == discord_id) & (df_history['player2_id'] == discord_id)]['player2_score'].sum()
    points_in_losses_p1 = df_history.loc[(df_history['winner_id'] != discord_id) & (df_history['player1_id'] == discord_id)]['player1_score'].sum()
    points_in_losses_p2 = df_history.loc[(df_history['winner_id'] != discord_id) & (df_history['player2_id'] == discord_id)]['player2_score'].sum()


    avg_score = round((as_player1_sums + as_player2_sums) / ngames, 2)
    avg_score_wins = round((points_in_wins_p1 + points_in_wins_p2) / nwins, 2)
    avg_score_losses = round((points_in_losses_p1 + points_in_losses_p2) / nlosses, 2)
    embed.set_footer(text=f'Average score: {avg_score}\nAverage score in wins: {avg_score_wins}\nAverage score in losses: {avg_score_losses}')
    ####

    del df_history
    return embed


async def get_stats_all(discord_id):
    user = await client.fetch_user(str(discord_id))
    df_history = pd.read_sql(f"select * from game_history where invalid=0 and (player1_id={discord_id} or player2_id={discord_id})", engine)
    ngames = len(df_history.index)
    embed = discord.Embed(color=0x70ac64)
    name = user.display_name
    embed.set_author(name=f'{name} all-time stats', icon_url=user.avatar_url)
    if ngames == 0:
        del df_history
        return embed

    nwins = len(df_history.loc[df_history['winner_id'] == discord_id].index)
    nlosses = ngames - nwins

    '''
    as_player1_sums = df_history.loc[df_history['player1_id'] == discord_id]['player1_score'].sum()
    as_player2_sums = df_history.loc[df_history['player2_id'] == discord_id]['player2_score'].sum()
    total_score = as_player1_sums + as_player2_sums

    as_player1_against_sums = df_history.loc[df_history['player1_id'] == discord_id]['player2_score'].sum()
    as_player2_against_sums = df_history.loc[df_history['player2_id'] == discord_id]['player1_score'].sum()
    total_score_against = as_player1_against_sums + as_player2_against_sums
    '''

    points_in_wins_p1 = df_history.loc[(df_history['winner_id'] == discord_id) & (df_history['player1_id'] == discord_id)]['player1_score'].sum()
    points_in_wins_p2 = df_history.loc[(df_history['winner_id'] == discord_id) & (df_history['player2_id'] == discord_id)]['player2_score'].sum()
    points_in_losses_p1 = df_history.loc[(df_history['winner_id'] != discord_id) & (df_history['player1_id'] == discord_id)]['player1_score'].sum()
    points_in_losses_p2 = df_history.loc[(df_history['winner_id'] != discord_id) & (df_history['player2_id'] == discord_id)]['player2_score'].sum()
    points_win = points_in_wins_p1 + points_in_wins_p2
    points_losses = points_in_losses_p1 + points_in_losses_p2
    total_points = points_win + points_losses

    points_against_in_wins_p1 = df_history.loc[(df_history['winner_id'] == discord_id) & (df_history['player1_id'] == discord_id)]['player2_score'].sum()
    points_against_in_wins_p2 = df_history.loc[(df_history['winner_id'] == discord_id) & (df_history['player2_id'] == discord_id)]['player1_score'].sum()
    points_against_in_losses_p1 = df_history.loc[(df_history['winner_id'] != discord_id) & (df_history['player1_id'] == discord_id)]['player2_score'].sum()
    points_against_in_losses_p2 = df_history.loc[(df_history['winner_id'] != discord_id) & (df_history['player2_id'] == discord_id)]['player1_score'].sum()
    points_against_win = points_against_in_wins_p1 + points_against_in_wins_p2
    points_against_losses = points_against_in_losses_p1 + points_against_in_losses_p2
    total_against_points = points_against_win + points_against_losses

    avg_score = round(total_points/ ngames, 2)
    avg_score_against = round(total_against_points / ngames, 2)
    avg_score_wins = round(points_win / nwins, 2)
    avg_score_wins_against = round(points_against_win / nwins, 2)
    avg_score_losses = round(points_losses / nlosses, 2)
    avg_score_losses_against = round(points_against_losses / nlosses, 2)


    embed.add_field(name="__Wins & Losses__", value=f'Wins: {nwins} -- Losses: {nlosses}', inline=False)
    embed.add_field(name="__Total scores__", value=f'Points scored: {total_points} -- Points scored on: {total_against_points}', inline=False)
    embed.add_field(name="__Average score__", value=f'Avg Score: {avg_score} -- Avg Score of Opponent: {avg_score_against}\nAvg Score in Wins: {avg_score_wins} -- Avg Opponent Score in Wins: {avg_score_wins_against}\nAvg Score in Losses: {avg_score_losses} -- Avg Opponent Score in Losses: {avg_score_losses_against}', inline=False)

    ####

    del df_history
    return embed



async def get_ladder(season):
    #df = pd.read_sql(f'select player_name, elo, wins, losses from `{season}` order by elo desc', engine)
    df = pd.read_sql(f'select row_number() over (order by elo desc, wins desc, losses asc) as rank, player_name, elo, wins, losses from `{season}`', engine)
    df.columns = ['Rank', 'Name', 'Elo', 'W', 'L']
    df['Rank'] = df['Rank'].astype(str) + '.'
    user = await client.fetch_user("1008939447439609907")
    cols = df.columns
    ar = df.to_numpy()
    out = ["{: <5} {: <30} {: <4} {: <4} {: <4}".format(*cols)]
    if len(df.index) == 0:
        out = out[0]
        embed = discord.Embed(color=0x70ac64, description=f"```{out}```")
        embed.set_author(name=f"{season} Ladder", icon_url=user.avatar_url)
        return embed
    for row in ar:
        out.append("{: <5} {: <30} {: <4} {: <4} {: <4}".format(*row))
    header, data = '\n'.join(out).split('\n', 1)

    embed = discord.Embed(color=0x70ac64, description=f"```yaml\n{header}``` ```\n{data}```")
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

async def recalc_season(season):
    db = await get_db()
    # channel = client.get_channel(1012172535678382080)
    cursor = db.cursor()
    cursor.execute(f'select gameid, player1_id, player2_id, winner_id, player1_score, player2_score from game_history where season=%s and invalid=0 order by game_date asc', (season,))
    games = cursor.fetchall()
    cursor.execute(f'truncate table `{season}`')
    for game in games:
        gameid, player1, player2, winner, player1_score, player2_score = list(game)
        p1 = winner
        if p1 != winner:
            p2 = player1
            p2_score = player1_score
            p1_score = player2_score
        else:
            p2 = player2
            p2_score = player2_score
            p1_score = player1_score
        # embed = await input_win(p1, p2, season, p1_score, p2_score, update=gameid)
        # await channel.send(embed=embed)
    cursor.close()

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
            channel = client.get_channel(1012172535678382080)
            await channel.send(embed=embed)

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
            channel = client.get_channel(1012172535678382080)
            await channel.send(embed=embed)

    if message.content.lower().startswith('.stats'):
        mentions = message.mentions
        if len(mentions) > 2:
            await message.channel.send('Can only mention one or two players.')
        elif len(mentions) == 2:
            player1 = str(mentions[0].id)
            player2 = str(mentions[1].id)
            embed = await get_versus_stats(player1, player2)
            if embed is None: await message.channel.send('No games played against each other.')
            else: await message.channel.send(embed=embed)
            return
        elif len(mentions) == 1:
            id = str(mentions[0].id)
        else:
            id = str(message.author.id)
        embed = await get_stats(id)
        if embed is None:
            await message.channel.send('No games played against each other.')
        else:
            await message.channel.send(embed=embed)

    if message.content.lower().startswith('.allstats'):
        mentions = message.mentions
        if len(mentions) > 2:
            await message.channel.send('Can only mention one or two players.')
        elif len(mentions) == 2:
            player1 = str(mentions[0].id)
            player2 = str(mentions[1].id)
            embed = await get_versus_stats_all(player1, player2)
            if embed is None: await message.channel.send('No games played against each other.')
            else: await message.channel.send(embed=embed)
            return
        elif len(mentions) == 1:
            id = str(mentions[0].id)
        else:
            id = str(message.author.id)
        embed = await get_stats_all(id)
        if embed is None:
            await message.channel.send('No games played against each other.')
        else:
            await message.channel.send(embed=embed)

    if message.content.lower().startswith('.history'):
        mentions = message.mentions
        if len(mentions) > 2:
            await message.channel.send('Can only mention one player.')
        elif len(mentions) == 2:
            player1 = str(mentions[0].id)
            player2 = str(mentions[1].id)
            embed = await get_history(player1, player2)
            await message.channel.send(embed=embed)
            return
        elif len(mentions) == 1:
            player1 = str(mentions[0].id)
        else:
            player1 = str(message.author.id)
        embed = await get_history(player1)
        await message.channel.send(embed=embed)


    if message.content.lower().startswith('.ladder') or message.content.lower().startswith('.leaderboard'):
        season = await get_current_ranked_season()
        embed = await get_ladder(season)
        await message.channel.send(embed=embed)

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
        if not auth_user:
            await message.channel.send('Not allowed to use this command.')
            return
        try:
            game_id = int(msg.lower().split('.invalidgame')[1].replace(" ", ""))
        except:
            await message.channel.send('Error reading input. Provide a game id number.')
            return

        result = await invalidate_game(game_id)
        await message.channel.send(result)


    if message.content.lower().startswith('.validgame'):
        if not auth_user:
            await message.channel.send('Not allowed to use this command.')
            return
        try:
            game_id = int(msg.lower().split('.validgame')[1].replace(" ", ""))
        except:
            await message.channel.send('Error reading input. Provide a game id number.')
            return

        result = await validate_game(game_id)
        await message.channel.send(result)

    if message.content.lower().startswith('.help'):
        embed = discord.Embed(title='Racquetbot Commands', color=0x70ac64)
        embed.add_field(name=".ranked",
                        value="Type .ranked followed by mentioning both players and the score.\nExample: .ranked @user1 @user2 11-6",
                        inline=True)
        embed.add_field(name=".normal or .unranked",
                        value="Type .normal or .unranked followed by mentioning both players and the score.\nExample: .normal @user1 @user2 11-6",
                        inline=True)
        embed.add_field(name=".stats",
                        value="Type .stats to view your statistics for the current season, or type .stats and @ someone else to view theirs.\nYou can also type .stats and mention 2 users to view their stats against each other.",
                        inline=True)
        embed.add_field(name=".allstats",
                        value="Type .allstats to view all statistics from all seasons, or type .allstats and @ someone else to view theirs.",
                        inline=True)
        embed.add_field(name=".history",
                        value="Type .history to view your game history, or type .history and @ someone else to view theirs.\nCan also mention two users to view their history against each other.",
                        inline=True)
        embed.add_field(name=".ladder or .leaderboard", value="Type .ladder or .leaderboard to view the ladder.", inline=True)
        await message.channel.send(embed=embed)

    if message.content.lower().startswith('.recalc'):
        season = await get_current_ranked_season()
        await message.channel.send('Recalculating.')
        await recalc_season(season)
        await message.channel.send('Games recalculated for current ranked season.')


# client.run(os.environ['TOKEN'])
TOKEN = open("/repo/discord_token.txt", "r").read()
client.run(TOKEN)
