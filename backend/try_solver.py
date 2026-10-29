from pathlib import Path
from config import TERM_CODE
from solver import Constraints, generate_schedules, load_term

DAYS = "MTWRFSU"


def hhmm(mins):
    return "TBA" if mins is None else f"{mins // 60:02d}:{mins % 60:02d}"


def show(schedule):
    for s in sorted(schedule, key=lambda s: (s["course"], s["type"] or "")):
        label = f"   {s['course']:<11}{(s['type'] or ''):<12}CRN {s['crn']}"
        if not s["meetings"]:
            print(label, " (no meeting time)")
        for m in s["meetings"]:
            days = "".join(DAYS[d] for d in m["days"]) or "-"
            print(label, f" {days:<5}{hhmm(m['start'])}-{hhmm(m['end'])}")


term = load_term(Path(__file__).parent / "data" / f"term_{TERM_CODE}.json")

COURSES = ["CS 18000", "MA 16100", "ENGL 10600"]   # swap in courses you actually want
constraints = Constraints(earliest_start=9 * 60)   # nothing before 9:00

try:
    result = generate_schedules(term, COURSES, constraints, max_solutions=5)
except ValueError as e:
    raise SystemExit(f"Problem: {e}")

print(result.message)
for i, sched in enumerate(result.schedules, 1):
    print(f"\nSchedule {i}")
    show(sched)
    