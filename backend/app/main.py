"""UNDERCUT API."""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .data import repository
from .data.schemas import DRY_COMPOUNDS
from .db import SessionLocal, init_db
from .engine.degradation import TyreModel
from .engine.optimizer import best_plans, evaluate_plan
from .engine.pitloss import estimate_pit_loss
from .live.session import RaceSession

sessions: dict[str, RaceSession] = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield
    for s in sessions.values():
        s.stop()


app = FastAPI(title="UNDERCUT", version="0.1.0", lifespan=lifespan,
              description="An AI pit wall that races its own strategy against reality.")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def race_or_404(db: Session, race_id: int):
    race = repository.get_race(db, race_id)
    if race is None:
        raise HTTPException(404, "Race not found. Load it first.")
    return race


# ---- schemas ------------------------------------------------------------
class LoadRace(BaseModel):
    year: Optional[int] = None
    round: Optional[int] = None
    demo: bool = False


class Stop(BaseModel):
    lap: int = Field(ge=1)
    compound: Literal["SOFT", "MEDIUM", "HARD"]


class OptimizeRequest(BaseModel):
    driver: str
    from_lap: int = Field(default=1, ge=1)


class SessionRequest(BaseModel):
    race_id: int
    driver: str
    mode: Literal["auto", "fixed"] = "auto"
    stops: list[Stop] = []
    branch_lap: int = Field(default=1, ge=1)
    seconds_per_lap: float = Field(default=2.0, ge=0.1, le=30)


class Ask(BaseModel):
    question: str = Field(min_length=1, max_length=500)


# ---- races --------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"ok": True, "sessions": len(sessions)}


@app.get("/api/schedule/{year}")
async def schedule(year: int):
    from .data.fastf1_loader import list_events
    try:
        return await run_in_threadpool(list_events, year)
    except Exception as exc:
        raise HTTPException(502, f"Couldn't fetch the {year} schedule from FastF1: {exc}") from exc


@app.post("/api/races/load")
async def load_race(body: LoadRace, db: Session = Depends(get_db)):
    try:
        race = await run_in_threadpool(repository.load_or_fetch, db, body.year, body.round, body.demo)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"Couldn't load that race: {exc}") from exc
    return race.summary()


@app.get("/api/races/{race_id}")
def get_race(race_id: int, db: Session = Depends(get_db)):
    return race_or_404(db, race_id).summary()


@app.get("/api/races/{race_id}/analysis")
def analysis(race_id: int, db: Session = Depends(get_db)):
    """Post-race view: the tyre model fitted on the whole race, and every driver's real strategy."""
    race = race_or_404(db, race_id)
    model = TyreModel.fit(race)
    strategies = []
    for d in race.drivers:
        laps = race.index().get(d.abbr, {})
        if not laps:
            continue
        stints, cur = [], None
        for n in sorted(laps):
            l = laps[n]
            if cur is None or l.stint != cur["stint"]:
                cur = {"stint": l.stint, "compound": l.compound, "from": n, "to": n}
                stints.append(cur)
            cur["to"] = n
        strategies.append({"driver": d.abbr, "team_color": d.team_color, "stints": stints})
    return {"model": model.to_dict(), "curves": model.curves(), "pit_loss": estimate_pit_loss(race),
            "strategies": strategies, "runs": repository.list_strategy_runs(db, race_id)}


@app.post("/api/races/{race_id}/optimize")
def optimize(race_id: int, body: OptimizeRequest, db: Session = Depends(get_db)):
    """Hindsight optimum for a driver from a given lap, compared with what they actually did."""
    race = race_or_404(db, race_id)
    laps = race.index().get(body.driver.upper())
    if not laps:
        raise HTTPException(404, "Driver not in this race")
    lap = min(body.from_lap, max(laps))
    state = laps[lap]
    model = TyreModel.fit(race)
    pit_loss = estimate_pit_loss(race)
    used = {laps[n].compound for n in laps if n <= lap and laps[n].compound in DRY_COMPOUNDS}
    plans = best_plans(model, body.driver.upper(), lap, state.compound, state.tyre_life, used, pit_loss, top=8)
    actual = [(n, laps[n + 1].compound) for n in sorted(laps) if n >= lap and laps[n].pit_in and n + 1 in laps]
    actual_time = evaluate_plan(model, body.driver.upper(), lap, state.compound, state.tyre_life, actual, pit_loss)
    best = plans[0].time if plans else actual_time
    return {"from_lap": lap, "pit_loss": pit_loss, "plans": [p.to_dict() for p in plans],
            "actual": {"stops": [{"lap": k, "compound": c} for k, c in actual],
                       "time": round(actual_time, 2), "delta": round(actual_time - best, 2)}}


# ---- live sessions -------------------------------------------------------
def _persist_run(session: RaceSession) -> None:
    if not session.summary:
        return
    db = SessionLocal()
    try:
        repository.save_strategy_run(db, race_id=session.race.race_id, **{
            k: session.summary[k] for k in ("driver", "mode", "branch_lap", "final_delta", "shadow_position",
                                            "actual_position", "shadow_stops", "actual_stops")})
    finally:
        db.close()


@app.post("/api/sessions")
def create_session(body: SessionRequest, db: Session = Depends(get_db)):
    race = race_or_404(db, body.race_id)
    driver = body.driver.upper()
    if driver not in race.index():
        raise HTTPException(404, "Driver not in this race")
    if body.branch_lap >= race.total_laps:
        raise HTTPException(400, "Takeover lap must be before the last lap")
    if body.mode == "fixed" and not body.stops:
        raise HTTPException(400, "A fixed strategy needs at least one stop")
    s = RaceSession(race, driver, body.mode, [(x.lap, x.compound) for x in body.stops], body.branch_lap,
                    body.seconds_per_lap, on_finish=_persist_run)
    sessions[s.id] = s
    # keep memory bounded: drop the oldest finished sessions
    if len(sessions) > 50:
        for sid in [k for k, v in sessions.items() if v.finished][:10]:
            sessions.pop(sid).stop()
    return s.info()


def session_or_404(sid: str) -> RaceSession:
    s = sessions.get(sid)
    if s is None:
        raise HTTPException(404, "Session not found")
    return s


@app.get("/api/sessions/{sid}")
def get_session(sid: str):
    return session_or_404(sid).info()


@app.post("/api/sessions/{sid}/ask")
async def ask(sid: str, body: Ask):
    return await session_or_404(sid).ask(body.question)


@app.websocket("/ws/sessions/{sid}")
async def session_ws(ws: WebSocket, sid: str):
    s = sessions.get(sid)
    await ws.accept()
    if s is None:
        await ws.send_json({"type": "error", "message": "Session not found"})
        await ws.close(code=4404)
        return
    q = s.subscribe()
    await ws.send_json(s.init_payload())
    s.start()

    async def sender():
        while True:
            await ws.send_json(await q.get())

    async def receiver():
        while True:
            msg = await ws.receive_json()
            kind = msg.get("type")
            if kind == "ask":
                text = str(msg.get("question", ""))[:500]
                reply = await s.ask(text)
                await ws.send_json({"type": "engineer", "question": text, "lap": s.lap, **reply})
            elif kind == "pause":
                s.paused = True
            elif kind == "resume":
                s.paused = False
            elif kind == "speed":
                s.interval = min(max(float(msg.get("seconds_per_lap", 2.0)), 0.1), 30.0)
            elif kind == "jump":
                await s.jump_to(int(msg.get("lap", s.lap + 1)))
            await ws.send_json({"type": "status", "session": s.info()})

    tasks = [asyncio.create_task(sender()), asyncio.create_task(receiver())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    except WebSocketDisconnect:
        pass
    finally:
        for t in tasks:
            t.cancel()
        s.unsubscribe(q)
