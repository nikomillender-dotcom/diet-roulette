"""Tests for the spin modifiers: lean, pantry, avoid, clock, weights, prefs, no-repeat."""

import json

from diet_roulette import prefs, tracker
from diet_roulette.wheel import (
    filter_foods,
    format_recipe,
    lean_subset,
    load_foods,
    matches_any_term,
    meal_for_hour,
    pantry_coverage,
    pick,
    protein_density,
)


# --- lean / protein density ---------------------------------------------------

def test_protein_density_math():
    assert protein_density({"protein_g": 30, "kcal": 300}) == 10.0
    assert protein_density({"protein_g": 10, "kcal": 0}) == 0.0  # no divide-by-zero


def test_lean_subset_keeps_the_densest_half():
    foods = load_foods()
    lean = lean_subset(foods)
    assert 1 <= len(lean) <= len(foods) // 2 + 1
    # The leanest kept meal is at least as dense as the densest dropped one.
    kept = min(protein_density(m) for m in lean)
    dropped = [m for m in foods if m not in lean]
    assert all(protein_density(m) <= kept for m in dropped)


# --- pantry mode (--have) -----------------------------------------------------

def test_pantry_coverage_ignores_staples_and_is_loose():
    meal = {"ingredients": [
        {"item": "chicken thigh"}, {"item": "rice"}, {"item": "salt"}, {"item": "oil"},
    ]}
    # salt + oil are staples, so only chicken + rice count; having both = full coverage.
    assert pantry_coverage(meal, ["chicken", "rice"]) == 1.0
    assert pantry_coverage(meal, ["chicken"]) == 0.5
    assert pantry_coverage(meal, []) == 1.0  # no pantry given -> everything qualifies


def test_filter_have_only_returns_makeable_meals():
    foods = load_foods()
    have = ["chicken", "rice", "soy sauce", "garlic", "ginger", "egg"]
    res = filter_foods(foods, have=have, pantry_threshold=0.5)
    assert res
    for m in res:
        assert pantry_coverage(m, have) >= 0.5


# --- avoid --------------------------------------------------------------------

def test_avoid_excludes_named_ingredients():
    foods = load_foods()
    res = filter_foods(foods, avoid=["pork", "shrimp"])
    assert res
    for m in res:
        assert not matches_any_term(m, ["pork", "shrimp"])
    # And the unfiltered pool really did contain some pork/shrimp meals.
    assert len(res) < len(foods)


# --- clock-aware --------------------------------------------------------------

def test_meal_for_hour_buckets():
    assert meal_for_hour(8) == "breakfast"
    assert meal_for_hour(12) == "lunch"
    assert meal_for_hour(19) == "dinner"
    assert meal_for_hour(23) == "snack"
    assert meal_for_hour(2) == "snack"


# --- weighted pick (rig the wheel) --------------------------------------------

def test_weighted_pick_favors_heavy_weight():
    a, b = {"name": "A"}, {"name": "B"}
    # B is 1000x more likely; a seeded draw should land on B.
    assert pick([a, b], seed=1, weights=[1, 1000])["name"] == "B"


# --- mystery display ----------------------------------------------------------

def test_mystery_hides_name_keeps_clues():
    meal = next(m for m in load_foods() if "Birria" in m["name"])
    out = format_recipe(meal, mystery=True)
    assert "Birria" not in out          # name hidden
    assert "mystery dish" in out
    assert "Ingredients" in out         # clues remain
    assert "beef chuck" in out


# --- prefs: rig the wheel -----------------------------------------------------

def test_apply_prefs_blocks_and_weights():
    foods = load_foods()
    p = {"favorites": ["birria"], "blocked": ["century egg"]}
    candidates, weights = prefs.apply_prefs(foods, p, favorite_weight=5)
    names = [m["name"] for m in candidates]
    assert not any("Century Egg" in n for n in names)            # blocked dropped
    fav_idx = [i for i, m in enumerate(candidates) if "Birria" in m["name"]]
    assert fav_idx and all(weights[i] == 5 for i in fav_idx)     # favorite weighted up
    assert len(candidates) == len(weights)


def test_prefs_roundtrip(tmp_path):
    path = tmp_path / "prefs.json"
    prefs.add_favorite("Birria", path=path)
    prefs.add_blocked("Gumbo", path=path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["favorites"] == ["Birria"]
    assert data["blocked"] == ["Gumbo"]
    prefs.remove_favorite("birria", path=path)  # case-insensitive removal
    assert prefs.load_prefs(path)["favorites"] == []


# --- no-repeat (--fresh) ------------------------------------------------------

def test_recent_names_window(tmp_path):
    path = tmp_path / "today.json"
    from datetime import date, timedelta
    today = date.today().isoformat()
    old = (date.today() - timedelta(days=10)).isoformat()
    path.write_text(json.dumps({
        today: [{"name": "Fresh Meal"}],
        old: [{"name": "Old Meal"}],
    }), encoding="utf-8")
    recent = tracker.recent_names(3, path=path)
    assert "Fresh Meal" in recent
    assert "Old Meal" not in recent
    assert tracker.recent_names(0, path=path) == set()
