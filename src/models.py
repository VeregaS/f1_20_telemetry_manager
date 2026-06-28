from datetime import datetime
from sqlalchemy import Column, Integer, Float, Boolean, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Session(Base):
    __tablename__ = 'sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    track_id = Column(Integer, nullable=False)
    session_type = Column(Integer, nullable=False)
    date = Column(DateTime, default=datetime.utcnow)
    
    laps = relationship("Lap", back_populates="session", cascade="all, delete-orphan")

class Lap(Base):
    __tablename__ = 'laps'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('sessions.id'), nullable=False)
    lap_number = Column(Integer, nullable=False)
    lap_time_ms = Column(Integer)
    sector1_ms = Column(Integer)
    sector2_ms = Column(Integer)
    sector3_ms = Column(Integer)
    is_valid = Column(Boolean, default=True)
    
    session = relationship("Session", back_populates="laps")
    telemetry = relationship("TelemetryData", back_populates="lap", cascade="all, delete-orphan")

class TelemetryData(Base):
    __tablename__ = 'telemetry_data'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    lap_id = Column(Integer, ForeignKey('laps.id'), nullable=False)
    # Индекс для ускорения синхронизации и интерполяции по дистанции
    lap_distance = Column(Float, nullable=False, index=True) 
    speed = Column(Integer, nullable=False)
    throttle = Column(Float, nullable=False)
    brake = Column(Float, nullable=False)
    gear = Column(Integer, nullable=False)
    steer = Column(Float, nullable=False)
    
    lap = relationship("Lap", back_populates="telemetry")