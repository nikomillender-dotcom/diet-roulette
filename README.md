# 🎡 diet-roulette

> Can't decide what to eat? **Spin the wheel** and let fate pick a healthy meal for you.

A fun little command-line diet app. It keeps a curated database of genuinely
healthy meals, spins an animated wheel in your terminal, and lands on something
that fits your goal — by meal type, calorie cap, or dietary tag. Accept your
picks and it doubles as a lightweight daily food tracker with a calorie budget.

**Zero dependencies.** Pure Python standard library — nothing to `pip install` to run it.

```
🎯 The wheel landed on:

🐟  Baked salmon with asparagus  (dinner)
   480 kcal  ·  P 40g  C 12g  F 28g  ·  high-protein, low-carb, gluten-free
```

## Install

Requires Python 3.9+.

Run straight from source — no install needed:

```bash
git clone https://github.com/<your-username>/diet-roulette.git
cd diet-roulette
python -m diet_roulette spin
```

Or install it as a `diet-roulette` command:

```bash
pip install -e .
diet-roulette spin
```

## Usage

```bash
# Spin for anything
diet-roulette spin

# Spin for a specific meal, under a calorie cap, vegetarian only
diet-roulette spin --meal lunch --max-kcal 500 --tag vegetarian

# Spin and auto-add to today's plan (no prompt, no animation)
diet-roulette spin --meal dinner --accept --no-anim

# See today's plan vs a 2000 kcal goal
diet-roulette today --goal 2000

# Browse the whole meal database
diet-roulette list --tag high-protein

# Start the day fresh
diet-roulette reset
```

### Flags for `spin` / `list`

| Flag | Description |
|------|-------------|
| `--meal {breakfast,lunch,dinner,snack}` | restrict to a meal type |
| `--max-kcal N` | only meals at or under N calories |
| `--tag TAG` | `vegetarian`, `vegan`, `high-protein`, `low-carb`, `gluten-free` |
| `--no-anim` | skip the spin animation (good for scripts/piping) |
| `--accept` | add the result straight to today's plan |
| `--seed N` | reproducible pick — share a meal with a friend by sharing the seed |

## How it works

- **Meals** live in [`diet_roulette/data/foods.json`](diet_roulette/data/foods.json) — edit it to add your own.
- **Today's picks** are saved to `~/.diet-roulette/today.json`, keyed by date.
- The wheel animation only plays in an interactive terminal; piped output stays clean.

## Develop & test

```bash
pip install -e ".[dev]"
pytest -q
```

## License

MIT — see [LICENSE](LICENSE).
