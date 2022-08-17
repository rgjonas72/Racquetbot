Skip to content
Search or jump to…
Pull requests
Issues
Marketplace
Explore
 
@rgjonas72 
rgjonas72
/
Racquetbot
Public
Code
Issues
Pull requests
Actions
Projects
Wiki
Security
Insights
Settings
Racquetbot
/
main.py
in
main
 

Spaces

4

No wrap
1
# Rank 1 role
2
​
3
# 1200 elo start, 500 for shitter
4
​
5
# log score, avg point differential, winrate vs player, point dif vs player
6
​
7
# rated, unrated queue
8
​
9
import discord
10
import os
11
import math
12
import mysql.connector
13
​
14
mydb = mysql.connector.connect(
15
    host = "localhost",
16
    user = "racquetbot",
17
    password = "racquet",
18
    database = "racquetbot"
19
)
20
​
21
mydb.autocommit = True
22
cursor = mydb.cursor()
23
​
24
​
25
async def Probability(rating1, rating2):
26
    return 1.0 * 1.0 / (1 + 1.0 * math.pow(10, 1.0 * (rating1 - rating2) / 400))
27
​
28
​
29
# Function to calculate Elo rating
30
# K is a constant.
31
# d determines whether
32
# Player A wins or Player B.
33
async def EloRating(winner, loser, queue, K=5):
34
    winner_db_string = await get_db_string(winner, queue)
35
    loser_db_string = await get_db_string(loser, queue)
36
    # Ra for winner, Rb for loser
37
    ###Ra = db[winner_db_string][1]
38
    ###Rb = db[loser_db_string][1]
39
​
40
    # To calculate the Winning
41
    # Probability of Player B
42
    Pb = await Probability(Ra, Rb)
43
​
44
    # To calculate the Winning
45
    # Probability of Player A
@rgjonas72
Commit changes
Commit summary
Create main.py
Optional extended description
Add an optional extended description…
 Commit directly to the main branch.
 Create a new branch for this commit and start a pull request. Learn more about pull requests.
 
Footer
© 2022 GitHub, Inc.
Footer navigation
Terms
Privacy
Security
Status
Docs
Contact GitHub
Pricing
API
Training
Blog
About
You have no unread notifications
