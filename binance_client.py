import pandas as pd
from binance import AsyncClient, BinanceSocketManager


class BinanceClient:
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.kline_socket_list = []

    async def client_connection(self):
        self.client = await AsyncClient.create(api_key=self.api_key, api_secret=self.api_secret)
        self.bm = BinanceSocketManager(self.client)

    async def client_close_connection(self):
        await self.client.close_connection()

    def create_trade_socket(self, symbol):
        ts = self.bm.trade_socket(symbol=symbol)
        return ts

    def create_kline_socket(self, symbol, interval):
        for socket in self.kline_socket_list:
            if socket[1] == symbol and socket[2] == interval:
                return socket[0]
        ks = self.bm.kline_socket(symbol=symbol, interval=interval)
        self.kline_socket_list.append([ks, symbol, interval])
        return ks

    def create_depth_socket(self, symbol, depth, interval):
        fs = self.bm.depth_socket(symbol=symbol, depth=depth, interval=interval)
        return fs

    async def get_candlestick(self, symbol, interval, start, end=None):
        data = await self.client.get_historical_klines(symbol=symbol,
                                                       interval=interval,
                                                       start_str=start,
                                                       end_str=end)
        df = pd.DataFrame(data=data).iloc[:, :6]
        df.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        df['Date'] = pd.to_datetime(df['Date'], unit='ms')
        for column in df.columns[1:]:
            df[column] = pd.to_numeric(df[column])
        return df

    @staticmethod
    async def socket_listener(socket):
        async with socket:
            data = await socket.recv()
            df = pd.DataFrame(data=[data.get('k')]).loc[:, ['t', 'o', 'h', 'l', 'c', 'v']]
            df.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            df['Date'] = pd.to_datetime(df['Date'], unit='ms')
            for column in df.columns[1:]:
                df[column] = pd.to_numeric(df[column])
            return df

    def __del__(self):
        print(f'Client {self.api_key} deleted!')
