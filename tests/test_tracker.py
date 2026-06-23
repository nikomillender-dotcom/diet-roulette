"""Tests for the day tracker. Uses a tmp state file so real logs are untouched."""

from diet_roulette import tracker


SAMPLE = {"name": "Test meal", "emoji": "🧪", "kcal": 500,
          "protein_g": 30, "carbs_g": 40, "fat_g": 20}


def test_accept_and_read_back(tmp_path):
    path = tmp_path / "today.json"
    tracker.accept(SAMPLE, path=path)
    tracker.accept(SAMPLE, path=path)
    picks = tracker.todays_picks(path=path)
    assert len(picks) == 2
    assert picks[0]["name"] == "Test meal"


def test_totals_sum():
    picks = [SAMPLE, SAMPLE, SAMPLE]
    t = tracker.totals(picks)
    assert t["kcal"] == 1500
    assert t["protein_g"] == 90


def test_reset_clears_today(tmp_path):
    path = tmp_path / "today.json"
    tracker.accept(SAMPLE, path=path)
    tracker.reset(path=path)
    assert tracker.todays_picks(path=path) == []


def test_budget_status_with_goal():
    status = tracker.budget_status([SAMPLE, SAMPLE], goal=2000)
    assert status["consumed"] == 1000
    assert status["remaining"] == 1000
    assert status["pct"] == 50


def test_budget_status_over():
    status = tracker.budget_status([SAMPLE] * 5, goal=2000)
    assert status["consumed"] == 2500
    assert status["remaining"] == -500
    assert status["pct"] == 125


def test_budget_status_without_goal():
    status = tracker.budget_status([SAMPLE], goal=None)
    assert status["consumed"] == 500
    assert status["goal"] is None
    assert status["remaining"] is None


def test_totals_empty():
    assert tracker.totals([])["kcal"] == 0
