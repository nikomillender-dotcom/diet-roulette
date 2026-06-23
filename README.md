# 🎡 diet-roulette

> Can't decide what to eat? **Spin the wheel** and let fate pick a healthy meal for you.

A fun little command-line diet app. Spin for a meal, tell it what protein you're
feeling, and it lands on something that fits, then shows you the **full recipe**
(ingredients with amounts + steps). Build a whole **weekly meal plan** with an
aggregated **shopping list**, and export it as a **cute, self-contained HTML page**
(fridge sticky-notes you can click to open each recipe, and print to PDF).

**Zero dependencies.** Pure Python standard library: nothing to `pip install` to run it.

```
🎯 The wheel landed on:

🥩  Beef in Its Juices (Carne en su jugo estilo Jalisco)  (lunch · Mexican (Jalisco))
   480 kcal  ·  P 40g  C 20g  F 26g  Fiber 6g  ·  one-pot, gluten-free, high-protein
   makes 4 serving(s)

Ingredients
  • 2 lb  beef sirloin or top round
  • 7 oz  bacon
  • 7 oz  tomatillos
  ...
```

## Install

Requires Python 3.9+.

Run straight from source, no install needed:

```bash
git clone https://github.com/nikomillender-dotcom/diet-roulette.git
cd diet-roulette
python -m diet_roulette          # shows the welcome screen
```

Or install it as a `diet-roulette` command:

```bash
pip install -e .
diet-roulette
```

## Commands

Run `diet-roulette` with no arguments for a welcome screen listing everything.

| Command | What it does |
|---------|--------------|
| `spin` | Spin for a meal. Asks what protein you want, then shows the full recipe. |
| `recipe <name>` | Look up a meal's full recipe (optionally `--save` to HTML). |
| `week` | Generate a weekly plan + shopping list, optionally export to cute HTML. |
| `today` | Show today's accepted picks vs a calorie budget. |
| `list` | Browse the meal database. |
| `reset` | Clear today's log. |

### Spin

```bash
diet-roulette spin
# It asks: "What protein are you feeling?"  ->  type "ground beef", "tofu", "salmon"...

diet-roulette spin --cuisine korean --meal dinner
diet-roulette spin --protein "ground beef" --no-anim     # scriptable, no prompt
diet-roulette spin --tag one-pot --accept                # add straight to today's plan
```

The protein picker is free text and forgiving: `beef` matches everything beefy, while
`ground beef` only spins meals that actually use ground beef. Odd inputs like `paneer`
or `oxtail` work too (it checks the ingredient lists).

Don't like what it landed on? Say `n` to "Accept this meal?" and it asks **"Re-spin the
wheel?"**, so you can keep spinning until something sounds good (no need to re-run anything).

### Weekly plan + shopping list

```bash
# A 7-day lunch+dinner plan that skews high-fiber, saved as a cute HTML page
diet-roulette week --goal high-fiber --save week.html

# Low-energy week: only one-pot / crockpot / sheet-pan / no-cook meals
diet-roulette week --low-energy --days 5 --meals dinner

# A Korean week
diet-roulette week --cuisine korean --seed 7
```

Goals understand free text: `high-fiber`, `high-protein`, `low-carb`, `low-calorie`
(plus synonyms like `keto`, `light`, `fiber`). The shopping list combines ingredients
across the week and groups them by grocery aisle.

The HTML export is a single self-contained file (no JavaScript, no external assets):
a warm "fridge wall" of tilted sticky-note cards. **Click a note to open its recipe**,
tick off the shopping checklist, and print to PDF to take it with you.

### Recipes

```bash
diet-roulette recipe birria              # print the recipe
diet-roulette recipe "dal tadka" --save dal.html
```

## Cuisines

The database has **130+ meals**: everyday healthy staples plus non-standard,
culture-specific dishes, fact-checked against authentic (often native-language) sources
and built out from a shelf of real cookbooks:

- **Mexican** (Guadalajara/Jalisco + Colima): birria, torta ahogada, carne en su jugo,
  pozole rojo, tatemado de Colima, sopitos colimenses
- **Japanese**: nikujaga, oyakodon, gyudon, Japanese curry, plus takeout favorites
  (tonkotsu ramen, katsudon, gyoza, chicken teriyaki, yaki udon, tempura) and miso dishes
- **Korean**: doenjang-jjigae, kimchi-jjigae, bibimbap, bulgogi, dak-bokkeum-tang, japchae
- **Chinese**: mapo tofu, hong shao rou, beef & broccoli, cashew chicken, mu shu pork,
  scallops in black bean sauce, lo mein, and more
- **African** (Congolese): moambe chicken, egusi soup, madesu stew, eggplant curry,
  coupe coupe, plantains in coconut milk
- **Black American (soul)**: red beans & rice, gumbo, smothered chicken, collard greens,
  shrimp & grits, jambalaya
- **Country US (Southern)**: chicken & dumplings, pot roast, beef stew, meatloaf,
  chicken-fried steak, biscuits & gravy
- **Indian**: chana masala, rajma, dal tadka, saag paneer, aloo gobi, chicken tikka masala

Plus loads of **everyday** dishes drawn from air-fryer, high-protein/bodybuilding, and
sugar-free cookbooks, tagged so you can filter for them (`--tag air-fryer`,
`--tag sugar-free`, `--tag high-protein`, `--tag keto`).

Filter any command with `--cuisine`, and browse with `diet-roulette list --cuisine indian`.

## How it works

- **Meals** live in [`diet_roulette/data/foods.json`](diet_roulette/data/foods.json):
  edit it to add your own (each meal has macros incl. fiber, dietary tags, a cuisine,
  protein tokens, and a recipe with ingredient amounts + steps).
- **Today's picks** are saved to `~/.diet-roulette/today.json`, keyed by date.
- The wheel animation only plays in an interactive terminal; piped output stays clean.

## Develop & test

```bash
pip install -e ".[dev]"
pytest -q
```

## License

MIT, see [LICENSE](LICENSE).
