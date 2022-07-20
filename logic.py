import asyncio
import queue
import threading

from binance_client import BinanceClient
from trade_strategy import Strategy
from database import Database
import database as db

# Очередь для передачи сигналов от графического интерфейса
q_signal = queue.Queue()

# Очередь для передачи данных о свечах в графический интерфейс
q_data = queue.Queue()

# Событие для блокировки окна входа пока ожидается ответ об успехе авторизации
event = threading.Event()

# Объект класса БД для взаимодействия с БД
database = Database()
database.create_tables()


# Цикл обработки логики программы
async def logic(api_key, api_secret):
    client = BinanceClient(api_key=api_key, api_secret=api_secret)
    try:
        await client.client_connection()  # Подключение к аккаунту
        await client.client.get_account()  # Проверка подключения
    except Exception as e:
        print(e)
        q_signal.put('authorization failed')
    else:
        q_signal.put('authorization successed')

        event.wait()

        trade_tasks = []
        while True:
            if not q_signal.empty():
                signal = q_signal.get()
                if signal['header'] == 'start ts':
                    strategy_task = asyncio.create_task(strategy(client,
                                                                 signal['body'][2],
                                                                 signal['body'][3],
                                                                 signal['body'][0],))
                    trade_tasks.append([strategy_task, signal['body'][0]])
                if signal['header'] == 'stop ts':
                    for task in reversed(trade_tasks):
                        if task[1] == signal['body']:
                            task[0].cancel()
                            trade_tasks.remove(task)
                if signal['header'] == 'get candlestick':
                    candlestick_task = asyncio.create_task(return_candlestick(client, signal['body']))
                if signal['header'] == 'exit':
                    break
            await asyncio.sleep(0)

    await client.client_close_connection()


# Передаёт в поток с интерфейсом данные по цене монеты для графика за последний час
async def return_candlestick(client, symbol):
    candlestick = await client.get_candlestick(symbol, '1m', '1 hour ago UTC')
    q_data.put(candlestick)


# Мета логика для торговой стратегии (создание вебсокетов, получение исторических данных для анализа,
# получение новых данных, обновление данных, анализ данных, и открытие ордеров по результатам анализа данных)
async def strategy(client, symbol, position, strategy_id):
    new_strategy = Strategy(symbol, position)
    symbol_ks = client.create_kline_socket(symbol, '1h')
    global_ks = client.create_kline_socket(symbol, '4h')
    btc_ks = client.create_kline_socket('BTCUSDT', '1h')

    data_stack = await asyncio.gather(client.get_candlestick(symbol, '1h', '3 day ago UTC'),
                                      client.get_candlestick(symbol, '4h', '4 day ago UTC'),
                                      client.get_candlestick(symbol, '1h', '3 day week ago UTC'))

    while True:
        new_data_stack = await asyncio.gather(client.socket_listener(symbol_ks),
                                              client.socket_listener(global_ks),
                                              client.socket_listener(btc_ks))
        for i in range(len(data_stack)):
            data_stack[i] = update_data(data_stack[i], new_data_stack[i])
        result = new_strategy.strategy(data_stack[0], data_stack[1], data_stack[2])
        print(f"{result} {symbol}")
        if result[0] == 'buy':
            client.futures_change_leverage(symbol=symbol, leverage=20)
            order = await client.futures_create_order(
                symbol=symbol,
                side=client.SIDE_BUY,
                type=client.FUTURE_ORDER_TYPE_MARKET,
                quantity=result[1])
            database.add_data(db.Trade(trade_type=order['side'],
                                       trade_price=order['price'],
                                       trade_quantity=order['origQty'],
                                       strategy_id=strategy_id))
        elif result[0] == 'sell':
            client.futures_change_leverage(symbol=symbol, leverage=20)
            order = await client.futures_create_order(
                symbol=symbol,
                side=client.SIDE_SELL,
                type=client.FUTURE_ORDER_TYPE_MARKET,
                quantity=result[1])
            database.add_data(db.Trade(trade_type=order['side'],
                                       trade_price=order['price'],
                                       trade_quantity=order['origQty'],
                                       strategy_id=strategy_id))


# Формирует новый датафрэйм из старых данных и новых, нужен для того, чтобы всегда был актуальный набор исторических
# данных для анализа
def update_data(data, new_data):
    if data['Date'].max() == new_data['Date'].max():
        data.drop(index=data.index[-1], inplace=True)
        data = data.append(new_data, ignore_index=True)
        return data
    else:
        data.drop(index=0, inplace=True)
        data = data.append(new_data, ignore_index=True)
        return data
