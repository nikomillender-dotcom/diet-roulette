"""Track the meals you accept during a day, persisted to ~/.diet-roulette.

State is intentionally simple: a JSON file keyed by ISO date. The functions that
do the math (totals, budget) are pure so they're trivial to test.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

STATE_DIR = Path.home() / ".diet-roulette"
STATE_FILE = STATE_DIR / "today.json"

MACRO_KEYS = ("kcal", "protein_g", "carbs_g", "fat_g")


def _today_key() -> str:
    return date.today().isoformat()


def _load(path: Path = STATE_FILE) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict, path: Path = STATE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def accept(meal: dict, path: Path = STATE_FILE) -> list[dict]:
    """Record a meal for today. Returns today's full list of picks."""
    data = _load(path)
    day = data.setdefault(_today_key(), [])
    day.append(
        {"name": meal["name"], "emoji": meal.get("emoji", "🍽️"),
         **{k: meal.get(k, 0) for k in MACRO_KEYS}}
    )
    _save(data, path)
    return day


def todays_picks(path: Path = STATE_FILE) -> list[dict]:
    """Return the meals accepted today (empty list if none)."""
    return _load(path).get(_today_key(), [])


def recent_names(days: int, path: Path = STATE_FILE) -> set[str]:
    """Names of meals accepted within the last ``days`` days (today counts as day 1).

    Drives the ``--fresh`` no-repeat spin so you stop being handed the same dinners.
    """
    if not days or days <= 0:
        return set()
    data = _load(path)
    cutoff = date.today() - timedelta(days=days - 1)
    out: set[str] = set()
    for key, picks in data.items():
        try:
            when = date.fromisoformat(key)
        except ValueError:
            continue
        if when >= cutoff:
            out.update(p["name"] for p in picks)
    return out


def reset(path: Path = STATE_FILE) -> None:
    """Clear today's log (other days are left untouched)."""
    data = _load(path)
    data.pop(_today_key(), None)
    _save(data, path)


def totals(picks: list[dict]) -> dict:
    """Sum macros across a list of picks. Pure function."""
    return {k: sum(p.get(k, 0) for p in picks) for k in MACRO_KEYS}


def budget_status(picks: list[dict], goal: Optional[int]) -> dict:
    """Compute consumed/remaining kcal vs a goal. Pure function.

    Returns dict with consumed, goal, remaining, pct (0-100+). If goal is None,
    remaining/pct are None.
    """
    consumed = totals(picks)["kcal"]
    if goal is None:
        return {"consumed": consumed, "goal": None, "remaining": None, "pct": None}
    remaining = goal - consumed
    pct = round(consumed / goal * 100) if goal else 0
    return {"consumed": consumed, "goal": goal, "remaining": remaining, "pct": pct}
