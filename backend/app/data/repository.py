"""Race storage: load once from FastF1, then serve from PostgreSQL + memory."""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import DriverRow, LapRow, RaceRow, StrategyRunRow
from .schemas import Driver, Lap, RaceData

_memory: dict[int, RaceData] = {}


def save_race(db: Session, race: RaceData) -> int:
    row = RaceRow(year=race.year, round=race.round, event=race.event, circuit=race.circuit,
                  total_laps=race.total_laps, source=race.source)
    db.add(row)
    db.flush()
    db.add_all(DriverRow(race_id=row.id, **d.to_dict()) for d in race.drivers)
    db.bulk_insert_mappings(LapRow, [{"race_id": row.id, **l.to_dict()} for l in race.laps])
    db.commit()
    race.race_id = row.id
    _memory[row.id] = race
    return row.id


def get_race(db: Session, race_id: int) -> RaceData | None:
    if race_id in _memory:
        return _memory[race_id]
    row = db.get(RaceRow, race_id)
    if row is None:
        return None
    drivers = [Driver(abbr=d.abbr, full_name=d.full_name, team=d.team, team_color=d.team_color, number=d.number)
               for d in db.scalars(select(DriverRow).where(DriverRow.race_id == race_id))]
    laps = [Lap(driver=l.driver, lap=l.lap, lap_time=l.lap_time, compound=l.compound, tyre_life=l.tyre_life,
                stint=l.stint, pit_in=l.pit_in, pit_out=l.pit_out, position=l.position,
                track_status=l.track_status, race_time=l.race_time)
            for l in db.scalars(select(LapRow).where(LapRow.race_id == race_id))]
    race = RaceData(year=row.year, round=row.round, event=row.event, circuit=row.circuit,
                    total_laps=row.total_laps, drivers=drivers, laps=laps, source=row.source, race_id=row.id)
    _memory[race_id] = race
    return race


def find_race_id(db: Session, year: int, round_number: int, source: str) -> int | None:
    return db.scalar(select(RaceRow.id).where(RaceRow.year == year, RaceRow.round == round_number,
                                              RaceRow.source == source))


def load_or_fetch(db: Session, year: int | None = None, round_number: int | None = None,
                  demo: bool = False) -> RaceData:
    if demo:
        from .synthetic import generate_demo_race
        race = generate_demo_race()
    else:
        if year is None or round_number is None:
            raise ValueError("year and round are required for a real race")
        race = None
    source = "synthetic" if demo else "fastf1"
    year_key = race.year if demo else year
    round_key = race.round if demo else round_number

    existing = find_race_id(db, year_key, round_key, source)
    if existing is not None:
        cached = get_race(db, existing)
        if cached is not None and cached.laps:
            return cached
        db.execute(delete(RaceRow).where(RaceRow.id == existing))
        db.commit()

    if race is None:
        from .fastf1_loader import load_race
        race = load_race(year, round_number)
    save_race(db, race)
    return race


def save_strategy_run(db: Session, **fields) -> None:
    db.add(StrategyRunRow(**fields))
    db.commit()


def list_strategy_runs(db: Session, race_id: int) -> list[dict]:
    rows = db.scalars(select(StrategyRunRow).where(StrategyRunRow.race_id == race_id)
                      .order_by(StrategyRunRow.created_at.desc()).limit(50))
    return [{"driver": r.driver, "mode": r.mode, "branch_lap": r.branch_lap, "final_delta": r.final_delta,
             "shadow_position": r.shadow_position, "actual_position": r.actual_position,
             "shadow_stops": r.shadow_stops, "actual_stops": r.actual_stops,
             "created_at": r.created_at.isoformat()} for r in rows]
