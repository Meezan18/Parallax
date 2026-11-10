"""A synthetic race with known physics.

Used for two things:
  * tests: the true tyre parameters are known, so we can check the model recovers them
  * offline demo: the app works without network access or FastF1 downloads

All drivers and teams are fictional.
"""
from __future__ import annotations

import random

from .schemas import Driver, Lap, RaceData

TEAMS = [
    ("Apex Racing", "#E10600"), ("Northline", "#1E41FF"), ("Verdant GP", "#00A19C"),
    ("Solaris", "#FF8700"), ("Ironbark", "#6CD3BF"), ("Kestrel", "#2293D1"),
    ("Halcyon", "#B6BABD"), ("Tidewater", "#5E8FAA"), ("Cobalt Works", "#C92D4B"),
    ("Ember", "#F596C8"),
]
DRIVERS = [
    ("ARN", "Aron Lind"), ("BAS", "Bastien Moreau"), ("CAL", "Cal Okafor"), ("DUV", "Dario Duval"),
    ("ESK", "Esko Virtanen"), ("FAR", "Farah Haddad"), ("GRA", "Gray Whitlock"), ("HOL", "Holm Stenberg"),
    ("IVA", "Ivan Petrov"), ("JUN", "Jun Takeda"), ("KAI", "Kai Mendes"), ("LAR", "Lars Brekke"),
    ("MAT", "Mateo Rios"), ("NOV", "Noa Novak"), ("OKO", "Obi Okonkwo"), ("PAL", "Pia Palmer"),
    ("QUI", "Quinn Avery"), ("ROS", "Rosa Albescu"), ("SAN", "Sander Holt"), ("TAV", "Tavi Reyes"),
]

# compound -> (pace offset s, linear deg s/lap, quadratic deg s/lap^2)
TRUE_TYRES = {
    "SOFT": (-0.65, 0.085, 0.0012),
    "MEDIUM": (0.0, 0.052, 0.0006),
    "HARD": (0.55, 0.031, 0.00025),
}
TRUE_PIT_LOSS = 22.5
FUEL = 0.032


def generate_demo_race(seed: int = 11, total_laps: int = 56) -> RaceData:
    rng = random.Random(seed)
    T = total_laps
    base = 91.5

    drivers = [Driver(abbr=a, full_name=n, team=TEAMS[i // 2][0], team_color=TEAMS[i // 2][1],
                      number=str(i + 2)) for i, (a, n) in enumerate(DRIVERS)]
    pace = {d.abbr: i * 0.09 + rng.gauss(0, 0.05) for i, d in enumerate(drivers)}

    vsc_start = rng.randint(9, 13)
    vsc_laps = {vsc_start, vsc_start + 1}
    sc_start = rng.randint(31, 35)
    sc_laps = set(range(sc_start, sc_start + 4))

    # Strategy per driver: (start compound, [(pit lap, new compound), ...])
    templates = [
        lambda: ("MEDIUM", [(rng.randint(19, 27), "HARD")]),
        lambda: ("SOFT", [(rng.randint(12, 17), "HARD")]),
        lambda: ("MEDIUM", [(rng.randint(15, 20), "HARD"), (rng.randint(38, 43), "SOFT")]),
        lambda: ("SOFT", [(rng.randint(11, 15), "MEDIUM"), (rng.randint(28, 30), "HARD")]),
        lambda: ("HARD", [(rng.randint(30, 38), "MEDIUM")]),
    ]
    plans = {}
    for i, d in enumerate(drivers):
        start, stops = templates[rng.choice([0, 0, 1, 2, 3, 4]) if i else 0]()
        # opportunists convert a planned stop into a cheap safety-car stop
        new_stops = []
        for lap, comp in stops:
            if sc_start <= lap <= sc_start + 8 and rng.random() < 0.6:
                lap = sc_start
            new_stops.append((lap, comp))
        plans[d.abbr] = (start, dict(new_stops))

    retired = {drivers[16].abbr: 38}

    cum = {d.abbr: i * 0.25 for i, d in enumerate(drivers)}
    tyre = {d.abbr: [plans[d.abbr][0], 1 + (2 if i < 10 else 0) - 1] for i, d in enumerate(drivers)}
    stint = {d.abbr: 1 for d in drivers}
    pitted_last = {d.abbr: None for d in drivers}
    laps: list[Lap] = []

    for n in range(1, T + 1):
        status = "SC" if n in sc_laps else "VSC" if n in vsc_laps else "GREEN"
        mult = 0.5 if status == "SC" else 0.65 if status == "VSC" else 1.0
        active = [d for d in drivers if n <= retired.get(d.abbr, T)]
        this_lap: dict[str, Lap] = {}
        for grid, d in enumerate(drivers):
            if d not in active:
                continue
            a = d.abbr
            pit_out = pitted_last[a] is not None
            if pit_out:
                tyre[a] = [pitted_last[a], 1]
                stint[a] += 1
                pitted_last[a] = None
            else:
                tyre[a][1] += 1
            comp, age = tyre[a]
            off, b, c = TRUE_TYRES[comp]
            if status == "GREEN":
                t = base + pace[a] + off + b * age + c * age * age + FUEL * (T - n) + rng.gauss(0, 0.22)
                if n == 1:
                    t += 4.5 + 0.18 * grid
            else:
                t = base + (26.0 if status == "SC" else 9.0) + rng.gauss(0, 0.3) + FUEL * (T - n)
            pit_in = n in plans[a][1] and n < T
            if pit_in:
                t += TRUE_PIT_LOSS * mult * 0.35 + rng.gauss(0, 0.3)
                pitted_last[a] = plans[a][1][n]
            if pit_out:
                t += TRUE_PIT_LOSS * mult * 0.65 + rng.gauss(0, 0.3)
            cum[a] += t
            this_lap[a] = Lap(driver=a, lap=n, lap_time=t, compound=comp, tyre_life=age, stint=stint[a],
                              pit_in=pit_in, pit_out=pit_out, position=None, track_status=status,
                              race_time=cum[a])

        # the field bunches up behind the safety car on its last lap
        if status == "SC" and n == max(sc_laps):
            order = sorted(this_lap, key=lambda x: cum[x])
            lead = cum[order[0]]
            for i, a in enumerate(order):
                target = lead + i * 0.9
                if cum[a] > target:
                    this_lap[a].lap_time -= cum[a] - target
                    cum[a] = target
                    this_lap[a].race_time = target

        for pos, a in enumerate(sorted(this_lap, key=lambda x: cum[x]), start=1):
            this_lap[a].position = pos
        laps.extend(this_lap.values())

    return RaceData(year=2026, round=0, event="Demo Grand Prix (synthetic)", circuit="Demo Circuit",
                    total_laps=T, drivers=drivers, laps=laps, source="synthetic")
