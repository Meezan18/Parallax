"""Load a real race from FastF1 and normalise it into RaceData."""
from __future__ import annotations

import math
import os

from .schemas import Driver, Lap, RaceData, normalise_track

CACHE_DIR = os.getenv("FASTF1_CACHE", os.path.join(os.path.dirname(__file__), "..", "..", ".fastf1_cache"))


def _enable_cache():
    import fastf1
    os.makedirs(CACHE_DIR, exist_ok=True)
    fastf1.Cache.enable_cache(CACHE_DIR)
    return fastf1


def _isnull(v) -> bool:
    if v is None:
        return True
    try:
        import pandas as pd
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return isinstance(v, float) and math.isnan(v)


def _secs(td) -> float | None:
    return None if _isnull(td) else float(td.total_seconds())


def parse_track_status(code) -> str:
    """FastF1 TrackStatus is a string of status codes seen during the lap."""
    s = "" if _isnull(code) else str(code)
    if "5" in s:
        return "RED"
    if "4" in s:
        return "SC"
    if "6" in s or "7" in s:
        return "VSC"
    if "2" in s:
        return "YELLOW"
    return "GREEN"


def list_events(year: int) -> list[dict]:
    fastf1 = _enable_cache()
    schedule = fastf1.get_event_schedule(year, include_testing=False)
    events = []
    for row in schedule.itertuples():
        events.append({
            "round": int(row.RoundNumber),
            "name": str(row.EventName),
            "country": str(row.Country),
            "location": str(row.Location),
            "date": str(row.EventDate.date()) if not _isnull(row.EventDate) else None,
        })
    return events


def load_race(year: int, round_number: int) -> RaceData:
    fastf1 = _enable_cache()
    session = fastf1.get_session(year, round_number, "R")
    # telemetry=True brings position data, which gives us the real circuit outline for the track map
    session.load(laps=True, telemetry=True, weather=False, messages=False)
    try:
        laps_df = session.laps
    except Exception as exc:  # FastF1 raises DataNotLoadedError when the download failed
        raise RuntimeError("FastF1 couldn't download timing data for this race. Check the server's internet "
                           "connection, or pick a race that has already happened.") from exc
    if laps_df is None or len(laps_df) == 0:
        raise RuntimeError("FastF1 returned no laps for this race. It may not have been run yet.")
    results = session.results

    drivers: list[Driver] = []
    for _, r in results.iterrows():
        color = r.get("TeamColor")
        color = f"#{color}" if isinstance(color, str) and color and not color.startswith("#") else "#888888"
        drivers.append(Driver(
            abbr=str(r["Abbreviation"]),
            full_name=str(r.get("FullName") or r["Abbreviation"]),
            team=str(r.get("TeamName") or ""),
            team_color=color,
            number=str(r.get("DriverNumber") or ""),
        ))

    start = laps_df.loc[laps_df["LapNumber"] == 1, "LapStartTime"].min()
    laps: list[Lap] = []
    for _, row in laps_df.iterrows():
        n = int(row["LapNumber"])
        lap_time = _secs(row["LapTime"])
        if lap_time is None and not _isnull(row["Time"]) and not _isnull(row["LapStartTime"]):
            lap_time = _secs(row["Time"] - row["LapStartTime"])
        race_time = None
        if not _isnull(row["Time"]) and not _isnull(start):
            race_time = _secs(row["Time"] - start)
        compound = row["Compound"]
        laps.append(Lap(
            driver=str(row["Driver"]),
            lap=n,
            lap_time=lap_time,
            compound=compound.upper() if isinstance(compound, str) and compound else "UNKNOWN",
            tyre_life=0 if _isnull(row["TyreLife"]) else int(row["TyreLife"]),
            stint=1 if _isnull(row["Stint"]) else int(row["Stint"]),
            pit_in=not _isnull(row["PitInTime"]),
            pit_out=n > 1 and not _isnull(row["PitOutTime"]),
            position=None if _isnull(row["Position"]) else int(row["Position"]),
            track_status=parse_track_status(row["TrackStatus"]),
            race_time=race_time,
        ))

    fill_missing_race_times(laps)
    track = circuit_outline(session)
    total = getattr(session, "total_laps", None) or int(laps_df["LapNumber"].max())
    return RaceData(
        year=year,
        round=round_number,
        event=str(session.event["EventName"]),
        circuit=str(session.event["Location"]),
        total_laps=int(total),
        drivers=drivers,
        laps=laps,
        source="fastf1",
        track=track,
    )


def fill_missing_race_times(laps: list[Lap]) -> None:
    """Some laps lack a timestamp; rebuild race time from lap times where possible."""
    by_driver: dict[str, list[Lap]] = {}
    for l in laps:
        by_driver.setdefault(l.driver, []).append(l)
    for driver_laps in by_driver.values():
        driver_laps.sort(key=lambda l: l.lap)
        prev = 0.0
        for l in driver_laps:
            if l.race_time is None and l.lap_time is not None:
                l.race_time = prev + l.lap_time
            if l.lap_time is None and l.race_time is not None and l.lap > 1:
                l.lap_time = l.race_time - prev
            if l.race_time is not None:
                prev = l.race_time


def circuit_outline(session) -> list[list[float]] | None:
    """Circuit shape from the fastest lap's position data, rotated the way F1 graphics show it."""
    try:
        import numpy as np
        pos = session.laps.pick_fastest().get_pos_data()
        x, y = pos["X"].to_numpy(float), pos["Y"].to_numpy(float)
        try:
            angle = np.deg2rad(float(session.get_circuit_info().rotation))
        except Exception:
            angle = 0.0
        rx = x * np.cos(angle) - y * np.sin(angle)
        ry = x * np.sin(angle) + y * np.cos(angle)
        return normalise_track(list(rx), list(ry))
    except Exception:
        return None  # the map falls back to a generic outline
