"""Personal taste prefs: favorites (weighted up) and a blocklist.

Persisted to ~/.diet-roulette/prefs.json, same simple style as the tracker. The
function that does the work (``apply_prefs``) is pure so it's easy to test: it
drops blocked meals and hands back per-candidate weights so favorites come up more.
"""

from __future__ import annotations

import json
from pathlib import Path

STATE_DIR = Path.home() / ".diet-roulette"
STATE_FILE = STATE_DIR / "prefs.json"

# A favorited meal is this many times more likely to be drawn than a normal one.
FAVORITE_WEIGHT = 4


def _empty() -> dict:
    return {"favorites": [], "blocked": []}


def _load(path: Path = STATE_FILE) -> dict:
    if not path.exists():
        return _empty()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty()
    data.setdefault("favorites", [])
    data.setdefault("blocked", [])
    return data


def _save(data: dict, path: Path = STATE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_prefs(path: Path = STATE_FILE) -> dict:
    """Return the stored prefs ({'favorites': [...], 'blocked': [...]})."""
    return _load(path)


def _toggle(kind: str, name: str, add: bool, path: Path) -> dict:
    data = _load(path)
    name = name.strip()
    if add:
        if name and name not in data[kind]:
            data[kind].append(name)
    else:
        data[kind] = [x for x in data[kind] if x.lower() != name.lower()]
    _save(data, path)
    return data


def add_favorite(name: str, path: Path = STATE_FILE) -> dict:
    return _toggle("favorites", name, True, path)


def remove_favorite(name: str, path: Path = STATE_FILE) -> dict:
    return _toggle("favorites", name, False, path)


def add_blocked(name: str, path: Path = STATE_FILE) -> dict:
    return _toggle("blocked", name, True, path)


def remove_blocked(name: str, path: Path = STATE_FILE) -> dict:
    return _toggle("blocked", name, False, path)


def apply_prefs(
    foods: list[dict],
    prefs: dict,
    favorite_weight: int = FAVORITE_WEIGHT,
) -> tuple[list[dict], list[float]]:
    """Drop blocked meals and weight favorites up.

    Returns ``(candidates, weights)``. Matching is case-insensitive substring on the
    meal name, so storing "birria" blocks "Beef Birria (Birria de res ...)". The
    weights line up with ``candidates`` for use by ``wheel.pick(..., weights=...)``.
    """
    blocked = [b.lower() for b in prefs.get("blocked", []) if b.strip()]
    favs = [f.lower() for f in prefs.get("favorites", []) if f.strip()]
    candidates: list[dict] = []
    weights: list[float] = []
    for meal in foods:
        name = meal["name"].lower()
        if any(b in name for b in blocked):
            continue
        candidates.append(meal)
        weights.append(favorite_weight if any(f in name for f in favs) else 1)
    return candidates, weights
