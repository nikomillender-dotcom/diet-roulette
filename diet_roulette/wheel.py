"""The spinning wheel: load meals, filter them, and pick one with a little flair."""

from __future__ import annotations

import json
import random
import sys
import time
from importlib import resources
from typing import Optional

# ANSI helpers (kept tiny; no dependencies).
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"

MEAL_TYPES = ("breakfast", "lunch", "dinner", "snack")


def load_foods() -> list[dict]:
    """Read the curated meal database that ships inside the package."""
    with resources.files("diet_roulette.data").joinpath("foods.json").open(
        encoding="utf-8"
    ) as fh:
        return json.load(fh)


def filter_foods(
    foods: list[dict],
    meal: Optional[str] = None,
    max_kcal: Optional[int] = None,
    tag: Optional[str] = None,
) -> list[dict]:
    """Narrow the database by meal type, calorie cap, and/or dietary tag."""
    result = foods
    if meal:
        result = [f for f in result if f["meal"] == meal]
    if max_kcal is not None:
        result = [f for f in result if f["kcal"] <= max_kcal]
    if tag:
        result = [f for f in result if tag in f.get("tags", [])]
    return result


def pick(candidates: list[dict], seed: Optional[int] = None) -> dict:
    """Pick one meal. A seed makes the choice reproducible (used by tests)."""
    if not candidates:
        raise ValueError("no meals match those filters")
    rng = random.Random(seed)
    return rng.choice(candidates)


def format_meal(meal: dict) -> str:
    """One-line summary with macros."""
    return (
        f"{meal['emoji']}  {BOLD}{meal['name']}{RESET}  {DIM}({meal['meal']}){RESET}\n"
        f"   {meal['kcal']} kcal  ·  "
        f"P {meal['protein_g']}g  C {meal['carbs_g']}g  F {meal['fat_g']}g"
        + (f"  ·  {DIM}{', '.join(meal['tags'])}{RESET}" if meal.get("tags") else "")
    )


def spin_animation(candidates: list[dict], winner: dict) -> None:
    """Cycle through candidate names like a slowing wheel, then land on the winner.

    Skipped automatically when not attached to a TTY (e.g. piped output).
    """
    if not sys.stdout.isatty() or len(candidates) < 2:
        return

    rng = random.Random()
    names = [f"{c['emoji']}  {c['name']}" for c in candidates]
    # Start fast, slow down — classic wheel feel.
    delay = 0.04
    elapsed = 0.0
    sys.stdout.write(f"{CYAN}Spinning the wheel...{RESET}\n")
    while elapsed < 1.6:
        choice = rng.choice(names)
        sys.stdout.write(f"\r\033[K  {YELLOW}{choice}{RESET}")
        sys.stdout.flush()
        time.sleep(delay)
        elapsed += delay
        delay *= 1.18  # ease out
    # Clear the spinner line so the caller can print the final result cleanly.
    sys.stdout.write("\r\033[K")
    sys.stdout.flush()
