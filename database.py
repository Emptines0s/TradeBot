from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import *


class Database:
    engine = create_engine(f"postgresql+psycopg2://root:root@localhost/TradeBot", echo=False)
    engine.connect()
    print(engine)
    Session = sessionmaker(engine)

    # создать все таблицы
    def create_tables(self):
        Base.metadata.create_all(self.engine)

    # удалить все таблицы
    def delete_tables(self):
        Base.metadata.drop_all(self.engine)

    # получить даныые об объектах удовлетворяющих условию в выбранной таблице
    def get_data(self, *table_args, attribute, value):
        with self.Session.begin() as session:
            target = session.query(*table_args).filter(attribute == value).all()
        return target

    # добавить строки с данными в таблицу
    def add_data(self, items):
        with self.Session.begin() as session:
            for item in items:
                session.add(item)

    # обновить строки с данными в таблице
    def update_data(self, table, attribute, value, update_values):
        with self.Session.begin() as session:
            session.query(table).filter(attribute == value).update(update_values)

    # удалить строки с данными в таблице
    def delete_data(self, table, attribute, value):
        with self.Session.begin() as session:
            items = session.query(table).filter(attribute == value).all()
            for item in items:
                session.delete(item)
