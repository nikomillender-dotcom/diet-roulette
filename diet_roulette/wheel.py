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

# Cuisines present in the database, with friendly display labels.
CUISINES = (
    "everyday",
    "mexican-jalisco",
    "mexican-colima",
    "japanese",
    "korean",
    "chinese",
    "black-american",
    "country-us",
    "indian",
)
CUISINE_LABELS = {
    "everyday": "Everyday",
    "mexican-jalisco": "Mexican (Jalisco)",
    "mexican-colima": "Mexican (Colima)",
    "japanese": "Japanese",
    "korean": "Korean",
    "chinese": "Chinese",
    "black-american": "Black American",
    "country-us": "Country US",
    "indian": "Indian",
}

# Inputs that mean "I don't care, surprise me" when asked for a protein.
_ANY_PROTEIN = {"", "any", "anything", "whatever", "surprise", "surprise me",
                "idc", "no preference", "none", "skip"}


def load_foods() -> list[dict]:
    """Read the curated meal database that ships inside the package."""
    with resources.files("diet_roulette.data").joinpath("foods.json").open(
        encoding="utf-8"
    ) as fh:
        return json.load(fh)


def matches_protein(meal: dict, query: Optional[str]) -> bool:
    """Does this meal contain the protein the user asked for?

    Free-text and forgiving: an empty/"any" query matches everything. Otherwise we
    match against the meal's ``proteins`` tokens, its name, and its ingredient items,
    in both substring directions. So "ground beef" only hits ground-beef meals, while
    "beef" hits everything beefy, and odd inputs like "oxtail" or "paneer" still work
    via the ingredient list.
    """
    if query is None:
        return True
    q = query.strip().lower()
    if q in _ANY_PROTEIN:
        return True

    # The match is directional: the query must be CONTAINED in the meal's data.
    # So "beef" matches both "beef" and "ground beef" meals, but "ground beef"
    # only matches meals that actually contain ground beef (not plain beef ones).
    haystack = (
        " ".join(meal.get("proteins", [])).lower()
        + " " + meal["name"].lower()
        + " " + " ".join(i.get("item", "").lower() for i in meal.get("ingredients", []))
    )
    return q in haystack


def filter_foods(
    foods: list[dict],
    meal: Optional[str] = None,
    max_kcal: Optional[int] = None,
    tag: Optional[str] = None,
    cuisine: Optional[str] = None,
    protein: Optional[str] = None,
) -> list[dict]:
    """Narrow the database by meal type, calorie cap, dietary tag, cuisine, protein."""
    result = foods
    if meal:
        result = [f for f in result if f["meal"] == meal]
    if max_kcal is not None:
        result = [f for f in result if f["kcal"] <= max_kcal]
    if tag:
        result = [f for f in result if tag in f.get("tags", [])]
    if cuisine:
        result = [f for f in result if f.get("cuisine") == cuisine]
    if protein is not None and protein.strip().lower() not in _ANY_PROTEIN:
        result = [f for f in result if matches_protein(f, protein)]
    return result


def pick(candidates: list[dict], seed: Optional[int] = None) -> dict:
    """Pick one meal. A seed makes the choice reproducible (used by tests)."""
    if not candidates:
        raise ValueError("no meals match those filters")
    rng = random.Random(seed)
    return rng.choice(candidates)


def cuisine_label(meal: dict) -> str:
    """Friendly display name for a meal's cuisine."""
    return CUISINE_LABELS.get(meal.get("cuisine", ""), meal.get("cuisine", ""))


def format_meal(meal: dict) -> str:
    """One-line summary with macros and cuisine."""
    badge = cuisine_label(meal)
    head = f"{meal['emoji']}  {BOLD}{meal['name']}{RESET}  {DIM}({meal['meal']}"
    head += f" · {badge}" if badge else ""
    head += f"){RESET}"
    return (
        f"{head}\n"
        f"   {meal['kcal']} kcal  ·  "
        f"P {meal['protein_g']}g  C {meal['carbs_g']}g  F {meal['fat_g']}g  "
        f"Fiber {meal.get('fiber_g', 0)}g"
        + (f"  ·  {DIM}{', '.join(meal['tags'])}{RESET}" if meal.get("tags") else "")
    )


def format_amount(ing: dict) -> str:
    """Render an ingredient amount like '2 lb', '4 clove', or 'to taste'."""
    qty, unit = ing.get("qty"), ing.get("unit")
    if qty is None and unit is None:
        return "to taste"
    # Trim trailing .0 so 2.0 shows as 2 but 0.5 stays 0.5.
    qty_str = ""
    if qty is not None:
        qty_str = f"{qty:g}"
    return " ".join(part for part in (qty_str, unit) if part).strip() or "to taste"


def format_recipe(meal: dict) -> str:
    """Full recipe: ingredients with amounts plus numbered steps."""
    lines = [format_meal(meal)]
    servings = meal.get("servings")
    if servings:
        lines.append(f"   {DIM}makes {servings} serving(s){RESET}")
    lines.append("")
    lines.append(f"{BOLD}Ingredients{RESET}")
    for ing in meal.get("ingredients", []):
        amount = format_amount(ing)
        lines.append(f"  • {amount}  {ing['item']}")
    lines.append("")
    lines.append(f"{BOLD}Steps{RESET}")
    for i, step in enumerate(meal.get("steps", []), 1):
        lines.append(f"  {i}. {step}")
    return "\n".join(lines)


def spin_animation(candidates: list[dict], winner: dict) -> None:
    """Cycle through candidate names like a slowing wheel, then land on the winner.

    Skipped automatically when not attached to a TTY (e.g. piped output).
    """
    if not sys.stdout.isatty() or len(candidates) < 2:
        return

    rng = random.Random()
    names = [f"{c['emoji']}  {c['name']}" for c in candidates]
    # Start fast, slow down, classic wheel feel.
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
