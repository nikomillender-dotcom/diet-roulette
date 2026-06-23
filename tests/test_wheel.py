"""Tests for the wheel: data integrity, filtering, protein matching, recipe format."""

import pytest

from diet_roulette.wheel import (
    CUISINES,
    MEAL_TYPES,
    filter_foods,
    format_amount,
    format_recipe,
    load_foods,
    matches_protein,
    pick,
)

REQUIRED = {"name", "meal", "cuisine", "kcal", "protein_g", "carbs_g", "fat_g",
            "fiber_g", "proteins", "servings", "tags", "emoji", "ingredients", "steps"}


def test_database_loads_and_is_well_formed():
    foods = load_foods()
    assert len(foods) >= 60
    for f in foods:
        assert REQUIRED <= set(f), f"missing keys in {f.get('name')}"
        assert f["meal"] in MEAL_TYPES
        assert f["cuisine"] in CUISINES, f"unknown cuisine {f['cuisine']}"
        assert f["kcal"] > 0
        assert isinstance(f["proteins"], list)
        assert isinstance(f["fiber_g"], int)
        assert f["steps"], f"{f['name']} has no steps"
        for ing in f["ingredients"]:
            assert {"item", "qty", "unit"} <= set(ing), f"bad ingredient in {f['name']}"


def test_every_cuisine_is_represented():
    present = {f["cuisine"] for f in load_foods()}
    assert present == set(CUISINES)


def test_filter_by_meal_and_kcal_and_tag():
    foods = load_foods()
    assert all(f["meal"] == "lunch" for f in filter_foods(foods, meal="lunch"))
    assert all(f["kcal"] <= 250 for f in filter_foods(foods, max_kcal=250))
    assert all("one-pot" in f["tags"] for f in filter_foods(foods, tag="one-pot"))


def test_filter_by_cuisine():
    foods = load_foods()
    korean = filter_foods(foods, cuisine="korean")
    assert korean and all(f["cuisine"] == "korean" for f in korean)


# --- protein matching ---------------------------------------------------------

def test_ground_beef_is_specific():
    """'ground beef' must only match meals that actually contain ground beef."""
    foods = load_foods()
    res = filter_foods(foods, protein="ground beef")
    assert res
    for f in res:
        blob = (" ".join(f["proteins"]) + f["name"]
                + " ".join(i["item"] for i in f["ingredients"])).lower()
        assert "ground beef" in blob
    # And a plain-beef dish (birria) must NOT be in the ground-beef results.
    names = {f["name"] for f in res}
    assert not any("Birria" in n for n in names)


def test_beef_is_broad():
    foods = load_foods()
    beef = {f["name"] for f in filter_foods(foods, protein="beef")}
    ground = {f["name"] for f in filter_foods(foods, protein="ground beef")}
    assert ground <= beef  # everything ground-beef is also "beef"
    assert len(beef) > len(ground)


def test_protein_matches_via_ingredient():
    foods = load_foods()
    paneer = filter_foods(foods, protein="paneer")
    assert paneer and any("Paneer" in f["name"] for f in paneer)


def test_any_protein_returns_everything():
    foods = load_foods()
    for word in ("", "any", "surprise", "whatever"):
        assert len(filter_foods(foods, protein=word)) == len(foods)


def test_matches_protein_none():
    foods = load_foods()
    assert all(matches_protein(f, None) for f in foods)


# --- picking & formatting -----------------------------------------------------

def test_seeded_pick_is_deterministic():
    foods = filter_foods(load_foods(), cuisine="indian")
    assert pick(foods, seed=1) == pick(foods, seed=1)


def test_pick_empty_raises():
    with pytest.raises(ValueError):
        pick([], seed=1)


def test_format_amount_cases():
    assert format_amount({"item": "x", "qty": 2, "unit": "lb"}) == "2 lb"
    assert format_amount({"item": "x", "qty": 0.5, "unit": "cup"}) == "0.5 cup"
    assert format_amount({"item": "x", "qty": 4, "unit": "clove"}) == "4 clove"
    assert format_amount({"item": "x", "qty": 3, "unit": None}) == "3"
    assert format_amount({"item": "x", "qty": None, "unit": None}) == "to taste"


def test_format_recipe_has_amounts_and_steps():
    foods = load_foods()
    birria = next(f for f in foods if "Birria" in f["name"])
    out = format_recipe(birria)
    assert "Ingredients" in out and "Steps" in out
    assert "2 lb  beef chuck" in out
    assert "to taste  salt" in out
