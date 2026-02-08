
import requests
import pandas as pd
import time
from datetime import datetime, timedelta

BASE_URL = "https://api.bitkub.com"

class BitkubService:
    def __init__(self):
        self.base_url = BASE_URL

    def get_symbols(self):
        """
        Fetch all available symbols from Bitkub
        returns: list of dictionaries containing symbol info
        """
        try:
            url = f"{self.base_url}/api/v3/market/symbols"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            if data['error'] == 0:
                return data['result']
            else:
                print(f"Error fetching symbols: {data['error']}")
                return []
        except Exception as e:
            print(f"Exception fetching symbols: {e}")
            return []

    def get_ticker(self, symbol=None):
        """
        Fetch ticker data.
        If symbol is provided, returns ticker for that symbol.
        Otherwise returns all tickers.
        """
        try:
            url = f"{self.base_url}/api/v3/market/ticker"
            params = {}
            if symbol:
                params['sym'] = symbol
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Exception fetching ticker: {e}")
            return None

    def get_recent_trades(self, symbol, limit=20):
        """
        Fetch recent trades for a symbol
        """
        try:
            url = f"{self.base_url}/api/v3/market/trades"
            params = {
                'sym': symbol,
                'lmt': limit
            }
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if data['error'] == 0:
                return data['result']
            else: 
                return []
        except Exception as e:
            print(f"Exception fetching trades: {e}")
            return []

    def get_candles(self, symbol, timeframe='1D', limit=100, start_timestamp=None, end_timestamp=None):
        """
        Fetch historical candle data (OHLC) for charting
        timeframe: '1D', '1H', etc. needs mapping to resolution seconds or string for API
        Bitkub /tradingview/history API uses:
        symbol: e.g. BTC_THB
        resolution: 1, 5, 15, 60, 240, 1D
        from: timestamp
        to: timestamp
        """
        try:
            # Resolution mapping
            res_map = {
                '1m': '1',
                '5m': '5',
                '15m': '15',
                '1h': '60',
                '4h': '240',
                '1D': '1D'
            }
            resolution = res_map.get(timeframe, '1D')
            
            # Calculate from/to timestamps
            if start_timestamp and end_timestamp:
                from_timestamp = start_timestamp
                to_timestamp = end_timestamp
            else:
                # For 1D, fetch enough data for indicators (e.g. 200 days for EMA200)
                now = datetime.now()
                
                # Default to fetching enough data for EMA200 + buffer
                # If timeframe is minutes, we need less days but enough candles
                if timeframe == '1D':
                    start_time = now - timedelta(days=limit + 200) 
                elif timeframe == '1h':
                    start_time = now - timedelta(hours=limit + 200)
                else:
                     start_time = now - timedelta(days=30) # Default fallback

                to_timestamp = int(now.timestamp())
                from_timestamp = int(start_time.timestamp())

            url = f"{self.base_url}/tradingview/history"
            params = {
                'symbol': symbol,
                'resolution': resolution,
                'from': from_timestamp,
                'to': to_timestamp
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            response = requests.get(url, params=params, headers=headers)
            print(f"Debug: Requesting {response.url}")
            response.raise_for_status()
            data = response.json()
            
            if data['s'] == 'ok':
                df = pd.DataFrame({
                    'timestamp': data['t'],
                    'open': data['o'],
                    'high': data['h'],
                    'low': data['l'],
                    'close': data['c'],
                    'volume': data['v']
                })
                # Convert timestamp to datetime
                df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
                return df
            else:
                print(f"Debug: API returned status '{data.get('s')}' for {symbol}")
                print(f"Debug: Full response: {data}")
                return pd.DataFrame() # Return empty if no data or error
                
        except Exception as e:
            print(f"Exception fetching candles: {e}")
            return pd.DataFrame()
