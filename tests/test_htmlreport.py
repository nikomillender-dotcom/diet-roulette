"""Tests for the cute HTML export (no-JS sticky notes)."""

from diet_roulette.htmlreport import render_recipe_html, render_week_html
from diet_roulette.planner import aggregate_shopping_list, build_week
from diet_roulette.wheel import load_foods


def _sample_plan():
    foods = load_foods()
    plan = build_week(foods, days=2, slots=("lunch", "dinner"), seed=9)
    shopping = aggregate_shopping_list(plan["all_meals"])
    return plan, shopping


def test_week_html_is_self_contained_and_no_js():
    plan, shopping = _sample_plan()
    html = render_week_html(plan, shopping)
    assert html.startswith("<!DOCTYPE html>")
    assert "<script" not in html  # no JavaScript at all
    assert "http://" not in html and "https://" not in html  # no external assets


def test_week_html_has_a_details_note_per_meal():
    plan, shopping = _sample_plan()
    html = render_week_html(plan, shopping)
    assert html.count("<details") == len(plan["all_meals"])
    # Each planned meal's name should appear.
    for meal in plan["all_meals"]:
        # names contain non-ascii; just check a stable ascii fragment is present
        assert meal["name"].split(" (")[0] in html


def test_week_html_has_shopping_checkboxes():
    plan, shopping = _sample_plan()
    html = render_week_html(plan, shopping)
    assert 'type="checkbox"' in html
    assert "Shopping list" in html


def test_html_escapes_meal_text():
    plan, shopping = _sample_plan()
    # Inject a hostile name into one meal copy.
    plan["all_meals"][0] = dict(plan["all_meals"][0], name="Taco <script>alert(1)</script>")
    plan["days"][0]["meals"][0] = ("lunch", plan["all_meals"][0])
    html = render_week_html(plan, shopping)
    assert "<script>alert(1)" not in html
    assert "&lt;script&gt;" in html


def test_recipe_html_renders_open_note():
    foods = load_foods()
    meal = next(f for f in foods if "Birria" in f["name"])
    html = render_recipe_html(meal)
    assert html.startswith("<!DOCTYPE html>")
    assert "<details" in html and " open>" in html
    assert "beef chuck" in html  # an ingredient
    assert "<script" not in html
