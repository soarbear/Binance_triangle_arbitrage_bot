# -*- coding: utf-8 -*-
from collections import defaultdict
from operator import itemgetter
from time import time, sleep
from binance.client import Client
import datetime
import itchat

PRIMARY = ['ETH', 'USDT', 'BTC'] # BNB excluded in advance
BASEPOINT = 'BTC' # the base point(first point) of triangle
FEE = 0.0005 # if you have BNB assets, otherwise FEE = 0.0010
BEPOINT = 1.0000 # break even point you can upgrade, ex. 1.0010 = 1.0% profit
EXCEPTION = 1
NORMAL = 0
#
# trade according to found triangle that makes the best profit over BEPOINT
#
def main():
    itchat.auto_login()
    api_key = '*****'
    api_secret = '*****'
    client = Client(api_key, api_secret)
    loop_count = 0
    triangle_count = 0
    exinfo = get_exinfo(client)
#   print(f"exinfo:{exinfo}")
    while(True):
        start_time = time()
        prices = get_prices(client)
#       print(f"prices:{prices}")
        prices_time = time()
        download_time = prices_time-start_time
        if (download_time > 0.5):
            print(f"Downloaded in {download_time:.4f}s, Sleep 2s...")
            sleep(2)
            continue
        else:
            print(f"Downloaded in: {prices_time-start_time:.4f}s")
        triangles = list(find_triangles(prices))
        computing_time = time()
        print(f"Computed in: {computing_time-prices_time:.4f}s")
        if triangles:
            sorted(triangles, key=itemgetter('profit'), reverse=True)
            triangle = triangles[0]
            triangle['coins'].reverse()
            coins = triangle['coins']
            describe_triangle(prices, coins, triangle)
            status = NORMAL
            for i_coin in range(len(coins)-1):
                base_coin = coins[i_coin]
                quote_coin = coins[i_coin+1]
                symb = base_coin+quote_coin
                symb_info = exinfo[symb]
                side = symb_info['side']
                tick = symb_info['tick']
                colm = symb_info['colm']
                pair = symb_info['pair']
                asset = 0.0
                price = prices[base_coin][quote_coin]
                try:
                    while (asset < 0.01):
                        asset = float(client.get_asset_balance(asset=base_coin)['free'])
                        if asset < 0.01:
                            sleep(0.1)
                        else:
                            break
                    if side == 'BUY':
                        asset = asset*price
                        sprice = f"{ceiling(1.0/price, tick):.8f}"
                    else:
                        sprice = f"{price:.8f}"
                    quan = ceiling(asset, colm)
                    print(f"sym:{symb},bas:{base_coin},{side},tic:{tick},col:{colm},ass:{asset:.4f},qua:{quan},pri:{sprice}")
                    order = client.create_test_order(symbol=pair, side=side, type='LIMIT', quantity=quan, price=sprice)
#                   order = client.order_limit(symbol=pair, side=side, quantity=quan, price=sprice)
#                   order = client.order_market(symbol=pair, side=side, quantity=quan)
                except Exception as ex:
                    print(f"exception:{ex}")
                    print(f"break at tri_count:{triangle_count}! as symbol:{symb}")
                    status = EXCEPTION
                    break
            if status == EXCEPTION:
                print(f"[info]tri_count #{triangle_count} failed in {time()-computing_time:.4f}s@{datetime.datetime.today()}")
                break
            else:
                print(f"[info]tri_count #{triangle_count} succeeded in {time()-computing_time:.4f}s@{datetime.datetime.today()}")
            triangle_count = triangle_count + 1
        else:
            sleep(0.2)
        loop_count += 1
    print(f"tri_count/loop_count:{triangle_count}/{loop_count}")
    itchat.send('[info]exception:tri_count/loop_count:'+str(triangle_count)+'/'+str(loop_count), toUserName='filehelper')
#
# prepare exchange information
#
def get_exinfo(client):
    exinfo = defaultdict(dict)
    tickers = client.get_exchange_info()
    for ticker in tickers['symbols']:
        tick = list(filter(lambda f: f['filterType'] == 'PRICE_FILTER', ticker['filters']))[0]['tickSize']
        step = list(filter(lambda f: f['filterType'] == 'LOT_SIZE', ticker['filters']))[0]['stepSize']
        pair = ticker['symbol']
        for primary in PRIMARY:
            if pair.endswith(primary):
                reverse = primary + pair[:-len(primary)]
                exinfo[pair]['side'] = 'SELL'
                exinfo[pair]['colm'] = float(round(1.0 / float(step)))
                exinfo[pair]['pair'] = pair
                exinfo[pair]['tick'] = float(round(1.0/float(tick)))
                exinfo[reverse]['side'] = 'BUY'
                exinfo[reverse]['colm'] = float(round(1.0 / float(step)))
                exinfo[reverse]['pair'] = pair
                exinfo[reverse]['tick'] = float(round(1.0/float(tick)))
    return exinfo
#
# prepare prices of ask & bid
#    
def get_prices(client):
    prices = client.get_orderbook_tickers()
    prepared = defaultdict(dict)
    for ticker in prices:
        pair = ticker['symbol']
        ask = float(ticker['askPrice'])
        bid = float(ticker['bidPrice'])
        for primary in PRIMARY:
            secondary = pair[:-len(primary)]
            if pair.endswith(primary) and secondary != 'BNB':
                prepared[primary][secondary] = 1/ask
                prepared[secondary][primary] = bid
    return prepared
#
# look for triangle that makes profit over BEPOINT
#    
def find_triangles(prices):
    triangles = []
    starting_coin = BASEPOINT
    for triangle in recurse_triangle(prices, starting_coin, starting_coin):
        coins = set(triangle['coins'])
        if not any(prev_triangle == coins for prev_triangle in triangles):
            yield triangle
            triangles.append(coins)
#
# calculate profit & look for triangle through recursion
# 
def recurse_triangle(prices, current_coin, starting_coin, depth_left=3, amount=1.0):
    if depth_left > 0:
        pairs = prices[current_coin]
        for coin, price in pairs.items():
            new_price = (amount*price)*(1.0-FEE)
            for triangle in recurse_triangle(prices, coin, starting_coin, depth_left-1, new_price):
                triangle['coins'] = triangle['coins']+[current_coin]
                yield triangle
    elif current_coin == starting_coin and amount > BEPOINT:
        yield {
            'coins': [current_coin],
            'profit': amount
        }
#
# print triangle
#
def describe_triangle(prices, coins, triangle):
    price_percentage = (triangle['profit']-1.0) * 100
    print(f"{'->'.join(coins):26} {round(price_percentage, 4):-10}% <- profit!")
    for i in range(len(coins)-1):
        first = coins[i]
        second = coins[i+1]
        print(f"     {first:4} -> {second:4} : {prices[first][second]:-17.8f}")
#
# calculate ceiling of float
#
def ceiling(src, colum):
    return float(int(src*colum)/colum)

if __name__ == '__main__':
    main()
