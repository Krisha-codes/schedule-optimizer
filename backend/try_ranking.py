from pathlib import Path
from config import TERM_CODE
from display import show
from ranking import Preferences, rank_schedules
from solver import Constraints, load_term

term = load_term(Path(__file__).parent / "data" / f"term_{TERM_CODE}.json")

COURSES = ["CS 18000", "MA 16100", "ENGL 10800"]   # use courses that exist in your data
constraints = Constraints(earliest_start=8 * 60)    # hard rule: nothing before 8:00
prefs = Preferences(preferred_start=10 * 60, w_days=60, w_spread=1)

try:
    result = rank_schedules(term, COURSES, constraints, prefs, top_n=5)
except ValueError as e:
    raise SystemExit(f"Problem: {e}")

print(result.message)
for i, (sched, b) in enumerate(zip(result.schedules, result.breakdowns), 1):
    print(f"\n#{i}  score {b['total']}  (days {b['days']}, spread {b['spread']}, "
          f"early {b['early']}, late {b['late']}, instructor {b['instructor']})")
    show(sched)

    