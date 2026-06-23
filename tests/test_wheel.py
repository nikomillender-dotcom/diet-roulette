"""Tests for the wheel: data integrity, filtering, and seeded determinism."""

from diet_roulette.wheel import MEAL_TYPES, filter_foods, load_foods, pick

import pytest


def test_database_loads_and_is_well_formed():
    foods = load_foods()
    assert len(foods) >= 20
    required = {"name", "meal", "kcal", "protein_g", "carbs_g", "fat_g", "tags", "emoji"}
    for f in foods:
        assert required <= set(f), f"missing keys in {f.get('name')}"
        assert f["meal"] in MEAL_TYPES
        assert f["kcal"] > 0


def test_filter_by_meal():
    foods = load_foods()
    lunches = filter_foods(foods, meal="lunch")
    assert lunches
    assert all(f["meal"] == "lunch" for f in lunches)


def test_filter_by_max_kcal():
    foods = load_foods()
    light = filter_foods(foods, max_kcal=200)
    assert all(f["kcal"] <= 200 for f in light)


def test_filter_by_tag():
    foods = load_foods()
    vegan = filter_foods(foods, tag="vegan")
    assert vegan
    assert all("vegan" in f["tags"] for f in vegan)


def test_filters_combine():
    foods = load_foods()
    res = filter_foods(foods, meal="dinner", max_kcal=500, tag="high-protein")
    assert all(
        f["meal"] == "dinner" and f["kcal"] <= 500 and "high-protein" in f["tags"]
        for f in res
    )


def test_seeded_pick_is_deterministic():
    foods = filter_foods(load_foods(), meal="lunch")
    assert pick(foods, seed=1) == pick(foods, seed=1)


def test_pick_empty_raises():
    with pytest.raises(ValueError):
        pick([], seed=1)
