import yfinance as yf
import pandas as pd
import numpy as np
import time
import itertools
import tweepy
import datetime
from datetime import date
from datetime import datetime
import calendar
import random
pd.options.mode.chained_assignment = None  # default='warn'

file_ymd = str(date.today().year) + str(date.today().month).zfill(2) + str(date.today().day).zfill(2)
text_ymd = str(date.today().year) + '-' + str(date.today().month).zfill(2) + '-' + str(date.today().day).zfill(2)

consumer_key = ''
consumer_secret = ''
access_token = ''
access_token_secret = ''
 
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(auth, wait_on_rate_limit = True)

today = pd.to_datetime(date.today())




##### first half of stocks (Export to Twitter, txt)

stock_list = ['AAPL', 'AMD', 'AMZN', 'CRM', 'CRSR', 'GOOG', 'INTC']
contrib_amt = [5.00, 5.00, 2.50, 1.25, 1.25, 2.50, 3.75]
trade_type = 'stock'
roll_days = 'quarter'
buyvalue = 1.2
multiplier = 5
segment_name = 'stock1'

# convert roll days into the proper number, with respect to stock/index vs crypto
roll_stock_index = {'month': 21, 'quarter': 65, '2_quarter': 130, 'year': 260}
roll_crypto = {'month': 30, 'quarter': 90, '2_quarter': 180, 'year': 365}
roll_dict = {'stock': roll_stock_index, 'index': roll_stock_index, 'crypto': roll_crypto}

roll_days = roll_dict[trade_type][roll_days]

### duplicate contrib_amt for all stocks if only 1 listed
if len(contrib_amt) == len(stock_list):
    pass
elif len(contrib_amt) == 1: 
    contrib_amt = [contrib_amt[0] for x in enumerate(stock_list)]
else:
    print('Incorrect length of contrib_amt. Make it match the length of the stock list or be 1 value')
    exit()

### pull most recent day
if trade_type == 'crypto' or trade_type == 'index':
    pass
else:
    x = 0
    while x < 1:
        df_now = yf.download(
        tickers = stock_list
        ,period = '1d' # set for 'today' instead
        ,interval = '1m'
        )

        # ensures a single stock can pass through, not just 2+ 
        if len(stock_list) == 1:
            df_now[stock_list[0]] = df_now['Open']
            df_now = df_now[[stock_list[0]]]
        else:
            df_now = df_now['Open']

        df_now = df_now.head(1) # open for today
        df_now = df_now.fillna(0)

        x = 1
        for i in stock_list:
            x = x * int(df_now[i])

        if x == 0: # wait 15 seconds if data aren't complete
            time.sleep(15)

# Overly complex way to pull data, but I have found that 'Open' prices are just a 
# copy of the previous day for the first few minutes of the trading day
# This method pulls in the true Open prices for today much quicker (a couple minutes after 6:30am PST)

if trade_type == 'crypto' or trade_type == 'index':
    df = yf.download(
        tickers = stock_list
        ,period = str(roll_days) + 'd'
    )

    # ensures a single crypto or index can pass through, not just 2+ 
    if len(stock_list) == 1:
        df[stock_list[0]] = df['Open']
        df = df[[stock_list[0]]]
    else:
        df = df['Open']
else:
    # Pull all data except for today
    df_bulk = yf.download(
            tickers = stock_list
            ,period = str(roll_days) + 'd'
        )

    # ensures a single stock can pass through, not just 2+ 
    if len(stock_list) == 1:
        df_bulk[stock_list[0]] = df_bulk['Open']
        df_bulk = df_bulk[[stock_list[0]]]
    else:
        df_bulk = df_bulk['Open']

    df_good_index = df_bulk.copy() # used to grab the ideal index
    df_bulk.drop(df_bulk.tail(1).index,inplace=True) # bulk w/o the most recent day

    # join the data (index is still bad)
    df = pd.concat([df_bulk, df_now])

    # sub in a good index
    df = df.reindex_like(df_good_index)

    # sub in good open data for today
    for i in stock_list:
        df[i][len(df)-1] = df_now[i].copy()
    

# add an index and useable date
df['Index'] = np.arange(1,len(df)+1)
df['date'] = df.index

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df['Index'].count()-df[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df[j]
    m, b = np.polyfit(x, y, 1)
    d = m*len(df[j])+b

    pred_open_list.append(d / df[j][len(df[j])-1] * d / df[j][len(df[j])-1])

multiplier_list = []
for i, j in enumerate(stock_list):
    if pred_open_list[i] > buyvalue:
        multiplier_list.append(1)
    else:
        multiplier_list.append(0)

final_buy_list = []
for i, j in enumerate(stock_list):
    if multiplier_list[i] == 0:
        final_buy_list.append(contrib_amt[i])
    else:
        final_buy_list.append(round(contrib_amt[i]*pred_open_list[i]*multiplier, 2))

final_df = pd.DataFrame()
final_df['stock'] = stock_list
final_df['buy_in_amt'] = final_buy_list
final_df['pred_open'] = pred_open_list

trade_day_date = df.tail(1)['date'].item().strftime('%Y.%m.%d')

stocks = []
for i, j, k, m in zip(stock_list, final_buy_list, pred_open_list, contrib_amt):
    if j == m:
        stocks.append(f'\n{i} ({round(k, 2)}): {j}')
    else:
        stocks.append(f'\n{i} ({round(k, 2)}): *{j}*')

file_ymdt = file_ymd + '_' + datetime.now().strftime('%H%M%S')
text_ymdt = text_ymd + ' ' + datetime.now().strftime('%H:%M:%S')

update = (f"{text_ymdt} ({calendar.day_name[date.today().weekday()]})\nRoll Hist Days = {roll_days}, Pred/Open^2 Threshold = {buyvalue}, Multiplier = {multiplier}\nStk (Pred/Open^2): Buy Value{(''.join(str(a) for a in stocks))}")

# exports
if df['date'][len(df)-1] == today:
    text_file = open(f'C:/Users/james/OneDrive/Desktop/Projects/twitter_bot/export/{segment_name}_{file_ymdt}.txt', 'w')
    text_file.write(update)
    text_file.close()

    api.update_status(update)

    print(f'{segment_name} complete')

else: print(f'{segment_name} not open (most recent date pull != today)')




##### second half of stocks (Export to Twitter, txt)

stock_list = ['MSFT', 'NVDA', 'QQQ', 'SBUX', 'SQ', 'TSLA', 'TSM']
contrib_amt = [2.50, 5.00, 2.50, 2.50, 2.50, 5.00, 3.75]
trade_type = 'stock'
roll_days = 'quarter'
buyvalue = 1.2
multiplier = 5
segment_name = 'stock2'

# convert roll days into the proper number, with respect to stock/index vs crypto
roll_stock_index = {'month': 21, 'quarter': 65, '2_quarter': 130, 'year': 260}
roll_crypto = {'month': 30, 'quarter': 90, '2_quarter': 180, 'year': 365}
roll_dict = {'stock': roll_stock_index, 'index': roll_stock_index, 'crypto': roll_crypto}

roll_days = roll_dict[trade_type][roll_days]

### duplicate contrib_amt for all stocks if only 1 listed
if len(contrib_amt) == len(stock_list):
    pass
elif len(contrib_amt) == 1: 
    contrib_amt = [contrib_amt[0] for x in enumerate(stock_list)]
else:
    print('Incorrect length of contrib_amt. Make it match the length of the stock list or be 1 value')
    exit()

### pull most recent day
if trade_type == 'crypto' or trade_type == 'index':
    pass
else:
    x = 0
    while x < 1:
        df_now = yf.download(
        tickers = stock_list
        ,period = '1d' # set for 'today' instead
        ,interval = '1m'
        )

        # ensures a single stock can pass through, not just 2+ 
        if len(stock_list) == 1:
            df_now[stock_list[0]] = df_now['Open']
            df_now = df_now[[stock_list[0]]]
        else:
            df_now = df_now['Open']

        df_now = df_now.head(1) # open for today
        df_now = df_now.fillna(0)

        x = 1
        for i in stock_list:
            x = x * int(df_now[i])

        if x == 0: # wait 15 seconds if data aren't complete
            time.sleep(15)

# Overly complex way to pull data, but I have found that 'Open' prices are just a 
# copy of the previous day for the first few minutes of the trading day
# This method pulls in the true Open prices for today much quicker (a couple minutes after 6:30am PST)

if trade_type == 'crypto' or trade_type == 'index':
    df = yf.download(
        tickers = stock_list
        ,period = str(roll_days) + 'd'
    )

    # ensures a single crypto or index can pass through, not just 2+ 
    if len(stock_list) == 1:
        df[stock_list[0]] = df['Open']
        df = df[[stock_list[0]]]
    else:
        df = df['Open']
else:
    # Pull all data except for today
    df_bulk = yf.download(
            tickers = stock_list
            ,period = str(roll_days) + 'd'
        )

    # ensures a single stock can pass through, not just 2+ 
    if len(stock_list) == 1:
        df_bulk[stock_list[0]] = df_bulk['Open']
        df_bulk = df_bulk[[stock_list[0]]]
    else:
        df_bulk = df_bulk['Open']

    df_good_index = df_bulk.copy() # used to grab the ideal index
    df_bulk.drop(df_bulk.tail(1).index,inplace=True) # bulk w/o the most recent day

    # join the data (index is still bad)
    df = pd.concat([df_bulk, df_now])

    # sub in a good index
    df = df.reindex_like(df_good_index)

    # sub in good open data for today
    for i in stock_list:
        df[i][len(df)-1] = df_now[i].copy()
    

# add an index and useable date
df['Index'] = np.arange(1,len(df)+1)
df['date'] = df.index

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df['Index'].count()-df[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df[j]
    m, b = np.polyfit(x, y, 1)
    d = m*len(df[j])+b

    pred_open_list.append(d / df[j][len(df[j])-1] * d / df[j][len(df[j])-1])

multiplier_list = []
for i, j in enumerate(stock_list):
    if pred_open_list[i] > buyvalue:
        multiplier_list.append(1)
    else:
        multiplier_list.append(0)

final_buy_list = []
for i, j in enumerate(stock_list):
    if multiplier_list[i] == 0:
        final_buy_list.append(contrib_amt[i])
    else:
        final_buy_list.append(round(contrib_amt[i]*pred_open_list[i]*multiplier, 2))

final_df = pd.DataFrame()
final_df['stock'] = stock_list
final_df['buy_in_amt'] = final_buy_list
final_df['pred_open'] = pred_open_list

trade_day_date = df.tail(1)['date'].item().strftime('%Y.%m.%d')

stocks = []
for i, j, k, m in zip(stock_list, final_buy_list, pred_open_list, contrib_amt):
    if j == m:
        stocks.append(f'\n{i} ({round(k, 2)}): {j}')
    else:
        stocks.append(f'\n{i} ({round(k, 2)}): *{j}*')

file_ymdt = file_ymd + '_' + datetime.now().strftime('%H%M%S')
text_ymdt = text_ymd + ' ' + datetime.now().strftime('%H:%M:%S')

update = (f"{text_ymdt} ({calendar.day_name[date.today().weekday()]})\nRoll Hist Days = {roll_days}, Pred/Open^2 Threshold = {buyvalue}, Multiplier = {multiplier}\nStk (Pred/Open^2): Buy Value{(''.join(str(a) for a in stocks))}")

# exports
if df['date'][len(df)-1] == today:
    text_file = open(f'C:/Users/james/OneDrive/Desktop/Projects/twitter_bot/export/{segment_name}_{file_ymdt}.txt', 'w')
    text_file.write(update)
    text_file.close()

    api.update_status(update)

    print(f'{segment_name} complete')

else: print(f'{segment_name} not open (most recent date pull != today)')




##### crypto (Export to Twitter, txt, xlsx)

# stock_list = ['BTC-USD', 'ETH-USD', 'DOGE-USD']
stock_list = ['BTC-USD', 'ETH-USD']
# contrib_amt = [25, 10, 5]
contrib_amt = [25, 20]
trade_type = 'crypto'
roll_days = 'quarter'
buyvalue = 1.2
multiplier = 3
segment_name = 'crypto'

# convert roll days into the proper number, with respect to stock/index vs crypto
roll_stock_index = {'month': 21, 'quarter': 65, '2_quarter': 130, 'year': 260}
roll_crypto = {'month': 30, 'quarter': 90, '2_quarter': 180, 'year': 365}
roll_dict = {'stock': roll_stock_index, 'index': roll_stock_index, 'crypto': roll_crypto}

roll_days = roll_dict[trade_type][roll_days]

### duplicate contrib_amt for all stocks if only 1 listed
if len(contrib_amt) == len(stock_list):
    pass
elif len(contrib_amt) == 1: 
    contrib_amt = [contrib_amt[0] for x in enumerate(stock_list)]
else:
    print('Incorrect length of contrib_amt. Make it match the length of the stock list or be 1 value')
    exit()

### pull most recent day
if trade_type == 'crypto' or trade_type == 'index':
    pass
else:
    x = 0
    while x < 1:
        df_now = yf.download(
        tickers = stock_list
        ,period = '1d' # set for 'today' instead
        ,interval = '1m'
        )

        # ensures a single stock can pass through, not just 2+ 
        if len(stock_list) == 1:
            df_now[stock_list[0]] = df_now['Open']
            df_now = df_now[[stock_list[0]]]
        else:
            df_now = df_now['Open']

        df_now = df_now.head(1) # open for today
        df_now = df_now.fillna(0)

        x = 1
        for i in stock_list:
            x = x * int(df_now[i])

        if x == 0: # wait 15 seconds if data aren't complete
            time.sleep(15)

# Overly complex way to pull data, but I have found that 'Open' prices are just a 
# copy of the previous day for the first few minutes of the trading day
# This method pulls in the true Open prices for today much quicker (a couple minutes after 6:30am PST)

if trade_type == 'crypto' or trade_type == 'index':
    df = yf.download(
        tickers = stock_list
        ,period = str(roll_days) + 'd'
    )

    # ensures a single crypto or index can pass through, not just 2+ 
    if len(stock_list) == 1:
        df[stock_list[0]] = df['Open']
        df = df[[stock_list[0]]]
    else:
        df = df['Open']
else:
    # Pull all data except for today
    df_bulk = yf.download(
            tickers = stock_list
            ,period = str(roll_days) + 'd'
        )

    # ensures a single stock can pass through, not just 2+ 
    if len(stock_list) == 1:
        df_bulk[stock_list[0]] = df_bulk['Open']
        df_bulk = df_bulk[[stock_list[0]]]
    else:
        df_bulk = df_bulk['Open']

    df_good_index = df_bulk.copy() # used to grab the ideal index
    df_bulk.drop(df_bulk.tail(1).index,inplace=True) # bulk w/o the most recent day

    # join the data (index is still bad)
    df = pd.concat([df_bulk, df_now])

    # sub in a good index
    df = df.reindex_like(df_good_index)

    # sub in good open data for today
    for i in stock_list:
        df[i][len(df)-1] = df_now[i].copy()
    

# add an index and useable date
df['Index'] = np.arange(1,len(df)+1)
df['date'] = df.index

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df['Index'].count()-df[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df[j]
    m, b = np.polyfit(x, y, 1)
    d = m*len(df[j])+b

    pred_open_list.append(d / df[j][len(df[j])-1] * d / df[j][len(df[j])-1])

multiplier_list = []
for i, j in enumerate(stock_list):
    if pred_open_list[i] > buyvalue:
        multiplier_list.append(1)
    else:
        multiplier_list.append(0)

final_buy_list = []
for i, j in enumerate(stock_list):
    if multiplier_list[i] == 0:
        final_buy_list.append(contrib_amt[i])
    else:
        final_buy_list.append(round(contrib_amt[i]*pred_open_list[i]*multiplier, 2))

final_df = pd.DataFrame()
final_df['stock'] = stock_list
final_df['buy_in_amt'] = final_buy_list
final_df['pred_open'] = pred_open_list

trade_day_date = df.tail(1)['date'].item().strftime('%Y.%m.%d')

stocks = []
for i, j, k, m in zip(stock_list, final_buy_list, pred_open_list, contrib_amt):
    if j == m:
        stocks.append(f'\n{i} ({round(k, 2)}): {j}')
    else:
        stocks.append(f'\n{i} ({round(k, 2)}): *{j}*')

file_ymdt = file_ymd + '_' + datetime.now().strftime('%H%M%S')
text_ymdt = text_ymd + ' ' + datetime.now().strftime('%H:%M:%S')

update = (f"{text_ymdt} ({calendar.day_name[date.today().weekday()]})\nRoll Hist Days = {roll_days}, Pred/Open^2 Threshold = {buyvalue}, Multiplier = {multiplier}\nStk (Pred/Open^2): Buy Value{(''.join(str(a) for a in stocks))}")

# exports
if df['date'][len(df)-1] == today:
    text_file = open(f'C:/Users/james/OneDrive/Desktop/Projects/twitter_bot/export/{segment_name}_{file_ymdt}.txt', 'w')
    text_file.write(update)
    text_file.close()

    final_df.to_excel(f'C:/Users/james/OneDrive/Desktop/Projects/twitter_bot/export/{segment_name}_{file_ymdt}.xlsx', index = False)

    api.update_status(update)

    print(f'{segment_name} complete')

else: print(f'{segment_name} not open (most recent date pull != today)')




##### all stocks (Export to xlsx)

stock_list = ['AAPL', 'AMD', 'AMZN', 'CRM', 'CRSR', 'GOOG', 'INTC', 'MSFT', 'NVDA', 'QQQ', 'SBUX', 'SQ', 'TSLA', 'TSM']
contrib_amt = [5.00, 5.00, 2.50, 1.25, 1.25, 2.50, 3.75, 2.50, 5.00, 2.50, 2.50, 2.50, 5.00, 3.75]
trade_type = 'stock'
roll_days = 'quarter'
buyvalue = 1.2
multiplier = 5
segment_name = 'stock_all'

# convert roll days into the proper number, with respect to stock/index vs crypto
roll_stock_index = {'month': 21, 'quarter': 65, '2_quarter': 130, 'year': 260}
roll_crypto = {'month': 30, 'quarter': 90, '2_quarter': 180, 'year': 365}
roll_dict = {'stock': roll_stock_index, 'index': roll_stock_index, 'crypto': roll_crypto}

roll_days = roll_dict[trade_type][roll_days]

### duplicate contrib_amt for all stocks if only 1 listed
if len(contrib_amt) == len(stock_list):
    pass
elif len(contrib_amt) == 1: 
    contrib_amt = [contrib_amt[0] for x in enumerate(stock_list)]
else:
    print('Incorrect length of contrib_amt. Make it match the length of the stock list or be 1 value')
    exit()

### pull most recent day
if trade_type == 'crypto' or trade_type == 'index':
    pass
else:
    x = 0
    while x < 1:
        df_now = yf.download(
        tickers = stock_list
        ,period = '1d' # set for 'today' instead
        ,interval = '1m'
        )

        # ensures a single stock can pass through, not just 2+ 
        if len(stock_list) == 1:
            df_now[stock_list[0]] = df_now['Open']
            df_now = df_now[[stock_list[0]]]
        else:
            df_now = df_now['Open']

        df_now = df_now.head(1) # open for today
        df_now = df_now.fillna(0)

        x = 1
        for i in stock_list:
            x = x * int(df_now[i])

        if x == 0: # wait 15 seconds if data aren't complete
            time.sleep(15)

# Overly complex way to pull data, but I have found that 'Open' prices are just a 
# copy of the previous day for the first few minutes of the trading day
# This method pulls in the true Open prices for today much quicker (a couple minutes after 6:30am PST)

if trade_type == 'crypto' or trade_type == 'index':
    df = yf.download(
        tickers = stock_list
        ,period = str(roll_days) + 'd'
    )

    # ensures a single crypto or index can pass through, not just 2+ 
    if len(stock_list) == 1:
        df[stock_list[0]] = df['Open']
        df = df[[stock_list[0]]]
    else:
        df = df['Open']
else:
    # Pull all data except for today
    df_bulk = yf.download(
            tickers = stock_list
            ,period = str(roll_days) + 'd'
        )

    # ensures a single stock can pass through, not just 2+ 
    if len(stock_list) == 1:
        df_bulk[stock_list[0]] = df_bulk['Open']
        df_bulk = df_bulk[[stock_list[0]]]
    else:
        df_bulk = df_bulk['Open']

    df_good_index = df_bulk.copy() # used to grab the ideal index
    df_bulk.drop(df_bulk.tail(1).index,inplace=True) # bulk w/o the most recent day

    # join the data (index is still bad)
    df = pd.concat([df_bulk, df_now])

    # sub in a good index
    df = df.reindex_like(df_good_index)

    # sub in good open data for today
    for i in stock_list:
        df[i][len(df)-1] = df_now[i].copy()
    

# add an index and useable date
df['Index'] = np.arange(1,len(df)+1)
df['date'] = df.index

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df['Index'].count()-df[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df[j]
    m, b = np.polyfit(x, y, 1)
    d = m*len(df[j])+b

    pred_open_list.append(d / df[j][len(df[j])-1] * d / df[j][len(df[j])-1])

multiplier_list = []
for i, j in enumerate(stock_list):
    if pred_open_list[i] > buyvalue:
        multiplier_list.append(1)
    else:
        multiplier_list.append(0)

final_buy_list = []
for i, j in enumerate(stock_list):
    if multiplier_list[i] == 0:
        final_buy_list.append(contrib_amt[i])
    else:
        final_buy_list.append(round(contrib_amt[i]*pred_open_list[i]*multiplier, 2))

final_df = pd.DataFrame()
final_df['stock'] = stock_list
final_df['buy_in_amt'] = final_buy_list
final_df['pred_open'] = pred_open_list

trade_day_date = df.tail(1)['date'].item().strftime('%Y.%m.%d')

stocks = []
for i, j, k, m in zip(stock_list, final_buy_list, pred_open_list, contrib_amt):
    if j == m:
        stocks.append(f'\n{i} ({round(k, 2)}): {j}')
    else:
        stocks.append(f'\n{i} ({round(k, 2)}): *{j}*')

file_ymdt = file_ymd + '_' + datetime.now().strftime('%H%M%S')
text_ymdt = text_ymd + ' ' + datetime.now().strftime('%H:%M:%S')

update = (f"{text_ymdt} ({calendar.day_name[date.today().weekday()]})\nRoll Hist Days = {roll_days}, Pred/Open^2 Threshold = {buyvalue}, Multiplier = {multiplier}\nStk (Pred/Open^2): Buy Value{(''.join(str(a) for a in stocks))}")

# exports
if df['date'][len(df)-1] == today:
    final_df.to_excel(f'C:/Users/james/OneDrive/Desktop/Projects/twitter_bot/export/{segment_name}_{file_ymdt}.xlsx', index = False)

    print(f'{segment_name} complete')

else: print(f'{segment_name} not open (most recent date pull != today)')











stock_list = ['VFIAX', 'VTIAX']
# stock_list = ['VTSAX', 'VFFVX']
# stock_list = ['AAPL', 'AMD', 'AMZN', 'CRM', 'GOOG', 'INTC', 'MSFT']
# stock_list = ['NVDA', 'QQQ', 'SBUX', 'SQ', 'TSLA', 'TSM']
# stock_list = ['BTC-USD', 'ETH-USD']

# contrib_amt = [350, 50, 100, 100]
contrib_amt = [5]

# trade_type = 'stock'
# trade_type = 'crypto'
trade_type = 'index'

# roll_days = 'month'
# roll_days = 'quarter'
# roll_days = '2_quarter'
roll_days = 'year'

# buyvalue = 1.2
# multiplier = 5
segment_name = 'slope - index 1'

# convert roll days into the proper number, with respect to stock/index vs crypto
roll_stock_index = {'month': 21, 'quarter': 65, '2_quarter': 130, 'year': 260}
roll_crypto = {'month': 30, 'quarter': 90, '2_quarter': 180, 'year': 365}
roll_dict = {'stock': roll_stock_index, 'index': roll_stock_index, 'crypto': roll_crypto}

month_len = roll_dict[trade_type]['month']
quarter_len = roll_dict[trade_type]['quarter']
two_quarter_len = roll_dict[trade_type]['2_quarter']
year_len = roll_dict[trade_type]['year']

roll_days = roll_dict[trade_type][roll_days]

if trade_type == 'crypto':
    round_digits = 4
else:
    round_digits = 4



### duplicate contrib_amt for all stocks if only 1 listed
if len(contrib_amt) == len(stock_list):
    pass
elif len(contrib_amt) == 1: 
    contrib_amt = [contrib_amt[0] for x in enumerate(stock_list)]
else:
    print('Incorrect length of contrib_amt. Make it match the length of the stock list or be 1 value')
    exit()

### pull most recent day
if trade_type == 'crypto' or trade_type == 'index':
    pass
else:
    x = 0
    while x < 1:
        df_now = yf.download(
        tickers = stock_list
        ,period = '1d' # set for 'today' instead
        ,interval = '1m'
        )

        # ensures a single stock can pass through, not just 2+ 
        if len(stock_list) == 1:
            df_now[stock_list[0]] = df_now['Open']
            df_now = df_now[[stock_list[0]]]
        else:
            df_now = df_now['Open']

        df_now = df_now.head(1) # open for today
        df_now = df_now.fillna(0)

        x = 1
        for i in stock_list:
            x = x * int(df_now[i])

        if x == 0: # wait 15 seconds if data aren't complete
            time.sleep(15)

# Overly complex way to pull data, but I have found that 'Open' prices are just a 
# copy of the previous day for the first few minutes of the trading day
# This method pulls in the true Open prices for today much quicker (a couple minutes after 6:30am PST)

if trade_type == 'crypto' or trade_type == 'index':
    df = yf.download(
        tickers = stock_list
        ,period = str(roll_days+1) + 'd'
    )

    # ensures a single crypto or index can pass through, not just 2+ 
    if len(stock_list) == 1:
        df[stock_list[0]] = df['Open']
        df = df[[stock_list[0]]]
    else:
        df = df['Open']
else:
    # Pull all data except for today
    df_bulk = yf.download(
            tickers = stock_list
            ,period = str(roll_days+1) + 'd'
        )

    # ensures a single stock can pass through, not just 2+ 
    if len(stock_list) == 1:
        df_bulk[stock_list[0]] = df_bulk['Open']
        df_bulk = df_bulk[[stock_list[0]]]
    else:
        df_bulk = df_bulk['Open']

    df_good_index = df_bulk.copy() # used to grab the ideal index
    df_bulk.drop(df_bulk.tail(1).index,inplace=True) # bulk w/o the most recent day

    # join the data (index is still bad)
    df = pd.concat([df_bulk, df_now])

    # sub in a good index
    df = df.reindex_like(df_good_index)

    # sub in good open data for today
    for i in stock_list:
        df[i][len(df)-1] = df_now[i].copy()
    

# add an index and useable date
df['date'] = df.index

for j in stock_list:
    df[j + ' norm'] = (df[j] - min(df[j]))/(max(df[j]) - min(df[j])) * 100
for j in stock_list:
    df[j] = df[j + ' norm']

df_today = df[1:].copy()
df_today['Index'] = np.arange(1,len(df_today)+1)

df_yesterday = df[:len(df)-1].copy()
df_yesterday['Index'] = np.arange(1,len(df_yesterday)+1)




### prep today data

df_260_today = df_today[len(df_today)-year_len:].copy()
df_130_today = df_today[len(df_today)-two_quarter_len:].copy()
df_65_today = df_today[len(df_today)-quarter_len:].copy()
df_21_today = df_today[len(df_today)-month_len:].copy()

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df_260_today[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df_260_today['Index'].count()-df_260_today[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df_260_today[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df_260_today[j]
    m, b = np.polyfit(x, y, 1)
    pred_open_list.append(round(m, round_digits))

df_260_today_slope = pd.DataFrame()
df_260_today_slope['stock'] = stock_list
df_260_today_slope['slope'] = pred_open_list
df_260_today_slope

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df_130_today[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df_130_today['Index'].count()-df_130_today[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df_130_today[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df_130_today[j]
    m, b = np.polyfit(x, y, 1)
    pred_open_list.append(round(m, round_digits))

df_130_today_slope = pd.DataFrame()
df_130_today_slope['stock'] = stock_list
df_130_today_slope['slope'] = pred_open_list
df_130_today_slope

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df_65_today[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df_65_today['Index'].count()-df_65_today[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df_65_today[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df_65_today[j]
    m, b = np.polyfit(x, y, 1)
    pred_open_list.append(round(m, round_digits))

df_65_today_slope = pd.DataFrame()
df_65_today_slope['stock'] = stock_list
df_65_today_slope['slope'] = pred_open_list
df_65_today_slope

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df_21_today[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df_21_today['Index'].count()-df_21_today[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df_21_today[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df_21_today[j]
    m, b = np.polyfit(x, y, 1)
    pred_open_list.append(round(m, round_digits))

df_21_today_slope = pd.DataFrame()
df_21_today_slope['stock'] = stock_list
df_21_today_slope['slope'] = pred_open_list
df_21_today_slope




### prep yesterday data
df_260_yesterday = df_yesterday[len(df_yesterday)-year_len:].copy()
df_130_yesterday = df_yesterday[len(df_yesterday)-two_quarter_len:].copy()
df_65_yesterday = df_yesterday[len(df_yesterday)-quarter_len:].copy()
df_21_yesterday = df_yesterday[len(df_yesterday)-month_len:].copy()

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df_260_yesterday[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df_260_yesterday['Index'].count()-df_260_yesterday[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df_260_yesterday[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df_260_yesterday[j]
    m, b = np.polyfit(x, y, 1)
    pred_open_list.append(round(m, round_digits))

df_260_yesterday_slope = pd.DataFrame()
df_260_yesterday_slope['stock'] = stock_list
df_260_yesterday_slope['slope'] = pred_open_list
df_260_yesterday_slope

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df_130_yesterday[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df_130_yesterday['Index'].count()-df_130_yesterday[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df_130_yesterday[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df_130_yesterday[j]
    m, b = np.polyfit(x, y, 1)
    pred_open_list.append(round(m, round_digits))

df_130_yesterday_slope = pd.DataFrame()
df_130_yesterday_slope['stock'] = stock_list
df_130_yesterday_slope['slope'] = pred_open_list
df_130_yesterday_slope

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df_65_yesterday[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df_65_yesterday['Index'].count()-df_65_yesterday[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df_65_yesterday[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df_65_yesterday[j]
    m, b = np.polyfit(x, y, 1)
    pred_open_list.append(round(m, round_digits))

df_65_yesterday_slope = pd.DataFrame()
df_65_yesterday_slope['stock'] = stock_list
df_65_yesterday_slope['slope'] = pred_open_list
df_65_yesterday_slope

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df_21_yesterday[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df_21_yesterday['Index'].count()-df_21_yesterday[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df_21_yesterday[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df_21_yesterday[j]
    m, b = np.polyfit(x, y, 1)
    pred_open_list.append(round(m, round_digits))

df_21_yesterday_slope = pd.DataFrame()
df_21_yesterday_slope['stock'] = stock_list
df_21_yesterday_slope['slope'] = pred_open_list
df_21_yesterday_slope



### form the final string

file_ymdt = file_ymd + '_' + datetime.now().strftime('%H%M%S')
text_ymdt = text_ymd + ' ' + datetime.now().strftime('%H:%M:%S')

final_print = []
for i, val21, val65, val130, val260, stk260, val21y, val65y, val130y, val260y in zip(range(len(df_21_today_slope)), df_21_today_slope['slope'], df_65_today_slope['slope'], df_130_today_slope['slope'], df_260_today_slope['slope'], df_260_today_slope['stock'], \
    df_21_yesterday_slope['slope'], df_65_yesterday_slope['slope'], df_130_yesterday_slope['slope'], df_260_yesterday_slope['slope']):
    # final_print.append(f"{stk260}: {val21y} > {val21}, {val65y} > {val65}, {val130y} > {val130}, {val260y} > {val260}\n")
    final_print.append(f"{stk260}\n{month_len}: {val21y} \u2192 {val21}\n{quarter_len}: {val65y} \u2192 {val65}\n{two_quarter_len}: {val130y} \u2192 {val130}\n{year_len}: {val260y} \u2192 {val260}\n")

update = (f"{text_ymdt} ({calendar.day_name[date.today().weekday()]})\nRolling Day Slopes (Prior \u2192 Current)\n{(''.join(str(a) for a in final_print))}")




# exports
if df['date'][len(df)-1] == today:
    # print(update)

    api.update_status(update)

    print(f'{segment_name} complete')

else: print(f'{segment_name} not open (most recent date pull != today)')













# stock_list = ['VFIAX', 'VTIAX']
stock_list = ['VTSAX', 'VFFVX']
# stock_list = ['AAPL', 'AMD', 'AMZN', 'CRM', 'GOOG', 'INTC', 'MSFT']
# stock_list = ['NVDA', 'QQQ', 'SBUX', 'SQ', 'TSLA', 'TSM']
# stock_list = ['BTC-USD', 'ETH-USD']

# contrib_amt = [350, 50, 100, 100]
contrib_amt = [5]

# trade_type = 'stock'
# trade_type = 'crypto'
trade_type = 'index'

# roll_days = 'month'
# roll_days = 'quarter'
# roll_days = '2_quarter'
roll_days = 'year'

# buyvalue = 1.2
# multiplier = 5
segment_name = 'slope - index 1'

# convert roll days into the proper number, with respect to stock/index vs crypto
roll_stock_index = {'month': 21, 'quarter': 65, '2_quarter': 130, 'year': 260}
roll_crypto = {'month': 30, 'quarter': 90, '2_quarter': 180, 'year': 365}
roll_dict = {'stock': roll_stock_index, 'index': roll_stock_index, 'crypto': roll_crypto}

month_len = roll_dict[trade_type]['month']
quarter_len = roll_dict[trade_type]['quarter']
two_quarter_len = roll_dict[trade_type]['2_quarter']
year_len = roll_dict[trade_type]['year']

roll_days = roll_dict[trade_type][roll_days]

if trade_type == 'crypto':
    round_digits = 4
else:
    round_digits = 4



### duplicate contrib_amt for all stocks if only 1 listed
if len(contrib_amt) == len(stock_list):
    pass
elif len(contrib_amt) == 1: 
    contrib_amt = [contrib_amt[0] for x in enumerate(stock_list)]
else:
    print('Incorrect length of contrib_amt. Make it match the length of the stock list or be 1 value')
    exit()

### pull most recent day
if trade_type == 'crypto' or trade_type == 'index':
    pass
else:
    x = 0
    while x < 1:
        df_now = yf.download(
        tickers = stock_list
        ,period = '1d' # set for 'today' instead
        ,interval = '1m'
        )

        # ensures a single stock can pass through, not just 2+ 
        if len(stock_list) == 1:
            df_now[stock_list[0]] = df_now['Open']
            df_now = df_now[[stock_list[0]]]
        else:
            df_now = df_now['Open']

        df_now = df_now.head(1) # open for today
        df_now = df_now.fillna(0)

        x = 1
        for i in stock_list:
            x = x * int(df_now[i])

        if x == 0: # wait 15 seconds if data aren't complete
            time.sleep(15)

# Overly complex way to pull data, but I have found that 'Open' prices are just a 
# copy of the previous day for the first few minutes of the trading day
# This method pulls in the true Open prices for today much quicker (a couple minutes after 6:30am PST)

if trade_type == 'crypto' or trade_type == 'index':
    df = yf.download(
        tickers = stock_list
        ,period = str(roll_days+1) + 'd'
    )

    # ensures a single crypto or index can pass through, not just 2+ 
    if len(stock_list) == 1:
        df[stock_list[0]] = df['Open']
        df = df[[stock_list[0]]]
    else:
        df = df['Open']
else:
    # Pull all data except for today
    df_bulk = yf.download(
            tickers = stock_list
            ,period = str(roll_days+1) + 'd'
        )

    # ensures a single stock can pass through, not just 2+ 
    if len(stock_list) == 1:
        df_bulk[stock_list[0]] = df_bulk['Open']
        df_bulk = df_bulk[[stock_list[0]]]
    else:
        df_bulk = df_bulk['Open']

    df_good_index = df_bulk.copy() # used to grab the ideal index
    df_bulk.drop(df_bulk.tail(1).index,inplace=True) # bulk w/o the most recent day

    # join the data (index is still bad)
    df = pd.concat([df_bulk, df_now])

    # sub in a good index
    df = df.reindex_like(df_good_index)

    # sub in good open data for today
    for i in stock_list:
        df[i][len(df)-1] = df_now[i].copy()
    

# add an index and useable date
df['date'] = df.index

for j in stock_list:
    df[j + ' norm'] = (df[j] - min(df[j]))/(max(df[j]) - min(df[j])) * 100
for j in stock_list:
    df[j] = df[j + ' norm']

df_today = df[1:].copy()
df_today['Index'] = np.arange(1,len(df_today)+1)

df_yesterday = df[:len(df)-1].copy()
df_yesterday['Index'] = np.arange(1,len(df_yesterday)+1)




### prep today data

df_260_today = df_today[len(df_today)-year_len:].copy()
df_130_today = df_today[len(df_today)-two_quarter_len:].copy()
df_65_today = df_today[len(df_today)-quarter_len:].copy()
df_21_today = df_today[len(df_today)-month_len:].copy()

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df_260_today[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df_260_today['Index'].count()-df_260_today[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df_260_today[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df_260_today[j]
    m, b = np.polyfit(x, y, 1)
    pred_open_list.append(round(m, round_digits))

df_260_today_slope = pd.DataFrame()
df_260_today_slope['stock'] = stock_list
df_260_today_slope['slope'] = pred_open_list
df_260_today_slope

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df_130_today[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df_130_today['Index'].count()-df_130_today[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df_130_today[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df_130_today[j]
    m, b = np.polyfit(x, y, 1)
    pred_open_list.append(round(m, round_digits))

df_130_today_slope = pd.DataFrame()
df_130_today_slope['stock'] = stock_list
df_130_today_slope['slope'] = pred_open_list
df_130_today_slope

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df_65_today[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df_65_today['Index'].count()-df_65_today[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df_65_today[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df_65_today[j]
    m, b = np.polyfit(x, y, 1)
    pred_open_list.append(round(m, round_digits))

df_65_today_slope = pd.DataFrame()
df_65_today_slope['stock'] = stock_list
df_65_today_slope['slope'] = pred_open_list
df_65_today_slope

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df_21_today[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df_21_today['Index'].count()-df_21_today[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df_21_today[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df_21_today[j]
    m, b = np.polyfit(x, y, 1)
    pred_open_list.append(round(m, round_digits))

df_21_today_slope = pd.DataFrame()
df_21_today_slope['stock'] = stock_list
df_21_today_slope['slope'] = pred_open_list
df_21_today_slope




### prep yesterday data
df_260_yesterday = df_yesterday[len(df_yesterday)-year_len:].copy()
df_130_yesterday = df_yesterday[len(df_yesterday)-two_quarter_len:].copy()
df_65_yesterday = df_yesterday[len(df_yesterday)-quarter_len:].copy()
df_21_yesterday = df_yesterday[len(df_yesterday)-month_len:].copy()

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df_260_yesterday[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df_260_yesterday['Index'].count()-df_260_yesterday[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df_260_yesterday[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df_260_yesterday[j]
    m, b = np.polyfit(x, y, 1)
    pred_open_list.append(round(m, round_digits))

df_260_yesterday_slope = pd.DataFrame()
df_260_yesterday_slope['stock'] = stock_list
df_260_yesterday_slope['slope'] = pred_open_list
df_260_yesterday_slope

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df_130_yesterday[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df_130_yesterday['Index'].count()-df_130_yesterday[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df_130_yesterday[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df_130_yesterday[j]
    m, b = np.polyfit(x, y, 1)
    pred_open_list.append(round(m, round_digits))

df_130_yesterday_slope = pd.DataFrame()
df_130_yesterday_slope['stock'] = stock_list
df_130_yesterday_slope['slope'] = pred_open_list
df_130_yesterday_slope

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df_65_yesterday[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df_65_yesterday['Index'].count()-df_65_yesterday[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df_65_yesterday[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df_65_yesterday[j]
    m, b = np.polyfit(x, y, 1)
    pred_open_list.append(round(m, round_digits))

df_65_yesterday_slope = pd.DataFrame()
df_65_yesterday_slope['stock'] = stock_list
df_65_yesterday_slope['slope'] = pred_open_list
df_65_yesterday_slope

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df_21_yesterday[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df_21_yesterday['Index'].count()-df_21_yesterday[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df_21_yesterday[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df_21_yesterday[j]
    m, b = np.polyfit(x, y, 1)
    pred_open_list.append(round(m, round_digits))

df_21_yesterday_slope = pd.DataFrame()
df_21_yesterday_slope['stock'] = stock_list
df_21_yesterday_slope['slope'] = pred_open_list
df_21_yesterday_slope



### form the final string

file_ymdt = file_ymd + '_' + datetime.now().strftime('%H%M%S')
text_ymdt = text_ymd + ' ' + datetime.now().strftime('%H:%M:%S')

final_print = []
for i, val21, val65, val130, val260, stk260, val21y, val65y, val130y, val260y in zip(range(len(df_21_today_slope)), df_21_today_slope['slope'], df_65_today_slope['slope'], df_130_today_slope['slope'], df_260_today_slope['slope'], df_260_today_slope['stock'], \
    df_21_yesterday_slope['slope'], df_65_yesterday_slope['slope'], df_130_yesterday_slope['slope'], df_260_yesterday_slope['slope']):
    # final_print.append(f"{stk260}: {val21y} > {val21}, {val65y} > {val65}, {val130y} > {val130}, {val260y} > {val260}\n")
    final_print.append(f"{stk260}\n{month_len}: {val21y} \u2192 {val21}\n{quarter_len}: {val65y} \u2192 {val65}\n{two_quarter_len}: {val130y} \u2192 {val130}\n{year_len}: {val260y} \u2192 {val260}\n")

update = (f"{text_ymdt} ({calendar.day_name[date.today().weekday()]})\nRolling Day Slopes (Prior \u2192 Current)\n{(''.join(str(a) for a in final_print))}")




# exports
if df['date'][len(df)-1] == today:
    # print(update)

    api.update_status(update)

    print(f'{segment_name} complete')

else: print(f'{segment_name} not open (most recent date pull != today)')













# stock_list = ['VFIAX', 'VTIAX']
# stock_list = ['VTSAX', 'VFFVX']
# stock_list = ['AAPL', 'AMD', 'AMZN', 'CRM', 'GOOG', 'INTC', 'MSFT']
# stock_list = ['NVDA', 'QQQ', 'SBUX', 'SQ', 'TSLA', 'TSM']
stock_list = ['BTC-USD', 'ETH-USD']

# contrib_amt = [350, 50, 100, 100]
contrib_amt = [5]

# trade_type = 'stock'
trade_type = 'crypto'
# trade_type = 'index'

# roll_days = 'month'
# roll_days = 'quarter'
# roll_days = '2_quarter'
roll_days = 'year'

# buyvalue = 1.2
# multiplier = 5
segment_name = 'slope - index 1'

# convert roll days into the proper number, with respect to stock/index vs crypto
roll_stock_index = {'month': 21, 'quarter': 65, '2_quarter': 130, 'year': 260}
roll_crypto = {'month': 30, 'quarter': 90, '2_quarter': 180, 'year': 365}
roll_dict = {'stock': roll_stock_index, 'index': roll_stock_index, 'crypto': roll_crypto}

month_len = roll_dict[trade_type]['month']
quarter_len = roll_dict[trade_type]['quarter']
two_quarter_len = roll_dict[trade_type]['2_quarter']
year_len = roll_dict[trade_type]['year']

roll_days = roll_dict[trade_type][roll_days]

if trade_type == 'crypto':
    round_digits = 4
else:
    round_digits = 4



### duplicate contrib_amt for all stocks if only 1 listed
if len(contrib_amt) == len(stock_list):
    pass
elif len(contrib_amt) == 1: 
    contrib_amt = [contrib_amt[0] for x in enumerate(stock_list)]
else:
    print('Incorrect length of contrib_amt. Make it match the length of the stock list or be 1 value')
    exit()

### pull most recent day
if trade_type == 'crypto' or trade_type == 'index':
    pass
else:
    x = 0
    while x < 1:
        df_now = yf.download(
        tickers = stock_list
        ,period = '1d' # set for 'today' instead
        ,interval = '1m'
        )

        # ensures a single stock can pass through, not just 2+ 
        if len(stock_list) == 1:
            df_now[stock_list[0]] = df_now['Open']
            df_now = df_now[[stock_list[0]]]
        else:
            df_now = df_now['Open']

        df_now = df_now.head(1) # open for today
        df_now = df_now.fillna(0)

        x = 1
        for i in stock_list:
            x = x * int(df_now[i])

        if x == 0: # wait 15 seconds if data aren't complete
            time.sleep(15)

# Overly complex way to pull data, but I have found that 'Open' prices are just a 
# copy of the previous day for the first few minutes of the trading day
# This method pulls in the true Open prices for today much quicker (a couple minutes after 6:30am PST)

if trade_type == 'crypto' or trade_type == 'index':
    df = yf.download(
        tickers = stock_list
        ,period = str(roll_days+1) + 'd'
    )

    # ensures a single crypto or index can pass through, not just 2+ 
    if len(stock_list) == 1:
        df[stock_list[0]] = df['Open']
        df = df[[stock_list[0]]]
    else:
        df = df['Open']
else:
    # Pull all data except for today
    df_bulk = yf.download(
            tickers = stock_list
            ,period = str(roll_days+1) + 'd'
        )

    # ensures a single stock can pass through, not just 2+ 
    if len(stock_list) == 1:
        df_bulk[stock_list[0]] = df_bulk['Open']
        df_bulk = df_bulk[[stock_list[0]]]
    else:
        df_bulk = df_bulk['Open']

    df_good_index = df_bulk.copy() # used to grab the ideal index
    df_bulk.drop(df_bulk.tail(1).index,inplace=True) # bulk w/o the most recent day

    # join the data (index is still bad)
    df = pd.concat([df_bulk, df_now])

    # sub in a good index
    df = df.reindex_like(df_good_index)

    # sub in good open data for today
    for i in stock_list:
        df[i][len(df)-1] = df_now[i].copy()
    

# add an index and useable date
df['date'] = df.index

for j in stock_list:
    df[j + ' norm'] = (df[j] - min(df[j]))/(max(df[j]) - min(df[j])) * 100
for j in stock_list:
    df[j] = df[j + ' norm']

df_today = df[1:].copy()
df_today['Index'] = np.arange(1,len(df_today)+1)

df_yesterday = df[:len(df)-1].copy()
df_yesterday['Index'] = np.arange(1,len(df_yesterday)+1)




### prep today data

df_260_today = df_today[len(df_today)-year_len:].copy()
df_130_today = df_today[len(df_today)-two_quarter_len:].copy()
df_65_today = df_today[len(df_today)-quarter_len:].copy()
df_21_today = df_today[len(df_today)-month_len:].copy()

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df_260_today[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df_260_today['Index'].count()-df_260_today[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df_260_today[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df_260_today[j]
    m, b = np.polyfit(x, y, 1)
    pred_open_list.append(round(m, round_digits))

df_260_today_slope = pd.DataFrame()
df_260_today_slope['stock'] = stock_list
df_260_today_slope['slope'] = pred_open_list
df_260_today_slope

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df_130_today[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df_130_today['Index'].count()-df_130_today[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df_130_today[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df_130_today[j]
    m, b = np.polyfit(x, y, 1)
    pred_open_list.append(round(m, round_digits))

df_130_today_slope = pd.DataFrame()
df_130_today_slope['stock'] = stock_list
df_130_today_slope['slope'] = pred_open_list
df_130_today_slope

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df_65_today[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df_65_today['Index'].count()-df_65_today[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df_65_today[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df_65_today[j]
    m, b = np.polyfit(x, y, 1)
    pred_open_list.append(round(m, round_digits))

df_65_today_slope = pd.DataFrame()
df_65_today_slope['stock'] = stock_list
df_65_today_slope['slope'] = pred_open_list
df_65_today_slope

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df_21_today[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df_21_today['Index'].count()-df_21_today[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df_21_today[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df_21_today[j]
    m, b = np.polyfit(x, y, 1)
    pred_open_list.append(round(m, round_digits))

df_21_today_slope = pd.DataFrame()
df_21_today_slope['stock'] = stock_list
df_21_today_slope['slope'] = pred_open_list
df_21_today_slope




### prep yesterday data
df_260_yesterday = df_yesterday[len(df_yesterday)-year_len:].copy()
df_130_yesterday = df_yesterday[len(df_yesterday)-two_quarter_len:].copy()
df_65_yesterday = df_yesterday[len(df_yesterday)-quarter_len:].copy()
df_21_yesterday = df_yesterday[len(df_yesterday)-month_len:].copy()

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df_260_yesterday[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df_260_yesterday['Index'].count()-df_260_yesterday[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df_260_yesterday[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df_260_yesterday[j]
    m, b = np.polyfit(x, y, 1)
    pred_open_list.append(round(m, round_digits))

df_260_yesterday_slope = pd.DataFrame()
df_260_yesterday_slope['stock'] = stock_list
df_260_yesterday_slope['slope'] = pred_open_list
df_260_yesterday_slope

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df_130_yesterday[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df_130_yesterday['Index'].count()-df_130_yesterday[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df_130_yesterday[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df_130_yesterday[j]
    m, b = np.polyfit(x, y, 1)
    pred_open_list.append(round(m, round_digits))

df_130_yesterday_slope = pd.DataFrame()
df_130_yesterday_slope['stock'] = stock_list
df_130_yesterday_slope['slope'] = pred_open_list
df_130_yesterday_slope

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df_65_yesterday[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df_65_yesterday['Index'].count()-df_65_yesterday[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df_65_yesterday[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df_65_yesterday[j]
    m, b = np.polyfit(x, y, 1)
    pred_open_list.append(round(m, round_digits))

df_65_yesterday_slope = pd.DataFrame()
df_65_yesterday_slope['stock'] = stock_list
df_65_yesterday_slope['slope'] = pred_open_list
df_65_yesterday_slope

# error checking, if a stock doesn't have enough history based on the current needs
nlist = []
for i in stock_list:
    if pd.isna(df_21_yesterday[i].iloc[0]) == True:
        nlist.append(i)

if len(nlist) >0:
    print('Stocks with not enough history', nlist)
    for j in nlist:
        print(j, 'missing days:', df_21_yesterday['Index'].count()-df_21_yesterday[j].count())
    exit() # Maybe not the best to add this. I still want to see the data

# create pred and pred/open list for each of the n dataframes
pred_open_list = []
for j in stock_list:
    x = range(1,len(df_21_yesterday[j])+1) # range must be 1-roll_days, not the auto implied 0-(roll_days-1)
    y = df_21_yesterday[j]
    m, b = np.polyfit(x, y, 1)
    pred_open_list.append(round(m, round_digits))

df_21_yesterday_slope = pd.DataFrame()
df_21_yesterday_slope['stock'] = stock_list
df_21_yesterday_slope['slope'] = pred_open_list
df_21_yesterday_slope



### form the final string

file_ymdt = file_ymd + '_' + datetime.now().strftime('%H%M%S')
text_ymdt = text_ymd + ' ' + datetime.now().strftime('%H:%M:%S')

final_print = []
for i, val21, val65, val130, val260, stk260, val21y, val65y, val130y, val260y in zip(range(len(df_21_today_slope)), df_21_today_slope['slope'], df_65_today_slope['slope'], df_130_today_slope['slope'], df_260_today_slope['slope'], df_260_today_slope['stock'], \
    df_21_yesterday_slope['slope'], df_65_yesterday_slope['slope'], df_130_yesterday_slope['slope'], df_260_yesterday_slope['slope']):
    # final_print.append(f"{stk260}: {val21y} > {val21}, {val65y} > {val65}, {val130y} > {val130}, {val260y} > {val260}\n")
    final_print.append(f"{stk260}\n{month_len}: {val21y} \u2192 {val21}\n{quarter_len}: {val65y} \u2192 {val65}\n{two_quarter_len}: {val130y} \u2192 {val130}\n{year_len}: {val260y} \u2192 {val260}\n")

update = (f"{text_ymdt} ({calendar.day_name[date.today().weekday()]})\nRolling Day Slopes (Prior \u2192 Current)\n{(''.join(str(a) for a in final_print))}")




# exports
if df['date'][len(df)-1] == today:
    # print(update)

    api.update_status(update)

    print(f'{segment_name} complete')

else: print(f'{segment_name} not open (most recent date pull != today)')













today = pd.to_datetime(date.today())
base_food_day = pd.to_datetime('2022-6-9')
base_recycle_day = pd.to_datetime('2022-6-2')

message = ''
if (today - base_food_day).days % 14 == 0:
    message = 'Reminder: Put out food waste for tomorrow pickup'
    print(message)
if (today - base_recycle_day).days % 14 == 0:
    message = 'Reminder: Put out recycling for tomorrow pickup'
    print(message)

if len(message) > 0:
    api.update_status(message)











