"""PostgreSQL persistence (SQLite fallback for local dev and tests)."""
from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Integer, String,
                        UniqueConstraint, create_engine)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./parallax.db")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class RaceRow(Base):
    __tablename__ = "races"
    __table_args__ = (UniqueConstraint("year", "round", "source", name="uq_race"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer)
    round: Mapped[int] = mapped_column(Integer)
    event: Mapped[str] = mapped_column(String(120))
    circuit: Mapped[str] = mapped_column(String(120))
    total_laps: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DriverRow(Base):
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id", ondelete="CASCADE"), index=True)
    abbr: Mapped[str] = mapped_column(String(5))
    full_name: Mapped[str] = mapped_column(String(80))
    team: Mapped[str] = mapped_column(String(80))
    team_color: Mapped[str] = mapped_column(String(9))
    number: Mapped[str] = mapped_column(String(4))


class LapRow(Base):
    __tablename__ = "laps"

    id: Mapped[int] = mapped_column(primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id", ondelete="CASCADE"), index=True)
    driver: Mapped[str] = mapped_column(String(5))
    lap: Mapped[int] = mapped_column(Integer)
    lap_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    compound: Mapped[str] = mapped_column(String(14))
    tyre_life: Mapped[int] = mapped_column(Integer)
    stint: Mapped[int] = mapped_column(Integer)
    pit_in: Mapped[bool] = mapped_column(Boolean)
    pit_out: Mapped[bool] = mapped_column(Boolean)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    track_status: Mapped[str] = mapped_column(String(8))
    race_time: Mapped[float | None] = mapped_column(Float, nullable=True)


class StrategyRunRow(Base):
    """Result of one finished shadow race, so runs can be compared later."""
    __tablename__ = "strategy_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id", ondelete="CASCADE"), index=True)
    driver: Mapped[str] = mapped_column(String(5))
    mode: Mapped[str] = mapped_column(String(10))
    branch_lap: Mapped[int] = mapped_column(Integer)
    final_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    shadow_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shadow_stops: Mapped[list] = mapped_column(JSON)
    actual_stops: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def init_db() -> None:
    Base.metadata.create_all(engine)
