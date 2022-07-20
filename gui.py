import sys

import pyqtgraph
from PyQt5.QtWidgets import QApplication, QWidget, QTableWidgetItem, QMainWindow
from PyQt5.uic import loadUi
from PyQt5 import QtGui
from PyQt5.QtCore import QTimer, Qt, QSize
from pyqtgraph import PlotWidget, plot

from logic import *


# Окно формы входа
class LoginWindow(QWidget):
    def __init__(self):
        super(LoginWindow, self).__init__()

        loadUi('gui/login_window.ui', self)

        self.pushButton.clicked.connect(self.authorization)
        self.setFixedSize(300, 325)

        self.show()

    # Процессе авторизации происходит проверка сединения,
    # запись о новом  клиенте создаётся в БД если это первая авторизация
    def authorization(self):
        api_key = self.lineEdit_api.text()
        api_secret = self.lineEdit_secret.text()
        event.clear()
        logic_thread = threading.Thread(target=lambda func: asyncio.run(func), args=(logic(api_key, api_secret),),
                                        daemon=True)
        logic_thread.start()
        while True:
            signal = q_signal.get()
            if signal == 'authorization failed':
                break
            if signal == 'authorization successed':
                self.close()
                user = database.get_data(db.Client.client_id,
                                         attribute=db.Client.client_key,
                                         value=api_key)
                if len(user) == 0:
                    database.add_data([db.Client(client_key=api_key)])
                    user = database.get_data(db.Client.client_id,
                                             attribute=db.Client.client_key,
                                             value=api_key)
                self.main_window = MainWindow(client_id=user[0]['client_id'])
                break

        event.set()


# Главное окно
class MainWindow(QMainWindow):
    def __init__(self, client_id):
        super(MainWindow, self).__init__()

        loadUi('gui/main_window.ui', self)

        self.client_id = client_id
        self.current_strategy = None
        self.current_pair = None
        self.load_user_strategies()

        self.pushButton_save.clicked.connect(self.save_user_strategy)
        self.pushButton_delete.clicked.connect(self.delete_user_strategy)
        self.pushButton_create.clicked.connect(self.add_user_strategy)
        self.pushButton_test.clicked.connect(self.open_trade_logs)

        # График цены и сделок
        self.graphWidget = PlotWidget()
        self.graphWidget.setBackground(QtGui.QColor(24, 73, 107))
        self.graphWidget.showGrid(x=True, y=True)
        self.verticalLayout_core.addWidget(self.graphWidget)
        pen = pyqtgraph.mkPen(color=(43, 118, 171), width=4, style=Qt.SolidLine)
        self.historical_data = self.graphWidget.plot(pen=pen)

        # Обновление графика через сигнал таймера (тик 1 секунда)
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_plot)
        self.timer.start()

        self.show()

    def update_plot(self):
        if self.current_pair is not None:
            q_signal.put({'header': 'get candlestick', 'body': self.current_pair})
        if not q_data.empty():
            data = q_data.get()
            self.historical_data.setData([row for row in range(len(data.index))], data['Close'])

    def open_trade_logs(self):
        self.logs_window = LogsWindow(self.current_strategy)

    # В метода ниже реализованная функциональная часть главного окна:
    # создание торговой стратегии, обновление, удаление, сохранение изменений, тригеры событий при её выборе, и запуск
    def load_user_strategies(self):
        user_strategies = database.get_data(db.Strategy.strategy_id,
                                            db.Strategy.strategy_pair,
                                            db.Strategy.strategy_name,
                                            db.Strategy.strategy_pnl,
                                            db.Strategy.strategy_position,
                                            db.Strategy.is_active,
                                            attribute=db.Strategy.client_id,
                                            value=self.client_id)
        for i in reversed(range(self.verticalLayout_pair.count())):
            self.verticalLayout_pair.itemAt(i).widget().deleteLater()

        for i, row in enumerate(user_strategies):
            new_strategy = StrategyWidget(info=row, parent=self)
            self.verticalLayout_pair.addWidget(new_strategy, i)

    def add_user_strategy(self):
        self.choose_user_strategy(None, None)

    def save_user_strategy(self):
        pair = self.lineEdit_pair.text()
        position = self.lineEdit_position.text()
        strategy = self.comboBox_strategy.currentText()
        if pair and position:
            if self.current_strategy is None:
                database.add_data([db.Strategy(strategy_pair=pair,
                                               strategy_name=strategy,
                                               strategy_pnl=0,
                                               strategy_position=position,
                                               is_active=False,
                                               client_id=self.client_id)])
            else:
                database.update_data(table=db.Strategy,
                                     attribute=db.Strategy.strategy_id,
                                     value=self.current_strategy,
                                     update_values={'strategy_pair': pair,
                                                    'strategy_name': strategy,
                                                    'strategy_position': position})
        self.load_user_strategies()
        self.choose_user_strategy(self.current_strategy, pair)

    def delete_user_strategy(self):
        database.delete_data(table=db.Strategy,
                             attribute=db.Strategy.strategy_id,
                             value=self.current_strategy)
        self.load_user_strategies()
        self.choose_user_strategy(None, None)

    def choose_user_strategy(self, strategy_id, strategy_pair):
        self.current_strategy = strategy_id
        self.current_pair = strategy_pair
        if self.current_strategy is not None:
            data = database.get_data(db.Strategy.strategy_pair,
                                     db.Strategy.strategy_position,
                                     db.Strategy.strategy_name,
                                     attribute=db.Strategy.strategy_id,
                                     value=self.current_strategy)
            self.lineEdit_pair.setText(data[0]['strategy_pair'])
            self.lineEdit_position.setText(str(data[0]['strategy_position']))
            self.comboBox_strategy.setCurrentText(data[0]['strategy_name'])
        else:
            self.lineEdit_pair.clear()
            self.lineEdit_position.clear()
            self.comboBox_strategy.setCurrentIndex(0)

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        try:
            self.logs_window.close()
        except Exception as e:
            print(e)


# Виджет отображающий краткую информацию по стратегии
class StrategyWidget(QWidget):
    def __init__(self, info, parent):
        super(StrategyWidget, self).__init__()

        loadUi('gui/strategy_widget.ui', self)

        self.parent = parent
        self.pushButton.clicked.connect(self.activate_strategy)
        if info is not None:
            self.strategy_id = info['strategy_id']
            self.strategy_pair = info['strategy_pair']
            self.strategy_position = info['strategy_position']
            self.strategy_name = info['strategy_name']
            self.label_pair.setText(self.strategy_pair)
            self.label_position.setText(str(self.strategy_position))
            self.label_strategy.setText(self.strategy_name)
            self.label_pnl.setText(str(info['strategy_pnl']))
            self.load_strategy_state()
        else:
            self.strategy_id = None
            self.strategy_pair = None

        # Обновление pnl через сигнал таймера (тик 1 секунда)
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_pnl)
        self.timer.start()

    def load_strategy_state(self):
        is_active = database.get_data(db.Strategy.is_active,
                                      attribute=db.Strategy.strategy_id,
                                      value=self.strategy_id
                                      )[0]['is_active']
        if is_active is False:
            self.pushButton.setIcon(QtGui.QIcon("gui/play.png"))
            self.pushButton.setIconSize(QSize(28, 28))
        else:
            self.pushButton.setIcon(QtGui.QIcon("gui/pause.png"))
            self.pushButton.setIconSize(QSize(28, 28))

    # Включение бота на торговую стратегию
    def activate_strategy(self):
        is_active = database.get_data(db.Strategy.is_active,
                                      attribute=db.Strategy.strategy_id,
                                      value=self.strategy_id
                                      )[0]['is_active']
        database.update_data(table=db.Strategy,
                             attribute=db.Strategy.strategy_id,
                             value=self.strategy_id,
                             update_values={'is_active': not is_active})
        is_active = not is_active
        if is_active is False:
            self.pushButton.setIcon(QtGui.QIcon("gui/play.png"))
            self.pushButton.setIconSize(QSize(28, 28))
            q_signal.put({'header': 'stop ts', 'body': self.strategy_id})
        else:
            self.pushButton.setIcon(QtGui.QIcon("gui/pause.png"))
            self.pushButton.setIconSize(QSize(28, 28))
            q_signal.put({'header': 'start ts', 'body': [self.strategy_id,
                                                         self.strategy_name,
                                                         self.strategy_pair,
                                                         self.strategy_position]})

    def update_pnl(self):
        if self.strategy_id is not None:
            data = database.get_data(db.Strategy.strategy_pnl,
                                     attribute=db.Strategy.strategy_id,
                                     value=self.strategy_id)
            self.label_pnl.setText(str(data[0]['strategy_pnl']))

    def mousePressEvent(self, a0: QtGui.QMouseEvent) -> None:
        MainWindow.choose_user_strategy(self.parent, self.strategy_id, self.strategy_pair)
        self.setStyleSheet(
            "background-color: rgb(24, 73, 107);"
        )

    def focusOutEvent(self, a0: QtGui.QFocusEvent) -> None:
        self.setStyleSheet(
            "background-color: rgb(43, 118, 171);"
        )


# Окно с логами по трэйдам бота выбранной стратегии
class LogsWindow(QWidget):
    def __init__(self, strategy_id):
        super(LogsWindow, self).__init__()

        loadUi('gui/logs_widget.ui', self)

        self.strategy_id = strategy_id

        # Обновление логов совершённых ботом сделок по выбранной торговой стратегии (тик 1 секунда)
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_trade_logs)
        self.timer.start()

        self.show()

    def update_trade_logs(self):
        logs = database.get_data(db.Trade.trade_type,
                                 db.Trade.trade_price,
                                 db.Trade.trade_quantity,
                                 db.Trade.datetime,
                                 attribute=db.Trade.strategy_id,
                                 value=self.strategy_id)
        self.tableWidget.setRowCount(len(logs))
        for i, row in enumerate(logs):
            self.tableWidget.setItem(i, 0, QTableWidgetItem(row['trade_type']))
            self.tableWidget.setItem(i, 1, QTableWidgetItem(row['trade_price']))
            self.tableWidget.setItem(i, 2, QTableWidgetItem(row['trade_quantity']))
            self.tableWidget.setItem(i, 3, QTableWidgetItem(row['datetime']))

    def resizeEvent(self, a0: QtGui.QResizeEvent) -> None:
        self.tableWidget.setColumnWidth(0, (self.tableWidget.geometry().width() / 4)-1)
        self.tableWidget.setColumnWidth(1, (self.tableWidget.geometry().width() / 4)-1)
        self.tableWidget.setColumnWidth(2, (self.tableWidget.geometry().width() / 4)-1)
        self.tableWidget.setColumnWidth(3, (self.tableWidget.geometry().width() / 4)-1)


def create_gui():
    app = QApplication(sys.argv)
    login_window = LoginWindow()
    app.exec()
    print('FINISH APP')
