"""Cute, self-contained HTML export: a fridge wall of sticky-note recipe cards.

Design grounded in the user's own design books:
- Warm, appetite-appeal palette (Robin Landa, Graphic Design Solutions): warm analogous
  pastels on a cream cork background.
- Unity through repetition with playful asymmetry (Beaird, Principles of Beautiful Web
  Design): identical note cards, each gently rotated, with a paper-tape accent.
- Readable type and measure (Rutter, Web Typography): system fonts, ~1.5 line-height,
  recipe steps capped near a 66-character measure.

No JavaScript: clicking a note expands its recipe via the native <details> element.
No external assets: all CSS is inline so the file is portable and prints cleanly to PDF.
"""

from __future__ import annotations

from html import escape as E
from pathlib import Path

from diet_roulette.planner import week_totals
from diet_roulette.wheel import cuisine_label, format_amount

# Rotating sticky-note pastels and tilt angles (cycled by card index).
_NOTE_COLORS = ["#ffe3c2", "#ffd9d2", "#fff1bf", "#d8efd3", "#dbe9ff"]
_NOTE_TILTS = ["-2.2deg", "1.6deg", "-1deg", "2.1deg", "-1.7deg", "1.1deg"]

_STYLE = """
:root {
  --cream: #fff8f0; --ink: #3a2a1e; --terra: #e8743b; --muted: #8a766a;
  --tape: rgba(255,255,255,0.55);
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 0 16px 64px;
  font-family: system-ui, "Segoe UI", Verdana, sans-serif;
  font-size: 16px; line-height: 1.5; color: var(--ink);
  background-color: var(--cream);
  background-image:
    radial-gradient(rgba(192,142,90,0.22) 1.1px, transparent 1.2px),
    radial-gradient(rgba(192,142,90,0.16) 1.1px, transparent 1.2px);
  background-size: 22px 22px, 22px 22px;
  background-position: 0 0, 11px 11px;
}
.wrap { max-width: 1100px; margin: 0 auto; }
header.banner {
  text-align: center; margin: 0 auto 8px; padding: 28px 16px 12px;
}
header.banner h1 {
  font-family: "Trebuchet MS", "Segoe UI", system-ui, sans-serif;
  font-size: 2.1rem; line-height: 1.2; margin: 0 0 6px; letter-spacing: .3px;
}
header.banner .sub { color: var(--muted); font-size: 1rem; }
.notice {
  max-width: 640px; margin: 4px auto 18px; padding: 8px 14px;
  background: #fff5d6; border: 1px dashed #e0b84a; border-radius: 10px;
  font-size: .9rem; color: #7a5b12; text-align: center;
}
.wall {
  display: grid; gap: 20px; padding: 12px 0 28px;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}
.note {
  background: var(--note, #ffe3c2);
  border-radius: 6px; padding: 16px 16px 14px; position: relative;
  box-shadow: 2px 5px 10px rgba(80,50,20,0.18);
  transform: rotate(var(--tilt, 0deg));
  transition: transform .12s ease, box-shadow .12s ease;
}
.note::before {
  content: ""; position: absolute; top: -9px; left: 50%;
  width: 78px; height: 20px; transform: translateX(-50%) rotate(-1.5deg);
  background: var(--tape); box-shadow: 0 1px 2px rgba(0,0,0,0.08);
}
.note[open], .note:hover { transform: rotate(0deg); box-shadow: 3px 8px 16px rgba(80,50,20,0.26); }
.note summary {
  list-style: none; cursor: pointer; outline: none;
}
.note summary::-webkit-details-marker { display: none; }
.note .emoji { font-size: 1.7rem; }
.note .title {
  font-family: "Trebuchet MS", "Segoe UI", system-ui, sans-serif;
  font-weight: 700; font-size: 1.06rem; margin: 4px 0 6px;
}
.badge {
  display: inline-block; font-size: .72rem; padding: 1px 8px; border-radius: 999px;
  background: rgba(58,42,30,0.12); color: var(--ink); margin-right: 6px;
}
.stats { font-size: .82rem; color: #6a5446; margin-top: 6px; }
.hint { font-size: .76rem; color: #9a7f55; margin-top: 8px; font-style: italic; }
.note[open] .hint { display: none; }
.note-body { margin-top: 12px; border-top: 1px solid rgba(58,42,30,0.18); padding-top: 10px; }
.note-body h4 {
  margin: 8px 0 4px; font-size: .82rem; text-transform: uppercase;
  letter-spacing: .06em; color: var(--terra);
}
.note-body ul { margin: 0 0 4px; padding-left: 18px; }
.note-body ol { margin: 0; padding-left: 18px; max-width: 66ch; }
.note-body li { margin: 2px 0; font-size: .9rem; }
.day-tag {
  font-family: "Trebuchet MS", "Segoe UI", system-ui, sans-serif;
  font-weight: 700; color: var(--terra); font-size: .82rem; letter-spacing: .04em;
}
section.shopping {
  max-width: 820px; margin: 28px auto 0; background: #fffdf8;
  border-radius: 14px; padding: 22px 26px; box-shadow: 0 4px 14px rgba(80,50,20,0.12);
}
section.shopping h2 {
  font-family: "Trebuchet MS", "Segoe UI", system-ui, sans-serif;
  margin: 0 0 4px; font-size: 1.4rem;
}
.aisles { columns: 2; column-gap: 32px; margin-top: 12px; }
.aisle { break-inside: avoid; margin-bottom: 14px; display: inline-block; width: 100%; }
.aisle h3 {
  font-size: .82rem; text-transform: uppercase; letter-spacing: .06em;
  color: var(--terra); margin: 0 0 6px; border-bottom: 1px solid #f0e4d4; padding-bottom: 3px;
}
.check { display: flex; align-items: baseline; gap: 8px; margin: 3px 0; font-size: .92rem; }
.check input { width: 16px; height: 16px; accent-color: var(--terra); flex: none; }
.check label { cursor: pointer; }
.check input:checked + label { text-decoration: line-through; color: #b3a395; }
.check .amt { color: var(--muted); font-size: .82rem; }
footer { text-align: center; color: var(--muted); font-size: .8rem; margin-top: 32px; }
@media print {
  body { background: #fff; }
  .note { transform: none !important; box-shadow: none !important; border: 1px solid #e7d8c4; break-inside: avoid; }
  .note::before { display: none; }
  .note-body { display: block !important; }
  .hint { display: none !important; }
  .wall { gap: 12px; }
  section.shopping { box-shadow: none; border: 1px solid #e7d8c4; break-inside: avoid; }
  .check input { -webkit-appearance: none; appearance: none; width: 12px; height: 12px; border: 1px solid #555; border-radius: 2px; }
}
"""


def _doc(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{E(title)}</title>\n<style>{_STYLE}</style>\n</head>\n<body>\n"
        f"{body}\n</body>\n</html>\n"
    )


def _note(meal: dict, index: int, day_tag: str = "", open_: bool = False) -> str:
    """Render one sticky-note <details> card for a meal."""
    color = _NOTE_COLORS[index % len(_NOTE_COLORS)]
    tilt = _NOTE_TILTS[index % len(_NOTE_TILTS)]
    badge = cuisine_label(meal)
    tag_html = f'<div class="day-tag">{E(day_tag)}</div>' if day_tag else ""

    ings = "".join(
        f"<li>{E(format_amount(i))} &middot; {E(i['item'])}</li>"
        for i in meal.get("ingredients", [])
    )
    steps = "".join(f"<li>{E(s)}</li>" for s in meal.get("steps", []))

    return (
        f'<details class="note" style="--note:{color};--tilt:{tilt}"'
        f'{" open" if open_ else ""}>'
        f'<summary>'
        f"{tag_html}"
        f'<div class="emoji">{E(meal.get("emoji", "🍽️"))}</div>'
        f'<div class="title">{E(meal["name"])}</div>'
        f'<div><span class="badge">{E(badge)}</span>'
        f'<span class="badge">{E(meal["meal"])}</span></div>'
        f'<div class="stats">{meal["kcal"]} kcal &middot; '
        f'P {meal["protein_g"]}g &middot; Fiber {meal.get("fiber_g", 0)}g</div>'
        f'<div class="hint">tap to see the recipe</div>'
        f"</summary>"
        f'<div class="note-body">'
        f"<h4>Ingredients</h4><ul>{ings}</ul>"
        f"<h4>Steps</h4><ol>{steps}</ol>"
        f"</div>"
        f"</details>"
    )


def _shopping_html(shopping_list: dict) -> str:
    if not shopping_list:
        return ""
    aisles = []
    cid = 0
    for aisle, items in shopping_list.items():
        rows = []
        for it in items:
            cid += 1
            box = f"shop-{cid}"
            rows.append(
                f'<div class="check"><input type="checkbox" id="{box}">'
                f'<label for="{box}">{E(it["item"])} '
                f'<span class="amt">{E(it["amount"])}</span></label></div>'
            )
        aisles.append(
            f'<div class="aisle"><h3>{E(aisle)}</h3>{"".join(rows)}</div>'
        )
    return (
        '<section class="shopping"><h2>🛒 Shopping list</h2>'
        f'<div class="aisles">{"".join(aisles)}</div></section>'
    )


def render_week_html(plan: dict, shopping_list: dict, meta: dict | None = None) -> str:
    """Build the full weekly-plan HTML page: sticky-note wall + shopping list."""
    meta = meta or {}
    title = meta.get("title", "My Week of Meals")
    totals = week_totals(plan)

    sub_bits = [f"{plan['params']['days']} days"]
    if plan["goal"] != "balanced":
        sub_bits.append(f"goal: {plan['goal']}")
    if plan["params"].get("cuisine"):
        sub_bits.append(cuisine_label({"cuisine": plan["params"]["cuisine"]}))
    if plan["params"].get("low_energy"):
        sub_bits.append("low-energy")
    sub_bits.append(f"~{totals['avg_kcal_per_day']} kcal/day")
    sub = " &middot; ".join(E(b) for b in sub_bits)

    notice = ""
    if plan.get("goal_relaxed"):
        notice = (
            '<div class="notice">Not enough meals fully matched the goal, so this '
            "plan leans toward it as best it can. Add more matching recipes for a "
            "stricter week.</div>"
        )

    notes = []
    idx = 0
    for day in plan["days"]:
        for slot, meal in day["meals"]:
            tag = f"{day['label']} · {slot}"
            notes.append(_note(meal, idx, day_tag=tag))
            idx += 1

    body = (
        '<div class="wrap">'
        f'<header class="banner"><h1>🎡 {E(title)}</h1>'
        f'<div class="sub">{sub}</div></header>'
        f"{notice}"
        f'<div class="wall">{"".join(notes)}</div>'
        f"{_shopping_html(shopping_list)}"
        '<footer>Made with diet-roulette &middot; tap a note to open its recipe, '
        "then print to PDF to take it shopping.</footer>"
        "</div>"
    )
    return _doc(title, body)


def render_recipe_html(meal: dict, meta: dict | None = None) -> str:
    """Build a single-recipe HTML page (one open sticky note, centered)."""
    meta = meta or {}
    title = meta.get("title", meal["name"])
    body = (
        '<div class="wrap">'
        f'<header class="banner"><h1>{E(meal.get("emoji", "🍽️"))} {E(meal["name"])}</h1>'
        f'<div class="sub">{E(cuisine_label(meal))} &middot; {E(meal["meal"])} &middot; '
        f'makes {meal.get("servings", 1)}</div></header>'
        '<div class="wall" style="grid-template-columns:minmax(260px,520px);justify-content:center">'
        f"{_note(meal, 0, open_=True)}"
        "</div>"
        '<footer>Made with diet-roulette</footer>'
        "</div>"
    )
    return _doc(title, body)


def save_html(text: str, path: str | Path) -> Path:
    """Write an HTML string to a file (UTF-8) and return the resolved path."""
    p = Path(path).expanduser()
    if p.suffix.lower() not in (".html", ".htm"):
        p = p.with_suffix(".html")
    p.write_text(text, encoding="utf-8")
    return p.resolve()
