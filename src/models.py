from datetime import datetime
from sqlalchemy import ForeignKey, BigInteger
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Session(Base):
    __tablename__ = 'sessions'
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    track_id: Mapped[int] = mapped_column(nullable=False)
    session_type: Mapped[int] = mapped_column(nullable=False)
    date: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    
    laps: Mapped[list["Lap"]] = relationship(back_populates="session", cascade="all, delete-orphan")

class Lap(Base):
    __tablename__ = 'laps'
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('sessions.id'), nullable=False)
    lap_number: Mapped[int] = mapped_column(nullable=False)
    lap_time_ms: Mapped[int | None] = mapped_column(default=None)
    sector1_ms: Mapped[int | None] = mapped_column(default=None)
    sector2_ms: Mapped[int | None] = mapped_column(default=None)
    sector3_ms: Mapped[int | None] = mapped_column(default=None)
    is_valid: Mapped[bool] = mapped_column(default=True)
    
    session: Mapped["Session"] = relationship(back_populates="laps")
    telemetry: Mapped[list["TelemetryData"]] = relationship(back_populates="lap", cascade="all, delete-orphan")

class TelemetryData(Base):
    __tablename__ = 'telemetry_data'
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    lap_id: Mapped[int] = mapped_column(ForeignKey('laps.id'), nullable=False)
    lap_distance: Mapped[float] = mapped_column(nullable=False, index=True) 
    speed: Mapped[int] = mapped_column(nullable=False)
    throttle: Mapped[float] = mapped_column(nullable=False)
    brake: Mapped[float] = mapped_column(nullable=False)
    gear: Mapped[int] = mapped_column(nullable=False)
    steer: Mapped[float] = mapped_column(nullable=False)
    
    lap: Mapped["Lap"] = relationship(back_populates="telemetry")