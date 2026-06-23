"""Tests for the weekly planner, goals, low-energy mode, and shopping list."""

import pytest

from diet_roulette.planner import (
    aggregate_shopping_list,
    build_week,
    categorize,
    is_low_energy,
    resolve_goal,
    week_totals,
)
from diet_roulette.wheel import load_foods


# --- goals --------------------------------------------------------------------

def test_resolve_goal_synonyms():
    assert resolve_goal("fiber") == ("high-fiber", True)
    assert resolve_goal("High Fiber") == ("high-fiber", True)
    assert resolve_goal("keto") == ("low-carb", True)
    assert resolve_goal("light") == ("low-calorie", True)
    assert resolve_goal(None) == ("balanced", True)


def test_resolve_goal_unknown_falls_back():
    key, recognized = resolve_goal("banana bread")
    assert key == "balanced" and recognized is False


# --- low energy ---------------------------------------------------------------

def test_is_low_energy():
    assert is_low_energy({"tags": ["one-pot", "gluten-free"]})
    assert is_low_energy({"tags": ["crockpot"]})
    assert not is_low_energy({"tags": ["high-protein"]})
    assert not is_low_energy({"tags": []})


# --- build_week ---------------------------------------------------------------

def test_build_week_shape_and_determinism():
    foods = load_foods()
    a = build_week(foods, days=7, slots=("lunch", "dinner"), seed=11)
    b = build_week(foods, days=7, slots=("lunch", "dinner"), seed=11)
    assert [d["label"] for d in a["days"]] == [f"Day {i}" for i in range(1, 8)]
    assert all(len(d["meals"]) == 2 for d in a["days"])
    assert len(a["all_meals"]) == 14
    # Same seed -> identical plan.
    assert [m["name"] for m in a["all_meals"]] == [m["name"] for m in b["all_meals"]]


def test_build_week_high_fiber_goal_filters():
    foods = load_foods()
    plan = build_week(foods, days=5, slots=("dinner",), goal="high-fiber", seed=3)
    assert not plan["goal_relaxed"]  # plenty of high-fiber dinners exist
    assert all(m["fiber_g"] >= 8 for m in plan["all_meals"])


def test_build_week_no_repeats_until_pool_exhausted():
    foods = load_foods()
    # One small cuisine slot: japanese has 6 dinners-ish; ask for fewer than pool.
    plan = build_week(foods, days=3, slots=("dinner",), cuisine="japanese", seed=5)
    names = [m["name"] for m in plan["all_meals"]]
    assert len(names) == len(set(names))  # no repeats while pool not exhausted


def test_build_week_relaxes_when_goal_too_strict():
    # Tiny synthetic pool where only one meal meets high-fiber.
    foods = [
        {"name": "A", "meal": "dinner", "cuisine": "everyday", "kcal": 400, "protein_g": 10,
         "carbs_g": 40, "fat_g": 10, "fiber_g": 12, "proteins": [], "servings": 1,
         "tags": [], "emoji": "🍽️", "ingredients": [], "steps": ["x"]},
        {"name": "B", "meal": "dinner", "cuisine": "everyday", "kcal": 400, "protein_g": 10,
         "carbs_g": 40, "fat_g": 10, "fiber_g": 2, "proteins": [], "servings": 1,
         "tags": [], "emoji": "🍽️", "ingredients": [], "steps": ["x"]},
    ]
    plan = build_week(foods, days=2, slots=("dinner",), goal="high-fiber", seed=1)
    assert plan["goal_relaxed"] is True


def test_build_week_low_energy_only():
    foods = load_foods()
    plan = build_week(foods, days=4, slots=("dinner",), low_energy=True, seed=2)
    assert all(is_low_energy(m) for m in plan["all_meals"])


def test_build_week_impossible_filter_raises():
    foods = load_foods()
    with pytest.raises(ValueError):
        build_week(foods, days=3, slots=("dinner",), cuisine="japanese", protein="lamb")


def test_week_totals():
    foods = load_foods()
    plan = build_week(foods, days=2, slots=("dinner",), seed=1)
    totals = week_totals(plan)
    assert totals["avg_kcal_per_day"] > 0
    assert totals["total_fiber_g"] >= 0


# --- shopping list ------------------------------------------------------------

def test_aggregate_sums_same_item_and_unit():
    meals = [
        {"ingredients": [{"item": "garlic", "qty": 3, "unit": "clove"}]},
        {"ingredients": [{"item": "garlic", "qty": 5, "unit": "clove"}]},
    ]
    shop = aggregate_shopping_list(meals)
    garlic = [x for items in shop.values() for x in items if x["item"] == "garlic"]
    assert garlic and garlic[0]["amount"] == "8 clove"


def test_aggregate_to_taste_and_skip_water():
    meals = [{"ingredients": [
        {"item": "salt", "qty": None, "unit": None},
        {"item": "water", "qty": 2, "unit": "cup"},
    ]}]
    shop = aggregate_shopping_list(meals)
    flat = {x["item"]: x["amount"] for items in shop.values() for x in items}
    assert flat["salt"] == "as needed"
    assert "water" not in flat  # tap water is skipped


def test_aggregate_groups_into_known_categories():
    meals = [{"ingredients": [
        {"item": "ground beef", "qty": 1, "unit": "lb"},
        {"item": "onion", "qty": 1, "unit": None},
        {"item": "black pepper", "qty": None, "unit": None},
    ]}]
    shop = aggregate_shopping_list(meals)
    assert "Meat" in shop and "Produce" in shop and "Spices & Seasoning" in shop


def test_categorize_collision_cases():
    assert categorize("black pepper") == "Spices & Seasoning"
    assert categorize("bell pepper") == "Produce"
    assert categorize("chili powder") == "Spices & Seasoning"
    assert categorize("serrano chiles") == "Produce"
    assert categorize("chicken broth") == "Pantry"
    assert categorize("chicken thighs") == "Meat"
    assert categorize("eggplant") == "Produce"
    assert categorize("egg") == "Dairy & Eggs"
