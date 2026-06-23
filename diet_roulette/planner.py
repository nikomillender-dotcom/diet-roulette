"""Weekly meal-plan generation, dietary goals, low-energy mode, and shopping lists.

All the selection and aggregation logic lives in pure functions so it is easy to
test and so the CLI and the HTML export can share it.
"""

from __future__ import annotations

import random
from typing import Callable, Optional

from diet_roulette.wheel import filter_foods

# --- Dietary goals --------------------------------------------------------------

# A goal is a hard predicate (used to filter the pool when enough meals qualify)
# plus a metric (used to rank meals when we have to relax the filter).
GOAL_RULES: dict[str, Callable[[dict], bool]] = {
    "high-fiber": lambda m: m.get("fiber_g", 0) >= 8,
    "high-protein": lambda m: m.get("protein_g", 0) >= 25,
    "low-carb": lambda m: m.get("carbs_g", 0) <= 25,
    "low-calorie": lambda m: m.get("kcal", 0) <= 450,
    "balanced": lambda m: True,
}
GOAL_METRIC: dict[str, Callable[[dict], float]] = {
    "high-fiber": lambda m: m.get("fiber_g", 0),
    "high-protein": lambda m: m.get("protein_g", 0),
    "low-carb": lambda m: -m.get("carbs_g", 0),
    "low-calorie": lambda m: -m.get("kcal", 0),
    "balanced": lambda m: 0,
}
# Free-text the user might type, mapped to a canonical goal.
GOAL_SYNONYMS = {
    "fiber": "high-fiber", "high fiber": "high-fiber", "high-fiber": "high-fiber",
    "fibre": "high-fiber", "high fibre": "high-fiber",
    "protein": "high-protein", "high protein": "high-protein",
    "high-protein": "high-protein", "muscle": "high-protein", "gains": "high-protein",
    "low carb": "low-carb", "low-carb": "low-carb", "keto": "low-carb", "lowcarb": "low-carb",
    "low calorie": "low-calorie", "low-calorie": "low-calorie", "lowcal": "low-calorie",
    "light": "low-calorie", "weight loss": "low-calorie", "weight-loss": "low-calorie",
    "cut": "low-calorie", "lean": "low-calorie",
    "balanced": "balanced", "none": "balanced", "any": "balanced", "": "balanced",
}


def resolve_goal(text: Optional[str]) -> tuple[str, bool]:
    """Map free-text goal input to a canonical goal.

    Returns (goal_key, recognized). An unrecognized goal falls back to "balanced"
    with recognized=False so the caller can warn the user.
    """
    if text is None:
        return "balanced", True
    key = text.strip().lower()
    if key in GOAL_SYNONYMS:
        return GOAL_SYNONYMS[key], True
    if key in GOAL_RULES:
        return key, True
    return "balanced", False


# --- Low-energy mode ------------------------------------------------------------

LOW_ENERGY_TAGS = {"one-pot", "crockpot", "sheet-pan", "no-cook"}


def is_low_energy(meal: dict) -> bool:
    """A low-effort meal: one-pot, slow-cooker, sheet-pan, or no-cook."""
    return bool(LOW_ENERGY_TAGS & set(meal.get("tags", [])))


# --- Weekly plan ----------------------------------------------------------------

# Which meal types can fill each slot. Lunch and dinner draw from the same pool
# since most main dishes work for either.
SLOT_POOL = {
    "breakfast": {"breakfast"},
    "lunch": {"lunch", "dinner"},
    "dinner": {"lunch", "dinner"},
    "snack": {"snack"},
}


def _slot_pool(base: list[dict], slot: str, goal_key: str) -> tuple[list[dict], bool]:
    """Build the candidate pool for one slot, applying the goal.

    Returns (pool, relaxed). If the hard goal filter leaves too few meals, we relax
    to the full slot pool sorted by the goal metric (best-effort) and flag it.
    """
    meal_types = SLOT_POOL.get(slot, {slot})
    pool = [m for m in base if m["meal"] in meal_types]
    if goal_key == "balanced" or not pool:
        return pool, False
    qualifying = [m for m in pool if GOAL_RULES[goal_key](m)]
    # Need a few qualifying meals to make a varied week; otherwise relax.
    if len(qualifying) >= 3:
        return qualifying, False
    ranked = sorted(pool, key=lambda m: GOAL_METRIC[goal_key](m), reverse=True)
    return ranked, True


class _Bag:
    """Draws items without repeats until the pool is exhausted, then reshuffles."""

    def __init__(self, pool: list[dict], rng: random.Random):
        self._pool = pool
        self._rng = rng
        self._bag: list[dict] = []

    def draw(self) -> dict:
        if not self._bag:
            self._bag = list(self._pool)
            self._rng.shuffle(self._bag)
        return self._bag.pop()


def build_week(
    foods: list[dict],
    days: int = 7,
    slots: tuple[str, ...] = ("lunch", "dinner"),
    goal: Optional[str] = None,
    cuisine: Optional[str] = None,
    protein: Optional[str] = None,
    low_energy: bool = False,
    seed: Optional[int] = None,
) -> dict:
    """Generate a meal plan. Pure and seedable.

    Returns a dict with: days (list of {label, meals: [(slot, meal)]}),
    all_meals (flat list in plan order, for the shopping list), goal (resolved key),
    goal_recognized, goal_relaxed, and the echoed params.
    """
    rng = random.Random(seed)
    goal_key, recognized = resolve_goal(goal)

    base = filter_foods(foods, cuisine=cuisine, protein=protein)
    if low_energy:
        base = [m for m in base if is_low_energy(m)]
    if not base:
        raise ValueError("no meals match those filters")

    relaxed = False
    bags: dict[str, _Bag] = {}
    for slot in slots:
        pool, slot_relaxed = _slot_pool(base, slot, goal_key)
        if not pool:
            raise ValueError(f"no meals available for the {slot} slot with those filters")
        relaxed = relaxed or slot_relaxed
        bags[slot] = _Bag(pool, rng)

    plan_days = []
    all_meals: list[dict] = []
    for d in range(1, days + 1):
        day_meals = []
        for slot in slots:
            meal = bags[slot].draw()
            day_meals.append((slot, meal))
            all_meals.append(meal)
        plan_days.append({"label": f"Day {d}", "meals": day_meals})

    return {
        "days": plan_days,
        "all_meals": all_meals,
        "goal": goal_key,
        "goal_recognized": recognized,
        "goal_relaxed": relaxed,
        "params": {
            "days": days, "slots": list(slots), "cuisine": cuisine,
            "protein": protein, "low_energy": low_energy, "seed": seed,
        },
    }


def week_totals(plan: dict) -> dict:
    """Average per-day kcal and the headline macros across the plan."""
    meals = plan["all_meals"]
    days = max(1, plan["params"]["days"])
    total_kcal = sum(m["kcal"] for m in meals)
    return {
        "total_kcal": total_kcal,
        "avg_kcal_per_day": round(total_kcal / days),
        "total_protein_g": sum(m["protein_g"] for m in meals),
        "total_fiber_g": sum(m.get("fiber_g", 0) for m in meals),
    }


# --- Shopping list --------------------------------------------------------------

# Grocery aisle keyword map. First matching category wins, so ORDER MATTERS: more
# specific / collision-prone buckets (spices, grains, pantry liquids) are checked
# before the broad Produce / Dairy buckets. This protects cases like "black pepper"
# vs "bell pepper", "chili powder" vs fresh "chiles", "chicken broth" vs "chicken",
# and "eggplant" vs "egg".
CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("Spices & Seasoning", (
        "black pepper", "white pepper", "peppercorn", "red pepper flakes", "chili powder",
        "red chili powder", "cayenne", "paprika", "cumin", "oregano", "turmeric",
        "garam masala", "coriander", "cinnamon", "whole clove", "bay leaves", "bay leaf",
        "thyme", "seasoning", "mango powder", "fenugreek", "sesame seeds", "star anise",
        "curry powder", "asafoetida", "file powder", "sugar", "honey", "chia", "salt")),
    ("Bakery & Grains", (
        "rice", "tortilla", "bread", "roll", "biscuit", "bun", "noodle", "oats", "grits",
        "masa", "flour", "breadcrumb", "granola", "quinoa", "shirataki", "dumpling", "hominy")),
    ("Pantry", (
        "broth", "stock", "chicken base", "soup", "beans", "lentil", "toor dal", "moong dal",
        "chana dal", " dal", "chickpea", "soy sauce", "fish sauce", "mirin", "sake", "shaoxing",
        "vinegar", "oil", "dashi", "doenjang", "gochujang", "gochugaru", "doubanjiang", "miso",
        "tahini", "hummus", "marinara", "ketchup", "worcestershire", "coconut milk", "curry roux",
        "tomato paste", "tomato puree", "refried beans", "edamame", "nuts", "almond butter",
        "peanut butter", "chocolate", "protein powder", "wine", "cornstarch", "rock sugar",
        "kimchi", "tofu", "dressing")),
    ("Seafood", ("shrimp", "salmon", "tuna", "cod", "mackerel", "fish")),
    ("Meat", (
        "beef", "pork", "chicken", "turkey", "lamb", "bacon", "sausage", "andouille", "ham",
        "steak", "rib", "chuck", "sirloin", "meat", "hock", "cube steak")),
    ("Produce", (
        "onion", "garlic", "ginger", "tomato", "tomatillo", "potato", "carrot", "celery",
        "pepper", "chile", "chili", "spinach", "lettuce", "cabbage", "broccoli", "cauliflower",
        "zucchini", "mushroom", "scallion", "cilantro", "basil", "parsley", "lime", "lemon",
        "avocado", "banana", "berries", "strawberr", "pineapple", "apple", "radish", "bok choy",
        "greens", "collard", "sprouts", "pear", "cucumber", "eggplant", "vegetable", "mitsuba",
        "okra", "daikon", "chestnut", "asparagus", "pea")),
    ("Dairy & Eggs", (
        "egg", "milk", "butter", "cheese", "yogurt", "cream", "feta", "mozzarella", "parmesan",
        "cotija", "paneer", "cottage", "kamaboko", "ghee")),
]


def categorize(item: str) -> str:
    """Map an ingredient name to a grocery aisle. Falls back to 'Other'."""
    low = item.lower()
    for category, keywords in CATEGORY_KEYWORDS:
        for kw in keywords:
            if kw in low:
                return category
    return "Other"


CATEGORY_ORDER = ["Produce", "Meat", "Seafood", "Dairy & Eggs", "Bakery & Grains",
                  "Pantry", "Spices & Seasoning", "Other"]

# Pantry/tap staples nobody needs on a shopping list.
_SHOP_SKIP = {"water", "ice", "ice water"}


def aggregate_shopping_list(meals: list[dict]) -> dict:
    """Combine ingredients across meals into a categorized shopping list.

    Groups by (item, unit), summing numeric quantities. Items with no quantity
    ("to taste") become "as needed". Returns an ordered dict: category -> list of
    {"item", "amount"} sorted by item name.
    """
    # key (item_lower, unit) -> {"item": display, "qty": float|None, "unit": str|None,
    #                            "as_needed": bool}
    agg: dict[tuple, dict] = {}
    for meal in meals:
        for ing in meal.get("ingredients", []):
            item = ing["item"]
            if item.strip().lower() in _SHOP_SKIP:
                continue  # nobody buys water or ice
            unit = ing.get("unit")
            qty = ing.get("qty")
            key = (item.lower(), unit)
            entry = agg.setdefault(
                key, {"item": item, "qty": None, "unit": unit, "as_needed": False}
            )
            if qty is None:
                entry["as_needed"] = True
            else:
                entry["qty"] = (entry["qty"] or 0) + qty

    by_category: dict[str, list[dict]] = {}
    for entry in agg.values():
        amount = _format_shop_amount(entry)
        cat = categorize(entry["item"])
        by_category.setdefault(cat, []).append({"item": entry["item"], "amount": amount})

    # Sort items within each category, and emit categories in a sensible aisle order.
    ordered: dict[str, list[dict]] = {}
    for cat in CATEGORY_ORDER:
        if cat in by_category:
            ordered[cat] = sorted(by_category[cat], key=lambda x: x["item"].lower())
    for cat in by_category:  # any unexpected categories last
        if cat not in ordered:
            ordered[cat] = sorted(by_category[cat], key=lambda x: x["item"].lower())
    return ordered


def _format_shop_amount(entry: dict) -> str:
    """Human-friendly amount for a shopping-list line."""
    qty, unit = entry["qty"], entry["unit"]
    if qty is None:
        return "as needed"
    qty_str = f"{qty:g}"
    base = " ".join(part for part in (qty_str, unit) if part)
    if entry["as_needed"]:
        base += " (+ to taste)"
    return base
