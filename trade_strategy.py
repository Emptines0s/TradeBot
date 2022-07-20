import talib as ta
from decimal import Decimal
from math import floor, log10


class Strategy:
    def __init__(self, ticker, position):
        self.ticker = ticker
        self.buy = False
        self.sell = False
        self.buy_price = float('inf')
        self.sell_price = 0
        self.sell_stop = float('inf')
        self.buy_stop = 0
        self.quant = 1
        self.position = position

    # Финальный метод в котором происходит подсчёт всех индикаторов, и принятие торговых решений по совакупности
    # их показателей
    def strategy(self, data, data_global, data_btc):
        buy_points = 0
        sell_points = 0
        buy_points, sell_points = self.RSI(data, buy_points, sell_points)
        buy_points, sell_points = self.EMA(data, buy_points, sell_points)
        buy_points, sell_points = self.ADX(data, buy_points, sell_points)
        buy_points, sell_points = self.AD(data, buy_points, sell_points)
        result, quantity = self.trade(data, data_global, data_btc, buy_points, sell_points)
        return result, quantity, buy_points, sell_points

    # Ставит стоп, проводит расчёт количества монет для покупки (x$ / цена монеты)
    def long(self, data, up_trand):
        self.buy = True
        self.buy_price = data.iloc[-1]['Close']

        if up_trand is False:
            self.buy_stop = data.iloc[-1]['Low'] * 0.986
        else:
            self.buy_stop = 0

        dirty_quant = Decimal(self.position) / Decimal(self.buy_price)
        self.quant = Decimal(round(dirty_quant, -int(floor(log10(abs(dirty_quant))))))
        self.quant = Decimal('{:f}'.format(self.quant))
        print(f'BUY:\nticker {self.ticker}\nbuy price {self.buy_price}\nquant {self.quant}\nbuy stop {self.buy_stop}')
        result = 'buy'
        return result, self.quant

    # Ставит стоп, проводит расчёт количества монет для покупки (x$ / цена монеты)
    def short(self, data, down_trand):
        self.sell = True
        self.sell_price = data.iloc[-1]['Close']

        if down_trand is False:
            self.sell_stop = data.iloc[-1]['High'] * 1.014
        else:
            self.sell_stop = float('inf')

        dirty_quant = Decimal(self.position) / Decimal(self.sell_price)
        self.quant = Decimal(round(dirty_quant, -int(floor(log10(abs(dirty_quant))))))
        self.quant = Decimal('{:f}'.format(self.quant))
        print(f'SELL:\nticker {self.ticker}\nsell price {self.sell_price}\nquant {self.quant}\nsell stop {self.sell_stop}')
        result = 'sell'
        return result, self.quant

    # Считает сколько нужно закрыть или ДО закрыть, если сделка закрылась частично
    def close(self):
        if self.buy:
            self.buy = False
            if self.buy_stop > self.buy_price:
                half_quant = self.quant - Decimal(round(self.quant / 2, -int(floor(log10(abs(self.quant / 2))))))
                half_quant = Decimal('{:f}'.format(half_quant))
            else:
                half_quant = self.quant
            if half_quant > 0:
                result = 'sell'
                return result, half_quant

        elif self.sell:
            self.sell = False
            if self.sell_stop < self.sell_price:
                half_quant = self.quant - Decimal(round(self.quant / 2, -int(floor(log10(abs(self.quant / 2))))))
                half_quant = Decimal('{:f}'.format(half_quant))
            elif self.sell_stop >= self.sell_price:
                half_quant = self.quant
            if half_quant > 0:
                result = 'buy'
                return result, half_quant

    # Обрабатывает логику принятия торговых решений ботом в зависимости от поступивших показателей от индикаторов
    # результат работы метода имеет следующий формат: (тип сделки/None, количество монет/None)
    def trade(self, data, data_global, data_btc, buy_points, sell_points):
        data_global['ADX'] = ta.ADX(data_global['High'], data_global['Low'], data_global['Close'], 14)
        data_global = data_global.astype({'ADX': float})
        data_global['minusDI'] = ta.MINUS_DI(data_global['High'], data_global['Low'], data_global['Close'], 14)
        data_global = data_global.astype({'minusDI': float})
        data_global['plusDI'] = ta.PLUS_DI(data_global['High'], data_global['Low'], data_global['Close'], 14)
        data_global = data_global.astype({'plusDI': float})

        data['Volatility'] = abs(data['Open'].diff())
        data = data.astype({'Volatility': float})
        data['Delta'] = data['Close'].diff()
        data = data.astype({'Delta': float})

        # Определение глобального тренда и изменение параметров в зависимости от него
        up_trand = False
        down_trand = False
        if data_global.iloc[-2]['ADX'] > data_global.iloc[-3]['ADX'] > data_global.iloc[-4]['ADX']: # Усиление тренда
            if data_global.iloc[-2]['minusDI'] > data_global.iloc[-2]['plusDI'] \
                    and data_global.iloc[-2]['minusDI'] - data_global.iloc[-2]['plusDI'] >= 10:
                down_trand = True
            elif data_global.iloc[-2]['minusDI'] < data_global.iloc[-2]['plusDI'] \
                    and data_global.iloc[-2]['plusDI'] - data_global.iloc[-2]['minusDI'] >= 10:
                up_trand = True

        elif data_global.iloc[-2]['ADX'] < data_global.iloc[-3]['ADX'] < data_global.iloc[-4]['ADX']: # Затухание тренда
            if data_global.iloc[-2]['minusDI'] > data_global.iloc[-2]['plusDI'] \
                    and data_global.iloc[-2]['minusDI'] - data_global.iloc[-2]['plusDI'] >= 10:
                up_trand = True
            elif data_global.iloc[-2]['minusDI'] < data_global.iloc[-2]['plusDI'] \
                    and data_global.iloc[-2]['plusDI'] - data_global.iloc[-2]['minusDI'] >= 10:
                down_trand = True

        if down_trand is True:
            sell_diff = 5
            buy_diff = 8

        elif up_trand is True:
            buy_diff = 5
            sell_diff = 8
        else:
            buy_diff = 7
            sell_diff = 7

        # Определение волатильности монеты и логика поведения связанная с ней
        mean_volatility = float(data.iloc[-20:]['Volatility'].mean())
        last_delta = data.iloc[-1]['Delta']
        penult_delta = data.iloc[-2]['Delta']

        if abs(last_delta) > abs(penult_delta) * 2.3 and last_delta < 0 and penult_delta > 0:
            sell_points += 2

        elif abs(last_delta) > abs(penult_delta) * 2.3 and last_delta > 0 and penult_delta < 0:
            buy_points += 2

        data_btc['Volatility'] = abs(data_btc['Open'].diff())
        data_btc['Delta'] = data_btc['Close'].diff()
        data_btc = data_btc.astype({'Delta': float})

        # Определение волатильности биткоина (Как бенчмарка криптовалюты) и логика поведения связанная с ней
        btc_volatility = float(data_btc.iloc[-20:]['Volatility'].mean())
        btc_last_delta = data_btc.iloc[-1]['Delta']
        btc_penult_delta = data_btc.iloc[-2]['Delta']

        if buy_points - sell_points >= buy_diff and self.buy is False:
            if abs(last_delta) > mean_volatility * 3 or abs(penult_delta) > mean_volatility * 3 \
                    or abs(btc_last_delta) > btc_volatility * 2.5 or abs(btc_penult_delta) > btc_volatility * 2.5:
                if not (last_delta < 0 or penult_delta < 0 or btc_last_delta < 0 or btc_penult_delta < 0) \
                        and up_trand is False:
                    if data.iloc[-30:-2]['Low'].min() * 0.994 < data.iloc[-1]['Close'] \
                            < data.iloc[-30:-2]['Low'].min() * 1.006:
                        result, quantity = self.long(data, up_trand)
                        return result, quantity
                else:
                    result, quantity = self.long(data, up_trand)
                    return result, quantity
            elif up_trand is False:
                if data.iloc[-30:-2]['Low'].min() * 0.994 < data.iloc[-1]['Close'] \
                        < data.iloc[-30:-2]['Low'].min() * 1.006:
                    result, quantity = self.long(data, up_trand)
                    return result, quantity
            else:
                result, quantity = self.long(data, up_trand)
                return result, quantity
        elif sell_points - buy_points >= sell_diff and self.sell is False:
            if abs(last_delta) > mean_volatility * 3 or abs(penult_delta) > mean_volatility * 3 \
                    or abs(btc_last_delta) > btc_volatility * 2.5 or abs(btc_penult_delta) > btc_volatility * 2.5:
                if not (last_delta > 0 or penult_delta > 0 or btc_last_delta > 0 or btc_penult_delta > 0) \
                        and down_trand is False:
                    if data.iloc[-30:-2]['High'].max() * 1.006 > data.iloc[-1]['Close'] \
                            > data.iloc[-30:-2]['High'].max() * 0.994:
                        result, quantity = self.short(data, down_trand)
                        return result, quantity
                else:
                    result, quantity = self.short(data, down_trand)
                    return result, quantity
            elif down_trand is False:
                if data.iloc[-30:-2]['High'].max() * 1.006 > data.iloc[-1]['Close'] \
                        > data.iloc[-30:-2]['High'].max() * 0.994:
                    result, quantity = self.short(data, down_trand)
                    return result, quantity
            else:
                result, quantity = self.short(data, down_trand)
                return result, quantity

        if self.buy:
            if abs(btc_last_delta) > btc_volatility * 5 or abs(btc_penult_delta) > btc_volatility * 5 \
                    and (btc_last_delta < 0 or btc_penult_delta < 0):
                result, quantity = self.close()
                return result, quantity
            elif self.buy_stop < self.buy_price and data.iloc[-1]['Close'] >= 1.008 * self.buy_price:
                self.buy_stop = self.buy_price * 1.002
                half_quant = Decimal(round(self.quant / 2, -int(floor(log10(abs(self.quant / 2))))))
                half_quant = Decimal('{:f}'.format(half_quant))
                result = 'sell'
                return result, half_quant

            for i in range(10, 200, 10):
                if data.iloc[-1]['Close'] >= self.buy_price * (1 + i / 1000) and \
                        self.buy_price * (1 + i / 1000 - 0.01) > self.buy_stop >= \
                        self.buy_price * (1 + i / 1000 - 0.02):
                    self.buy_stop = self.buy_price * (1 + i / 1000 - 0.01)

            if data.iloc[-1]['Close'] <= self.buy_stop or buy_points - sell_points < -1:
                result, quantity = self.close()
                return result, quantity

        if self.sell:
            if abs(btc_last_delta) > btc_volatility * 5 or abs(btc_penult_delta) > btc_volatility * 5 \
                    and btc_last_delta > 0 or btc_penult_delta > 0:
                result, quantity = self.close()
                return result, quantity
            elif self.sell_stop > self.sell_price and data.iloc[-1]['Close'] <= 0.992 * self.sell_price:
                self.sell_stop = self.sell_price * 0.998
                half_quant = Decimal(round(self.quant / 2, -int(floor(log10(abs(self.quant / 2))))))
                half_quant = Decimal('{:f}'.format(half_quant))
                result = 'buy'
                return result, half_quant

            for i in range(10, 200, 10):
                if data.iloc[-1]['Close'] <= self.sell_price * (1 - i / 1000) and \
                        self.sell_price * (1 - i / 1000 + 0.01) < self.sell_stop <= \
                        self.sell_price * (1 - i / 1000 + 0.02):
                    self.sell_stop = self.sell_price * (1 - i / 1000 + 0.01)

            if data.iloc[-1]['Close'] >= self.sell_stop or sell_points - buy_points < -1:
                result, quantity = self.close()
                return result, quantity
        return None, None

    def RSI(self, data, buy_points, sell_points):
        rsi_range = 14.0
        rsi_high = 70.0
        rsi_low = 30.0
        
        data['RSI'] = ta.RSI(data['Close'], timeperiod=rsi_range)
        current_value = float(data.iloc[-1]['RSI'])

        if current_value > rsi_high:
            sell_points = + 1
        elif current_value < rsi_low:
            buy_points += 1
        if current_value > rsi_high + 10:
            sell_points += 1
        elif current_value < rsi_low - 10:
            buy_points += 1

        if data.iloc[-80:-40]['RSI'].max() > data.iloc[-39:-1]['RSI'].max() \
                and data.iloc[-80:-40]['High'].max() < data.iloc[-39:-1]['High'].max() \
                and data.iloc[-1]['Close'] > 0.98 * data.iloc[-39:-1]['High'].max():
            sell_points += 1.5

        elif data.iloc[-60:-30]['RSI'].max() > data.iloc[-29:-1]['RSI'].max() \
                and data.iloc[-60:-30]['High'].max() < data.iloc[-29:-1]['High'].max() \
                and data.iloc[-1]['Close'] > 0.98 * data.iloc[-29:-1]['High'].max():
            sell_points += 1

        elif data.iloc[-20:-10]['RSI'].max() > data.iloc[-9:-1]['RSI'].max() \
                and data.iloc[-20:-10]['High'].max() < data.iloc[-9:-1]['High'].max() \
                and data.iloc[-1]['Close'] > 0.98 * data.iloc[-9:-1]['High'].max():
            sell_points += 0.5

        if data.iloc[-80:-40]['RSI'].min() < data.iloc[-39:-1]['RSI'].min() \
                and data.iloc[-80:-40]['Low'].max() > data.iloc[-39:-1]['Low'].min() \
                and data.iloc[-1]['Close'] < 1.02 * data.iloc[-39:-1]['Low'].min():
            buy_points += 1.5

        elif data.iloc[-60:-30]['RSI'].min() < data.iloc[-29:-1]['RSI'].min() \
                and data.iloc[-60:-30]['Low'].max() > data.iloc[-29:-1]['Low'].min() \
                and data.iloc[-1]['Close'] < 1.02 * data.iloc[-29:-1]['Low'].min():
            buy_points += 1

        elif data.iloc[-20:-10]['RSI'].min() < data.iloc[-9:-1]['RSI'].min() \
                and data.iloc[-20:-10]['Low'].max() > data.iloc[-9:-1]['Low'].min() \
                and data.iloc[-1]['Close'] < 1.02 * data.iloc[-9:-1]['Low'].min():
            buy_points += 0.5

        return buy_points, sell_points

    def EMA(self, data, buy_points, sell_points):
        data['EMA_20'] = ta.EMA(data['Close'], timeperiod=20)
        data = data.astype({'EMA_20': float})
        data['EMA_50'] = ta.EMA(data['Close'], timeperiod=50)
        data = data.astype({'EMA_20': float})

        if 1.005 * data.iloc[-1]['EMA_50'] > data.iloc[-1]['Open'] > 0.995 * data.iloc[-1]['EMA_50']:
            if data.iloc[-2]['Open'] > data.iloc[-2]['EMA_50'] and data.iloc[-3]['Open'] > data.iloc[-3]['EMA_50']:
                buy_points += 1.5
            elif data.iloc[-2]['Open'] < data.iloc[-2]['EMA_50'] and data.iloc[-3]['Open'] < data.iloc[-3]['EMA_50']:
                buy_points += 1.5

        elif 1.005 * data.iloc[-1]['EMA_20'] > data.iloc[-1]['Open'] > 0.995 * data.iloc[-1]['EMA_20']:
            if data.iloc[-2]['Open'] > data.iloc[-2]['EMA_20'] and data.iloc[-3]['Open'] > data.iloc[-3]['EMA_20']:
                sell_points += 0.75
            elif data.iloc[-2]['Open'] < data.iloc[-2]['EMA_20'] and data.iloc[-3]['Open'] < data.iloc[-3]['EMA_20']:
                sell_points += 0.75

        if data.iloc[-30:-4]['Low'].min() * 1.006 > data.iloc[-1]['Close'] > data.iloc[-30:-4]['Low'].min() * 0.994:
            buy_points += 1
        elif data.iloc[-30:-4]['High'].max() * 1.006 > data.iloc[-1]['Close'] > data.iloc[-30:-4]['High'].max() * 0.994:
            sell_points += 1

        return buy_points, sell_points

    def ADX(self, data, buy_points, sell_points):
        data['ADX'] = ta.ADX(data['High'], data['Low'], data['Close'], 14)
        data = data.astype({'ADX': float})
        data['minusDI'] = ta.MINUS_DI(data['High'], data['Low'], data['Close'], 14)
        data = data.astype({'minusDI': float})
        data['plusDI'] = ta.PLUS_DI(data['High'], data['Low'], data['Close'], 14)
        data = data.astype({'plusDI': float})

        if data.iloc[-2]['minusDI'] > data.iloc[-2]['plusDI'] \
                and data.iloc[-1]['minusDI'] < data.iloc[-1]['plusDI'] \
                and data.iloc[-5]['minusDI'] - data.iloc[-5]['plusDI'] >= 10 \
                and data.iloc[-1]['ADX'] < data.iloc[-2]['ADX']:
            buy_points += 3

        elif data.iloc[-3]['minusDI'] > data.iloc[-3]['plusDI'] \
                and data.iloc[-2]['minusDI'] < data.iloc[-2]['plusDI'] \
                and data.iloc[-6]['minusDI'] - data.iloc[-6]['plusDI'] >= 10 \
                and data.iloc[-1]['ADX'] < data.iloc[-2]['ADX']:
            buy_points += 3

        elif data.iloc[-2]['minusDI'] < data.iloc[-2]['plusDI'] and data.iloc[-1]['minusDI'] > data.iloc[-1]['plusDI'] \
                and data.iloc[-5]['plusDI'] - data.iloc[-5]['minusDI'] >= 10 \
                and data.iloc[-1]['ADX'] < data.iloc[-2]['ADX']:
            sell_points += 3

        elif data.iloc[-3]['minusDI'] < data.iloc[-3]['plusDI'] \
                and data.iloc[-2]['minusDI'] > data.iloc[-2]['plusDI'] \
                and data.iloc[-6]['plusDI'] - data.iloc[-6]['minusDI'] >= 10 \
                and data.iloc[-1]['ADX'] < data.iloc[-2]['ADX']:
            sell_points += 3

        if (data.iloc[-2]['minusDI'] - data.iloc[-2]['plusDI']) < (data.iloc[-1]['minusDI'] - data.iloc[-1]['plusDI']) \
                and data.iloc[-1]['ADX'] > data.iloc[-2]['ADX']:
            if data.iloc[-1]['minusDI'] > data.iloc[-1]['plusDI']:
                sell_points += 3
            elif data.iloc[-1]['minusDI'] < data.iloc[-1]['plusDI']:
                buy_points += 3

        return buy_points, sell_points

    def AD(self, data, buy_points, sell_points):
        data['AD'] = ta.ADOSC(data['High'], data['Low'], data['Close'], data['Volume'])
        data = data.astype({'AD': float})
        filtered_data = data[(data['AD']) > data['AD'].max() / 20]

        if data.iloc[-2]['AD'] > 0 and data.iloc[-3]['AD'] < 0:
            for row in data.iloc[-10:-2]['AD']:
                if row < -abs(filtered_data['AD'].mean()):
                    buy_points += 3
                    break

        if data.iloc[-2]['AD'] < 0 and data.iloc[-3]['AD'] > 0:
            for row in data.iloc[-10:-2]['AD']:
                if row > abs(filtered_data['AD'].mean()):
                    sell_points += 3
                    break

        return buy_points, sell_points
