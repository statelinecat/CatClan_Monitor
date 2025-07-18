from binance.client import Client
from config import Config
import pandas as pd
from datetime import datetime, timedelta


class BinanceAPI:
    def __init__(self):
        self.client = Client(Config.BINANCE_API_KEY, Config.BINANCE_API_SECRET)

    def get_current_balance(self):
        """Получение текущего спотового баланса"""
        try:
            account = self.client.get_account()
            balances = []
            for balance in account['balances']:
                free = float(balance['free'])
                locked = float(balance['locked'])
                if free > 0 or locked > 0:
                    balances.append({
                        'asset': balance['asset'],
                        'free': free,
                        'locked': locked,
                        'total': free + locked
                    })
            return balances
        except Exception as e:
            print(f"Error getting spot balance: {e}")
            return []

    def get_futures_balance(self):
        """Получение фьючерсного баланса с проверкой полей"""
        try:
            futures_account = self.client.futures_account_balance()
            for balance in futures_account:
                if balance['asset'] == 'USDT':
                    return [{
                        'asset': 'USDT',
                        'balance': float(balance.get('balance', 0)),
                        'available': float(balance.get('withdrawAvailable', balance.get('balance', 0)))
                    }]
            return []
        except Exception as e:
            print(f"Error getting futures balance: {e}")
            return []

    def get_futures_positions(self):
        """Получение открытых позиций с защитой от отсутствия полей"""
        try:
            positions = self.client.futures_position_information()
            prices = {symbol['symbol']: float(symbol['markPrice'])
                      for symbol in self.client.futures_mark_price()}

            valid_positions = []
            for pos in positions:
                try:
                    amount = float(pos.get('positionAmt', 0))
                    if amount == 0:
                        continue

                    symbol = pos['symbol']
                    mark_price = prices.get(symbol, 0)
                    entry_price = float(pos.get('entryPrice', 0))
                    usdt_value = abs(amount) * mark_price
                    leverage = float(pos.get('leverage', 1))
                    unrealized = float(pos.get('unRealizedProfit', 0))

                    valid_positions.append({
                        'symbol': symbol,
                        'positionAmt': amount,
                        'positionSide': pos.get('positionSide', 'BOTH'),
                        'unRealizedProfit': unrealized,
                        'entryPrice': entry_price,
                        'markPrice': mark_price,
                        'usdtValue': usdt_value,
                        'roe': (unrealized / (abs(amount) * entry_price)) * 100 if entry_price and amount else 0,
                        'leverage': int(leverage) if leverage else 1
                    })
                except (ValueError, KeyError) as e:
                    print(f"Skipping position {pos.get('symbol')} due to error: {e}")
                    continue

            return valid_positions
        except Exception as e:
            print(f"Error getting futures positions: {e}")
            return []

    def get_historical_prices(self, symbol, days=30):
        """Получение исторических цен"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            klines = self.client.futures_klines(
                symbol=symbol,
                interval=Client.KLINE_INTERVAL_1DAY,
                start_str=start_date.strftime("%Y-%m-%d"),
                end_str=end_date.strftime("%Y-%m-%d")
            )

            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades',
                'taker_buy_volume', 'taker_buy_quote_volume', 'ignore'
            ])

            df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['close'] = pd.to_numeric(df['close'])

            return df[['date', 'close']]
        except Exception as e:
            print(f"Error getting historical prices: {e}")
            return pd.DataFrame()