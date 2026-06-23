"""Command-line interface for diet-roulette.

Commands:
    spin    spin the wheel for a meal (asks your protein, shows the recipe)
    recipe  look up a meal's full recipe (optionally export to HTML)
    today   show today's accepted picks vs a calorie goal
    list    browse the meal database
    week    generate a weekly meal plan + shopping list (export to cute HTML)
    reset   clear today's log
"""

from __future__ import annotations

import argparse
import random
import sys

from diet_roulette import __version__, prefs as prefs_mod, tracker
from diet_roulette.htmlreport import render_recipe_html, render_week_html, save_html
from diet_roulette.planner import (
    GOAL_RULES,
    aggregate_shopping_list,
    build_week,
    resolve_goal,
    week_totals,
)
from diet_roulette.wheel import (
    BOLD,
    CUISINES,
    CYAN,
    DIM,
    GREEN,
    MEAL_TYPES,
    RESET,
    YELLOW,
    cuisine_label,
    filter_foods,
    format_meal,
    format_recipe,
    lean_subset,
    load_foods,
    matches_any_term,
    meal_for_hour,
    pick,
    spin_animation,
)


def _split_terms(text: str | None) -> list[str]:
    """Parse a comma/space separated free-text list into lowercase terms."""
    if not text:
        return []
    return [t.strip().lower() for t in text.replace(";", ",").split(",") if t.strip()]

GOAL_CHOICES = sorted(GOAL_RULES.keys())


def _bar(pct: int, width: int = 24) -> str:
    pct = max(0, pct)
    filled = min(width, round(pct / 100 * width))
    over = pct > 100
    color = YELLOW if over else GREEN
    return f"{color}{'█' * filled}{DIM}{'░' * (width - filled)}{RESET}"


def _run_bracket(candidates: list[dict], seed: int | None) -> dict:
    """This-or-that: show two meals at a time, let the user pick, bracket to a winner."""
    rng = random.Random(seed)
    field = rng.sample(candidates, min(4, len(candidates)))
    rnd = 1
    while len(field) > 1:
        print(f"\n{BOLD}{CYAN}Round {rnd}{RESET}  {DIM}({len(field)} in the running){RESET}")
        winners: list[dict] = []
        i = 0
        while i < len(field):
            if i + 1 >= len(field):
                winners.append(field[i])  # odd one out gets a bye
                break
            a, b = field[i], field[i + 1]
            print(f"  {BOLD}A){RESET} {a['emoji']}  {a['name']}  {DIM}({a['kcal']} kcal){RESET}")
            print(f"  {BOLD}B){RESET} {b['emoji']}  {b['name']}  {DIM}({b['kcal']} kcal){RESET}")
            ans = input(f"  {BOLD}Which sounds better? [A/b]{RESET} ").strip().lower()
            winners.append(b if ans in ("b", "2") else a)
            i += 2
        field = winners
        rnd += 1
    return field[0]


def cmd_spin(args: argparse.Namespace) -> int:
    foods = load_foods()
    interactive = sys.stdin.isatty() and not args.no_anim and not args.accept
    avoid = _split_terms(args.avoid)
    have = _split_terms(args.have)

    # Clock-aware: if --now and no explicit --meal, pick the meal type from the time.
    meal = args.meal
    if args.now and not meal:
        from datetime import datetime

        now = datetime.now()
        meal = meal_for_hour(now.hour)
        print(f"{DIM}It's {now:%H:%M}, so let's find you something for {meal}.{RESET}")

    # Ask which protein they want, unless passed, in surprise mode, or non-interactive.
    protein = args.protein
    if protein is None and interactive and not args.surprise:
        protein = input(
            f"{BOLD}What protein are you feeling?{RESET} "
            f"{DIM}(steak, chicken, tofu, ground beef… or Enter for any){RESET} "
        ).strip() or None

    # Build the candidate pool.
    if args.surprise:
        # Chaos mode ignores the usual filters, but still respects allergens.
        candidates = [f for f in foods if not matches_any_term(f, avoid)]
        print(f"{CYAN}🎰 Chaos mode: anything goes!{RESET}")
    else:
        candidates = filter_foods(
            foods, meal=meal, max_kcal=args.max_kcal, tag=args.tag,
            cuisine=args.cuisine, protein=protein, avoid=avoid, have=have,
        )
        if args.spicy:
            candidates = [f for f in candidates if "spicy" in f.get("tags", [])]
        if args.quick:
            candidates = [f for f in candidates if "quick" in f.get("tags", [])]
        if args.lean:
            candidates = lean_subset(candidates)

    # No-repeat: drop anything eaten recently, but never empty the wheel over it.
    if args.fresh:
        recent = tracker.recent_names(args.fresh)
        fresh = [f for f in candidates if f["name"] not in recent]
        if fresh:
            candidates = fresh
        elif candidates:
            print(f"{DIM}(You've had everything matching lately, so re-runs are allowed.){RESET}")

    # Rig the wheel: drop blocked meals and weight favorites up (unless opted out).
    weights = None
    if not args.no_rig:
        candidates, weights = prefs_mod.apply_prefs(candidates, prefs_mod.load_prefs())

    if not candidates:
        print("😕 No meals match those filters.", file=sys.stderr)
        if protein:
            without = filter_foods(
                foods, meal=meal, max_kcal=args.max_kcal, tag=args.tag,
                cuisine=args.cuisine, avoid=avoid, have=have,
            )
            if not args.no_rig:
                without, weights = prefs_mod.apply_prefs(without, prefs_mod.load_prefs())
            if without and interactive:
                ans = input(
                    f"Nothing with {BOLD}{protein}{RESET}. "
                    f"Spin without that protein? [y/N] "
                ).strip().lower()
                if ans in ("y", "yes"):
                    candidates = without
        if not candidates:
            return 1

    # This-or-that bracket is its own interactive flow.
    if args.bracket and interactive and len(candidates) >= 2:
        winner = _run_bracket(candidates, args.seed)
        print(f"\n{CYAN}🏆 Your champion:{RESET}\n")
        print(format_recipe(winner))
        ans = input(f"\n{BOLD}Add it to today's plan? [y/N]{RESET} ").strip().lower()
        if ans in ("y", "yes"):
            day = tracker.accept(winner)
            print(f"{GREEN}✓ Added to today's plan ({len(day)} meal(s) so far).{RESET}")
        else:
            print(f"{DIM}No worries, run it back anytime.{RESET}")
        return 0

    # Spin (and re-spin) until the user accepts a meal or bows out.
    while True:
        winner = pick(candidates, seed=args.seed, weights=weights)
        if not args.no_anim:
            spin_animation(candidates, winner)

        print(f"\n{CYAN}🎯 The wheel landed on:{RESET}\n")
        print(format_recipe(winner, mystery=args.mystery))

        if args.accept:
            day = tracker.accept(winner)
            print(f"\n{GREEN}✓ Added to today's plan ({len(day)} meal(s) so far).{RESET}")
            return 0
        if not interactive:
            return 0

        prompt = "Accept this mystery meal? [y/N]" if args.mystery else "Accept this meal? [y/N]"
        ans = input(f"\n{BOLD}{prompt}{RESET} ").strip().lower()
        if args.mystery:
            print(f"{CYAN}🎭 It was {winner['emoji']}  {winner['name']}!{RESET}")
        if ans in ("y", "yes"):
            day = tracker.accept(winner)
            print(f"{GREEN}✓ Added to today's plan ({len(day)} meal(s) so far).{RESET}")
            return 0

        # Declined. Offer another spin (only worthwhile if there's more than one option).
        if len(candidates) < 2:
            print(f"{DIM}That's the only meal matching your filters. Maybe next time!{RESET}")
            return 0
        again = input(f"{BOLD}Re-spin the wheel? [Y/n]{RESET} ").strip().lower()
        if again in ("n", "no"):
            print(f"{DIM}No worries, spin again anytime.{RESET}")
            return 0
        # A fixed seed would just land on the same meal, so drop it on re-spins.
        args.seed = None


def _find_meal(foods: list[dict], query: str) -> dict | list[dict]:
    """Resolve a name query to a single meal, or return a list of candidates."""
    q = query.strip().lower()
    exact = [f for f in foods if f["name"].lower() == q]
    if exact:
        return exact[0]
    starts = [f for f in foods if f["name"].lower().startswith(q)]
    if len(starts) == 1:
        return starts[0]
    contains = [f for f in foods if q in f["name"].lower()]
    if len(contains) == 1:
        return contains[0]
    return contains  # zero or several


def cmd_recipe(args: argparse.Namespace) -> int:
    foods = load_foods()
    result = _find_meal(foods, args.query)
    if isinstance(result, list):
        if not result:
            print(f"No meal matches '{args.query}'. Try `diet-roulette list`.", file=sys.stderr)
            return 1
        print(f"Several meals match '{args.query}', be more specific:")
        for m in result:
            print(f"  {m['emoji']}  {m['name']}  {DIM}({cuisine_label(m)}){RESET}")
        return 1

    meal = result
    if args.save:
        path = save_html(render_recipe_html(meal), args.save)
        print(f"{GREEN}✓ Saved recipe to {path}{RESET}")
    else:
        print(format_recipe(meal))
    return 0


def cmd_today(args: argparse.Namespace) -> int:
    picks = tracker.todays_picks()
    if not picks:
        print("Nothing logged today yet. Run `diet-roulette spin` to get started! 🎲")
        return 0

    print(f"{BOLD}Today's plan:{RESET}")
    for p in picks:
        print(f"  {p.get('emoji', '🍽️')}  {p['name']}  {DIM}({p['kcal']} kcal){RESET}")

    t = tracker.totals(picks)
    print(
        f"\n{BOLD}Totals:{RESET} {t['kcal']} kcal  ·  "
        f"P {t['protein_g']}g  C {t['carbs_g']}g  F {t['fat_g']}g"
    )

    status = tracker.budget_status(picks, args.goal)
    if status["goal"] is not None:
        bar = _bar(status["pct"])
        remaining = status["remaining"]
        msg = (
            f"{GREEN}{remaining} kcal left{RESET}"
            if remaining >= 0
            else f"{YELLOW}{-remaining} kcal over budget{RESET}"
        )
        print(f"Goal:   {bar} {status['consumed']}/{status['goal']} kcal · {msg}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    foods = load_foods()
    candidates = filter_foods(
        foods, meal=args.meal, max_kcal=args.max_kcal, tag=args.tag,
        cuisine=args.cuisine, protein=args.protein,
        avoid=_split_terms(args.avoid), have=_split_terms(args.have),
    )
    if not candidates:
        print("No meals match those filters.", file=sys.stderr)
        return 1
    for meal_type in MEAL_TYPES:
        group = [f for f in candidates if f["meal"] == meal_type]
        if not group:
            continue
        print(f"\n{BOLD}{meal_type.title()}{RESET}")
        for f in group:
            print(
                f"  {f['emoji']}  {f['name']}  "
                f"{DIM}{f['kcal']} kcal · {cuisine_label(f)}{RESET}"
            )
    print()
    return 0


def cmd_week(args: argparse.Namespace) -> int:
    foods = load_foods()
    slots = tuple(s.strip() for s in args.meals.split(",") if s.strip())
    bad = [s for s in slots if s not in MEAL_TYPES]
    if bad or not slots:
        print(f"Invalid --meals {args.meals!r}. Choose from {', '.join(MEAL_TYPES)}.",
              file=sys.stderr)
        return 1

    goal_key, recognized = resolve_goal(args.goal)
    if args.goal and not recognized:
        print(f"{YELLOW}Didn't recognize goal '{args.goal}', using 'balanced'. "
              f"Try: {', '.join(GOAL_CHOICES)}.{RESET}")

    try:
        plan = build_week(
            foods, days=args.days, slots=slots, goal=args.goal,
            cuisine=args.cuisine, protein=args.protein,
            low_energy=args.low_energy, seed=args.seed,
        )
    except ValueError as e:
        print(f"😕 {e}", file=sys.stderr)
        return 1

    label_bits = [f"{args.days} days", f"meals: {', '.join(slots)}"]
    if plan["goal"] != "balanced":
        label_bits.append(f"goal: {plan['goal']}")
    if args.cuisine:
        label_bits.append(cuisine_label({"cuisine": args.cuisine}))
    if args.low_energy:
        label_bits.append("low-energy")
    print(f"{BOLD}{CYAN}🗓  Your week{RESET}  {DIM}({' · '.join(label_bits)}){RESET}\n")

    if plan["goal_relaxed"]:
        print(f"{YELLOW}Heads up: not enough meals fully met the goal, so the plan "
              f"leans toward it as best it can.{RESET}\n")

    for day in plan["days"]:
        print(f"{BOLD}{day['label']}{RESET}")
        for slot, meal in day["meals"]:
            print(
                f"  {DIM}{slot:<9}{RESET} {meal['emoji']}  {meal['name']}  "
                f"{DIM}{meal['kcal']} kcal · fiber {meal.get('fiber_g', 0)}g · "
                f"{cuisine_label(meal)}{RESET}"
            )
    totals = week_totals(plan)
    print(f"\n{BOLD}Weekly:{RESET} ~{totals['avg_kcal_per_day']} kcal/day  ·  "
          f"{totals['total_protein_g']}g protein  ·  {totals['total_fiber_g']}g fiber total")

    shopping = aggregate_shopping_list(plan["all_meals"])
    print(f"\n{BOLD}🛒 Shopping list{RESET}")
    for aisle, items in shopping.items():
        print(f"\n  {CYAN}{aisle}{RESET}")
        for it in items:
            print(f"    ☐ {it['item']}  {DIM}{it['amount']}{RESET}")

    if args.save:
        html = render_week_html(plan, shopping, {"title": args.title})
        path = save_html(html, args.save)
        print(f"\n{GREEN}✓ Saved a cute HTML plan to {path}{RESET}")
        print(f"{DIM}  Open it in a browser, tap a note to see its recipe, "
              f"print to PDF for the fridge.{RESET}")
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    tracker.reset()
    print("🧹 Cleared today's log.")
    return 0


def cmd_favorite(args: argparse.Namespace) -> int:
    """Rig the wheel toward a meal you love (or take it off the favorites)."""
    foods = load_foods()
    result = _find_meal(foods, args.name)
    if isinstance(result, list):
        if not result:
            print(f"No meal matches '{args.name}'. Try `diet-roulette list`.", file=sys.stderr)
        else:
            print(f"Several meals match '{args.name}', be more specific:")
            for m in result:
                print(f"  {m['emoji']}  {m['name']}")
        return 1
    name = result["name"]
    if args.remove:
        prefs_mod.remove_favorite(name)
        print(f"{DIM}Removed {name} from your favorites.{RESET}")
    else:
        prefs_mod.add_favorite(name)
        print(f"{GREEN}⭐ Favorited {name}. The wheel will land on it more often.{RESET}")
    return 0


def cmd_block(args: argparse.Namespace) -> int:
    """Banish a meal from the wheel for good (or lift the ban)."""
    foods = load_foods()
    result = _find_meal(foods, args.name)
    if isinstance(result, list):
        if not result:
            print(f"No meal matches '{args.name}'. Try `diet-roulette list`.", file=sys.stderr)
        else:
            print(f"Several meals match '{args.name}', be more specific:")
            for m in result:
                print(f"  {m['emoji']}  {m['name']}")
        return 1
    name = result["name"]
    if args.remove:
        prefs_mod.remove_blocked(name)
        print(f"{GREEN}Welcome back, {name}. It can show up again.{RESET}")
    else:
        prefs_mod.add_blocked(name)
        print(f"{DIM}🚫 Blocked {name}. The wheel will never land on it.{RESET}")
    return 0


def cmd_prefs(args: argparse.Namespace) -> int:
    """Show your rigged wheel: favorites and blocklist."""
    p = prefs_mod.load_prefs()
    favs, blocked = p.get("favorites", []), p.get("blocked", [])
    print(f"{BOLD}⭐ Favorites{RESET} {DIM}(come up more often){RESET}")
    if favs:
        for n in favs:
            print(f"  • {n}")
    else:
        print(f"  {DIM}none yet. Try: diet-roulette favorite birria{RESET}")
    print(f"\n{BOLD}🚫 Blocked{RESET} {DIM}(never shown){RESET}")
    if blocked:
        for n in blocked:
            print(f"  • {n}")
    else:
        print(f"  {DIM}none yet. Try: diet-roulette block 'century egg'{RESET}")
    return 0


def cmd_welcome(args: argparse.Namespace | None = None) -> int:
    """Friendly overview shown when no command is given."""
    print(f"""{CYAN}{BOLD}🎡 diet-roulette{RESET}  {DIM}v{__version__}{RESET}
Spin the wheel and let fate pick your next healthy meal.

{BOLD}Commands{RESET}
  {GREEN}spin{RESET}      Spin for a meal (asks your protein, shows the recipe)
              {DIM}diet-roulette spin --meal dinner --cuisine korean{RESET}
  {GREEN}recipe{RESET}    Look up a meal's full recipe (or export it to HTML)
              {DIM}diet-roulette recipe birria{RESET}
  {GREEN}week{RESET}      Build a weekly plan + shopping list, export cute HTML
              {DIM}diet-roulette week --goal high-fiber --save week.html{RESET}
  {GREEN}today{RESET}     Show today's accepted picks vs a calorie goal
              {DIM}diet-roulette today --goal 2000{RESET}
  {GREEN}list{RESET}      Browse the meal database
              {DIM}diet-roulette list --cuisine indian{RESET}
  {GREEN}favorite{RESET}  Rig the wheel toward a meal you love ({GREEN}block{RESET} banishes one)
              {DIM}diet-roulette favorite birria   ·   diet-roulette prefs{RESET}
  {GREEN}reset{RESET}     Clear today's log
              {DIM}diet-roulette reset{RESET}

{BOLD}Spin modifiers{RESET}  {DIM}mix and match to keep it interesting{RESET}
  {DIM}--surprise{RESET} chaos pick   {DIM}--spicy{RESET}/{DIM}--quick{RESET}/{DIM}--lean{RESET} vibes   {DIM}--now{RESET} time-of-day
  {DIM}--mystery{RESET} hide the name   {DIM}--bracket{RESET} this-or-that   {DIM}--fresh{RESET} no recent repeats
  {DIM}--have "chicken, rice"{RESET} pantry mode   {DIM}--avoid "pork, cilantro"{RESET} exclude
  {DIM}--protein "ground beef"  --tag one-pot  --cuisine japanese  --seed 7{RESET}

Run {BOLD}diet-roulette <command> -h{RESET} for the full options of any command.
""")
    return 0


def _add_filters(p: argparse.ArgumentParser) -> None:
    p.add_argument("--meal", choices=MEAL_TYPES, help="restrict to a meal type")
    p.add_argument("--max-kcal", type=int, metavar="N", help="cap calories at N")
    p.add_argument("--tag", help="dietary/effort tag, e.g. vegetarian, vegan, "
                                 "high-protein, low-carb, gluten-free, one-pot, crockpot")
    p.add_argument("--cuisine", choices=CUISINES, help="restrict to a cuisine")
    p.add_argument("--protein", help='protein to require, e.g. "chicken", "ground beef", '
                                     '"tofu", "paneer" (free text)')
    p.add_argument("--avoid", metavar='"pork, cilantro"',
                   help="exclude meals mentioning these ingredients (comma list)")
    p.add_argument("--have", metavar='"chicken, rice"',
                   help="pantry mode: only meals you can mostly make from these (comma list)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="diet-roulette",
        description="🎡 Spin the wheel and let fate pick your next healthy meal.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    p_spin = sub.add_parser("spin", help="spin the wheel for a meal")
    _add_filters(p_spin)
    p_spin.add_argument("--surprise", action="store_true",
                        help="chaos mode: ignore filters, pick from anything")
    p_spin.add_argument("--spicy", action="store_true", help="only spicy dishes")
    p_spin.add_argument("--quick", action="store_true", help="only quick (about 30 min) meals")
    p_spin.add_argument("--lean", action="store_true",
                        help="favor the most protein-dense (lean) meals")
    p_spin.add_argument("--now", action="store_true",
                        help="auto-pick the meal type from the current time")
    p_spin.add_argument("--mystery", action="store_true",
                        help="blind spin: hide the name until you decide")
    p_spin.add_argument("--bracket", action="store_true",
                        help="this-or-that: pick between pairs down to a winner")
    p_spin.add_argument("--fresh", type=int, nargs="?", const=3, metavar="DAYS",
                        help="no repeats from the last DAYS days (default 3)")
    p_spin.add_argument("--no-rig", action="store_true",
                        help="ignore your favorites/blocklist for this spin")
    p_spin.add_argument("--no-anim", action="store_true", help="skip the spin animation")
    p_spin.add_argument("--accept", action="store_true", help="auto-add the result to today's plan")
    p_spin.add_argument("--seed", type=int, help="reproducible pick (for testing/sharing)")
    p_spin.set_defaults(func=cmd_spin)

    p_recipe = sub.add_parser("recipe", help="look up a meal's full recipe")
    p_recipe.add_argument("query", help="part of a meal name, e.g. birria")
    p_recipe.add_argument("--save", metavar="FILE.html", help="export the recipe to a cute HTML file")
    p_recipe.set_defaults(func=cmd_recipe)

    p_today = sub.add_parser("today", help="show today's plan and budget")
    p_today.add_argument("--goal", type=int, metavar="KCAL", help="daily calorie goal")
    p_today.set_defaults(func=cmd_today)

    p_list = sub.add_parser("list", help="browse the meal database")
    _add_filters(p_list)
    p_list.set_defaults(func=cmd_list)

    p_week = sub.add_parser("week", help="generate a weekly meal plan + shopping list")
    p_week.add_argument("--days", type=int, default=7, help="number of days (default 7)")
    p_week.add_argument("--meals", default="lunch,dinner",
                        help="comma list of slots per day (default lunch,dinner)")
    p_week.add_argument("--goal", help=f"weekly goal: {', '.join(GOAL_CHOICES)} (or free text)")
    p_week.add_argument("--cuisine", choices=CUISINES, help="restrict to a cuisine")
    p_week.add_argument("--protein", help="protein to require (free text)")
    p_week.add_argument("--low-energy", action="store_true",
                        help="only one-pot / crockpot / sheet-pan / no-cook meals")
    p_week.add_argument("--seed", type=int, help="reproducible plan")
    p_week.add_argument("--save", metavar="FILE.html", help="export a cute HTML plan + shopping list")
    p_week.add_argument("--title", default="My Week of Meals", help="title for the HTML export")
    p_week.set_defaults(func=cmd_week)

    p_reset = sub.add_parser("reset", help="clear today's log")
    p_reset.set_defaults(func=cmd_reset)

    p_fav = sub.add_parser("favorite", help="rig the wheel toward a meal you love")
    p_fav.add_argument("name", help="part of a meal name, e.g. birria")
    p_fav.add_argument("--remove", action="store_true", help="take it off your favorites")
    p_fav.set_defaults(func=cmd_favorite)

    p_block = sub.add_parser("block", help="banish a meal from the wheel")
    p_block.add_argument("name", help="part of a meal name, e.g. 'century egg'")
    p_block.add_argument("--remove", action="store_true", help="lift the ban")
    p_block.set_defaults(func=cmd_block)

    p_prefs = sub.add_parser("prefs", help="show your favorites and blocklist")
    p_prefs.set_defaults(func=cmd_prefs)

    p_help = sub.add_parser("help", help="show the welcome overview")
    p_help.set_defaults(func=cmd_welcome)

    return parser


def _force_utf8() -> None:
    """Windows consoles often default to cp1252, which can't encode emoji.

    Reconfigure stdout/stderr to UTF-8 (replacing anything unencodable) so the
    fun stuff renders instead of crashing.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv: list[str] | None = None) -> int:
    _force_utf8()
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "command", None) is None:
        return cmd_welcome()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
