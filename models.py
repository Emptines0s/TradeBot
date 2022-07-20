from sqlalchemy import Column, PrimaryKeyConstraint, Integer, String, DateTime, ForeignKeyConstraint, Float, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func


Base = declarative_base()


class Client(Base):
    __tablename__ = 'client'

    client_id = Column(Integer)
    client_key = Column(String)
    strategies = relationship('Strategy', cascade='all, delete-orphan')

    __table_args__ = (
        PrimaryKeyConstraint('client_id', name='client_pk'),
    )


class Strategy(Base):
    __tablename__ = 'strategy'

    strategy_id = Column(Integer)
    strategy_pair = Column(String)
    strategy_name = Column(String)
    strategy_pnl = Column(Float)
    strategy_position = Column(Float)
    is_active = Column(Boolean)
    client_id = Column(Integer)
    trades = relationship('Trade', cascade='all, delete-orphan')

    __table_args__ = (
        PrimaryKeyConstraint('strategy_id', name='strategy_pk'),
        ForeignKeyConstraint(['client_id'], ['client.client_id'])
    )


class Trade(Base):
    __tablename__ = 'trade'

    trade_id = Column(Integer)
    trade_type = Column(String)
    trade_price = Column(Float)
    trade_quantity = Column(Float)
    datetime = Column(DateTime, server_default=func.now())
    strategy_id = Column(Integer)

    __table_args__ = (
        PrimaryKeyConstraint('trade_id', name='trade_pk'),
        ForeignKeyConstraint(['strategy_id'], ['strategy.strategy_id'])
    )
