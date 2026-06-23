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
    "african",
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
    "african": "African",
}

# Inputs that mean "I don't care, surprise me" when asked for a protein.
_ANY_PROTEIN = {"", "any", "anything", "whatever", "surprise", "surprise me",
                "idc", "no preference", "none", "skip"}

# Pantry staples assumed always on hand, so they don't count for/against pantry mode.
_STAPLES = {
    "salt", "pepper", "black pepper", "white pepper", "water", "ice", "ice water",
    "oil", "olive oil", "vegetable oil", "cooking oil", "sesame oil", "sugar",
    "flour", "all-purpose flour", "baking powder", "baking soda",
}


def load_foods() -> list[dict]:
    """Read the curated meal database that ships inside the package."""
    with resources.files("diet_roulette.data").joinpath("foods.json").open(
        encoding="utf-8"
    ) as fh:
        return json.load(fh)


def _haystack(meal: dict) -> str:
    """All the searchable text for a meal: protein tokens, name, ingredient items."""
    return (
        " ".join(meal.get("proteins", [])).lower()
        + " " + meal["name"].lower()
        + " " + " ".join(i.get("item", "").lower() for i in meal.get("ingredients", []))
    )


def matches_protein(meal: dict, query: Optional[str]) -> bool:
    """Does this meal contain the protein the user asked for?

    Free-text and forgiving: an empty/"any" query matches everything. Otherwise we
    match against the meal's ``proteins`` tokens, its name, and its ingredient items.
    The match is directional (query must be CONTAINED in the meal's data), so
    "ground beef" only hits ground-beef meals while "beef" hits everything beefy, and
    odd inputs like "oxtail" or "paneer" still work via the ingredient list.
    """
    if query is None:
        return True
    q = query.strip().lower()
    if q in _ANY_PROTEIN:
        return True
    return q in _haystack(meal)


def matches_any_term(meal: dict, terms: list[str]) -> bool:
    """True if any of the given lowercase terms appears in the meal's text.

    Used by the ``--avoid`` filter: avoid "pork, cilantro" drops anything that
    mentions pork or cilantro in its name, proteins, or ingredients.
    """
    if not terms:
        return False
    hay = _haystack(meal)
    return any(t in hay for t in terms)


def protein_density(meal: dict) -> float:
    """Grams of protein per 100 kcal. Higher means more protein-efficient."""
    kcal = meal.get("kcal") or 0
    if kcal <= 0:
        return 0.0
    return meal.get("protein_g", 0) / kcal * 100


def lean_subset(foods: list[dict]) -> list[dict]:
    """Keep the leaner half of the pool, ranked by protein density (at least one)."""
    if not foods:
        return []
    ranked = sorted(foods, key=protein_density, reverse=True)
    keep = max(1, len(ranked) // 2)
    return ranked[:keep]


def pantry_coverage(meal: dict, have: list[str]) -> float:
    """Fraction of a meal's non-staple ingredients you already have (0.0 to 1.0).

    Staples (salt, oil, water...) are assumed on hand and ignored. Matching is loose
    and bidirectional, so "chicken" covers "chicken thigh" and vice versa.
    """
    if not have:
        return 1.0
    core = [i.get("item", "").lower() for i in meal.get("ingredients", [])]
    core = [it for it in core if it and it not in _STAPLES]
    if not core:
        return 1.0
    matched = sum(1 for it in core if any(h in it or it in h for h in have))
    return matched / len(core)


def meal_for_hour(hour: int) -> str:
    """Map a clock hour (0 to 23) to the meal you'd probably want then."""
    if 5 <= hour < 11:
        return "breakfast"
    if 11 <= hour < 15:
        return "lunch"
    if 15 <= hour < 21:
        return "dinner"
    return "snack"


def filter_foods(
    foods: list[dict],
    meal: Optional[str] = None,
    max_kcal: Optional[int] = None,
    tag: Optional[str] = None,
    cuisine: Optional[str] = None,
    protein: Optional[str] = None,
    avoid: Optional[list[str]] = None,
    have: Optional[list[str]] = None,
    pantry_threshold: float = 0.5,
) -> list[dict]:
    """Narrow the database by meal type, calories, tag, cuisine, protein, and more.

    ``avoid`` drops meals mentioning any of those terms. ``have`` keeps only meals
    you can mostly make (>= ``pantry_threshold`` of their non-staple ingredients).
    """
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
    if avoid:
        result = [f for f in result if not matches_any_term(f, avoid)]
    if have:
        result = [f for f in result if pantry_coverage(f, have) >= pantry_threshold]
    return result


def pick(
    candidates: list[dict],
    seed: Optional[int] = None,
    weights: Optional[list[float]] = None,
) -> dict:
    """Pick one meal. A seed makes the choice reproducible (used by tests).

    If ``weights`` is given (same length as ``candidates``), the draw is weighted,
    so favorited meals can come up more often.
    """
    if not candidates:
        raise ValueError("no meals match those filters")
    rng = random.Random(seed)
    if weights:
        return rng.choices(candidates, weights=weights, k=1)[0]
    return rng.choice(candidates)


def cuisine_label(meal: dict) -> str:
    """Friendly display name for a meal's cuisine."""
    return CUISINE_LABELS.get(meal.get("cuisine", ""), meal.get("cuisine", ""))


def format_meal(meal: dict, mystery: bool = False) -> str:
    """One-line summary with macros and cuisine.

    When ``mystery`` is set, the name and cuisine are hidden (the macros, ingredients
    and steps stay visible as clues) for a blind "mystery box" spin.
    """
    if mystery:
        head = f"{meal['emoji']}  {BOLD}??? mystery dish ???{RESET}  {DIM}({meal['meal']}){RESET}"
    else:
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


def format_recipe(meal: dict, mystery: bool = False) -> str:
    """Full recipe: ingredients with amounts plus numbered steps.

    With ``mystery`` set, the dish name and cuisine stay hidden so the ingredients
    and steps act as clues before the reveal.
    """
    lines = [format_meal(meal, mystery=mystery)]
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
