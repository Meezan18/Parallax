"""Race engineer Q&A: answer questions about the live race state.

Answers come from a deterministic intent matcher over the current state, so they
are instant and always grounded in the data. If ANTHROPIC_API_KEY is set, questions
the matcher doesn't understand are passed to an LLM together with the state as context.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Protocol

from ..data.schemas import NEUTRALISED


class EngineerContext(Protocol):
    race: Any
    driver: str
    lap: int
    shadow: Any
    assessment: Any
    model: Any
    pit_loss: float
    board: list[dict]

    def state_summary(self) -> dict: ...


HELP = ("Try: \"who's leading?\", \"is there a safety car?\", \"gap to CAL\", \"where is DUV?\", "
        "\"what's our plan?\", \"how's the shadow car doing?\", \"tyre deg?\", \"undercut?\", "
        "\"who has pitted?\", \"laps left\".")


def _drivers_in(text: str, ctx: EngineerContext) -> list[str]:
    found = []
    words = re.findall(r"[a-zA-Z]+", text)
    lower = text.lower()
    for d in ctx.race.drivers:
        last = d.full_name.split()[-1].lower()
        if any(w.upper() == d.abbr for w in words if len(w) == 3) or re.search(rf"\b{re.escape(last)}\b", lower):
            found.append(d.abbr)
    return found


def _row(ctx: EngineerContext, abbr: str) -> dict | None:
    return next((r for r in ctx.board if r["driver"] == abbr), None)


def _has(q: str, *patterns: str) -> bool:
    return any(re.search(p, q) for p in patterns)


def answer_rules(question: str, ctx: EngineerContext) -> str | None:
    q = question.lower().strip()
    if not ctx.board:
        return "Lights haven't gone out yet. Ask me again once the race is running."
    lap, total = ctx.lap, ctx.race.total_laps
    mentioned = [d for d in _drivers_in(question, ctx) if d != ctx.driver]
    me = _row(ctx, ctx.driver)
    status = ctx.race.track_status(lap)

    if _has(q, r"\bhelp\b", r"what can you"):
        return HELP

    if _has(q, r"safety car", r"\bsc\b", r"\bvsc\b", r"red flag", r"track status", r"yellow", r"\bflag"):
        if status == "GREEN":
            since = next((n for n in range(lap, 0, -1) if ctx.race.track_status(n) != "GREEN"), None)
            tail = f" Last neutralisation ended around lap {since + 1}." if since else ""
            return f"No. Track is green on lap {lap}.{tail}"
        start = lap
        while start > 1 and ctx.race.track_status(start - 1) == status:
            start -= 1
        names = {"SC": "the Safety Car is out", "VSC": "a Virtual Safety Car is out",
                 "RED": "the race is red-flagged", "YELLOW": "there are yellow flags"}
        extra = f" Pit stops cost about {ctx.pit_loss * (0.5 if status == 'SC' else 0.65):.0f}s right now." \
            if status in ("SC", "VSC") else ""
        return f"Yes, {names[status]} (since lap {start}).{extra}"

    if _has(q, r"\blead", r"\bp1\b", r"first place", r"winning", r"in front\b.*race"):
        lead = ctx.board[0]
        second = ctx.board[1] if len(ctx.board) > 1 else None
        tail = f", {second['interval'].lstrip('+')}s ahead of {second['driver']}" if second else ""
        return (f"{lead['name']} ({lead['driver']}) leads on lap {lap}/{total}{tail}. "
                f"{lead['compound'].title()}s, {lead['tyre_age']} laps old.")

    if _has(q, r"laps? (left|remaining|to go)", r"how many laps"):
        return f"Lap {lap} of {total}: {total - lap} to go."

    if _has(q, r"fastest"):
        best = min(((l.lap_time, l.driver, l.lap) for l in ctx.race.laps
                    if l.lap <= lap and l.lap_time and not l.pit_in and not l.pit_out), default=None)
        if best:
            m, s = divmod(best[0], 60)
            return f"Fastest lap so far: {best[1]}, {int(m)}:{s:06.3f} on lap {best[2]}."

    if _has(q, r"undercut", r"overcut"):
        uc = ctx.assessment.undercut if ctx.assessment else None
        if not uc:
            return "No undercut in play right now. We're not within six laps of our stop, or we're leading."
        verdict = "ON" if uc["on"] else "not on yet"
        return (f"Undercut on {uc['rival']} is {verdict}: gap {uc['gap']:.1f}s, two laps on fresh tyres "
                f"worth about {uc['gain']:.1f}s.")

    if _has(q, r"shadow", r"ghost", r"\bai\b", r"would (we|it)", r"delta", r"versus real", r"vs real"):
        d = ctx.shadow.delta(lap)
        pos = ctx.shadow.virtual_position(lap)
        if d is None:
            return "The shadow car isn't running on this lap."
        ahead = "ahead of" if d < 0 else "behind"
        stops_ai = ", ".join(f"L{k} {c[0]}" for k, c in ctx.shadow.car.pits) or "none yet"
        stops_real = ", ".join(f"L{s['lap']} {s['compound'][0]}" for s in ctx.shadow.actual_stops()
                               if s["lap"] <= lap) or "none yet"
        real_pos = me["position"] if me else "?"
        return (f"Shadow {ctx.driver} is {abs(d):.1f}s {ahead} the real car: virtual P{pos} vs real P{real_pos}. "
                f"Shadow stops: {stops_ai}. Real stops: {stops_real}.")

    if _has(q, r"plan", r"strateg", r"when .*(pit|box|stop)", r"\bbox\b", r"should we"):
        a = ctx.assessment
        if not a or not a.plans:
            return "No dry strategy to compute right now."
        best = a.plans[0]
        alt = f" Plan B: {a.plans[1].label()} (+{a.plans[1].delta:.1f}s)." if len(a.plans) > 1 else ""
        nxt = best.next_stop
        when = f"Next stop lap {nxt[0]} for {nxt[1].title()}s." if nxt else "No more stops: run to the flag."
        return f"Plan {best.label()}. {when}{alt}"

    if _has(q, r"tyre", r"tire", r"\bdeg", r"compound", r"\bwear"):
        if mentioned:
            r = _row(ctx, mentioned[0])
            if r:
                return f"{r['driver']} is on {r['compound'].title()}s, {r['tyre_age']} laps old, {r['stops']} stop(s)."
        parts = [f"{c.title()} +{p.b:.3f}s/lap ({p.n_laps} laps seen)" for c, p in ctx.model.params.items()]
        car = ctx.shadow.car
        return (f"Live degradation fit: {'; '.join(parts)}. Shadow car on {car.compound.title()}s at {car.age} laps. "
                f"Pit loss estimate {ctx.pit_loss:.1f}s.")

    if _has(q, r"pitted", r"who.*(stop|pit)", r"how many stops"):
        rows = [f"{r['driver']} {r['stops']}" for r in ctx.board if r["stops"] and not r["retired"]]
        return ("Stops so far: " + ", ".join(rows) + ".") if rows else "Nobody has pitted yet."

    if _has(q, r"\bgap\b", r"interval", r"how far", r"behind", r"ahead"):
        if mentioned and me:
            r = _row(ctx, mentioned[0])
            if r and r["gap_s"] is not None and me["gap_s"] is not None:
                diff = r["gap_s"] - me["gap_s"]
                rel = "ahead of" if diff < 0 else "behind"
                return f"{r['driver']} is {abs(diff):.1f}s {rel} {ctx.driver} (real car)."
        if me:
            i = ctx.board.index(me)
            ahead = ctx.board[i - 1] if i > 0 else None
            behind = ctx.board[i + 1] if i + 1 < len(ctx.board) else None
            parts = [f"{ctx.driver} is P{me['position']}"]
            if ahead:
                parts.append(f"{me['interval'].lstrip('+')}s behind {ahead['driver']}")
            if behind and behind["interval"]:
                parts.append(f"{behind['interval'].lstrip('+')}s ahead of {behind['driver']}")
            return ", ".join(parts) + "."

    if mentioned or _has(q, r"where is", r"position", r"\bp\d+\b"):
        target = mentioned[0] if mentioned else ctx.driver
        r = _row(ctx, target)
        if r:
            if r["retired"]:
                return f"{r['driver']} is out of the race."
            return (f"{r['name']} is P{r['position']} ({r['gap']}), on {r['compound'].title()}s, "
                    f"{r['tyre_age']} laps old, {r['stops']} stop(s).")
    return None


async def answer(question: str, ctx: EngineerContext) -> dict:
    text = answer_rules(question, ctx)
    if text:
        return {"answer": text, "source": "rules"}
    key = os.getenv("ANTHROPIC_API_KEY")
    if key:
        try:
            return {"answer": await _llm_answer(question, ctx, key), "source": "llm"}
        except Exception as exc:  # network or API errors fall back to the help text
            return {"answer": f"Couldn't reach the language model ({type(exc).__name__}). {HELP}", "source": "rules"}
    return {"answer": f"Didn't catch that. {HELP}", "source": "rules"}


async def _llm_answer(question: str, ctx: EngineerContext, key: str) -> str:
    import httpx
    system = ("You are a calm Formula 1 race engineer on the pit wall. Answer in at most three short sentences, "
              "using only the race state JSON provided. If the data doesn't answer it, say so.")
    payload = {
        "model": os.getenv("ENGINEER_MODEL", "claude-sonnet-5-5"),
        "max_tokens": 250,
        "system": system,
        "messages": [{"role": "user", "content": f"Race state:\n{json.dumps(ctx.state_summary())}\n\n"
                                                  f"Question: {question}"}],
    }
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post("https://api.anthropic.com/v1/messages", json=payload,
                              headers={"x-api-key": key, "anthropic-version": "2023-06-01"})
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json().get("content", []))


__all__ = ["answer", "answer_rules", "NEUTRALISED"]
