"""Command-line interface for diet-roulette.

Commands:
    spin   spin the wheel for a meal (with optional filters)
    today  show today's accepted picks vs a calorie goal
    list   browse the meal database
    reset  clear today's log
"""

from __future__ import annotations

import argparse
import sys

from diet_roulette import __version__, tracker
from diet_roulette.wheel import (
    BOLD,
    CYAN,
    DIM,
    GREEN,
    MEAL_TYPES,
    RESET,
    YELLOW,
    filter_foods,
    format_meal,
    load_foods,
    pick,
    spin_animation,
)


def _bar(pct: int, width: int = 24) -> str:
    pct = max(0, pct)
    filled = min(width, round(pct / 100 * width))
    over = pct > 100
    color = YELLOW if over else GREEN
    return f"{color}{'█' * filled}{DIM}{'░' * (width - filled)}{RESET}"


def cmd_spin(args: argparse.Namespace) -> int:
    foods = load_foods()
    candidates = filter_foods(foods, meal=args.meal, max_kcal=args.max_kcal, tag=args.tag)
    if not candidates:
        print("😕 No meals match those filters. Try loosening them.", file=sys.stderr)
        return 1

    winner = pick(candidates, seed=args.seed)
    if not args.no_anim:
        spin_animation(candidates, winner)

    print(f"\n{CYAN}🎯 The wheel landed on:{RESET}\n")
    print(format_meal(winner))

    if args.accept:
        day = tracker.accept(winner)
        print(f"\n{GREEN}✓ Added to today's plan ({len(day)} meal(s) so far).{RESET}")
    elif sys.stdin.isatty() and not args.no_anim:
        ans = input(f"\n{BOLD}Accept this meal? [y/N]{RESET} ").strip().lower()
        if ans in ("y", "yes"):
            day = tracker.accept(winner)
            print(f"{GREEN}✓ Added to today's plan ({len(day)} meal(s) so far).{RESET}")
        else:
            print(f"{DIM}No worries — spin again anytime.{RESET}")
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
        print(f"Goal:   {bar} {status['consumed']}/{status['goal']} kcal — {msg}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    foods = load_foods()
    candidates = filter_foods(foods, meal=args.meal, max_kcal=args.max_kcal, tag=args.tag)
    if not candidates:
        print("No meals match those filters.", file=sys.stderr)
        return 1
    for meal_type in MEAL_TYPES:
        group = [f for f in candidates if f["meal"] == meal_type]
        if not group:
            continue
        print(f"\n{BOLD}{meal_type.title()}{RESET}")
        for f in group:
            print(f"  {f['emoji']}  {f['name']}  {DIM}{f['kcal']} kcal{RESET}")
    print()
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    tracker.reset()
    print("🧹 Cleared today's log.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="diet-roulette",
        description="🎡 Spin the wheel and let fate pick your next healthy meal.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    # Shared filter args for spin/list.
    def add_filters(p: argparse.ArgumentParser) -> None:
        p.add_argument("--meal", choices=MEAL_TYPES, help="restrict to a meal type")
        p.add_argument("--max-kcal", type=int, metavar="N", help="cap calories at N")
        p.add_argument("--tag", help="dietary tag, e.g. vegetarian, vegan, high-protein, low-carb, gluten-free")

    p_spin = sub.add_parser("spin", help="spin the wheel for a meal")
    add_filters(p_spin)
    p_spin.add_argument("--no-anim", action="store_true", help="skip the spin animation")
    p_spin.add_argument("--accept", action="store_true", help="auto-add the result to today's plan")
    p_spin.add_argument("--seed", type=int, help="reproducible pick (for testing/sharing)")
    p_spin.set_defaults(func=cmd_spin)

    p_today = sub.add_parser("today", help="show today's plan and budget")
    p_today.add_argument("--goal", type=int, metavar="KCAL", help="daily calorie goal")
    p_today.set_defaults(func=cmd_today)

    p_list = sub.add_parser("list", help="browse the meal database")
    add_filters(p_list)
    p_list.set_defaults(func=cmd_list)

    p_reset = sub.add_parser("reset", help="clear today's log")
    p_reset.set_defaults(func=cmd_reset)

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
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
