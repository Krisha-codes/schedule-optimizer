"""Rank schedules by soft preferences (lower score = better).

Hard rules live in solver.py. Here we add an objective to the same CP-SAT model,
ask for the best schedule, forbid it, ask again, and so on.
"""
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from solver import Constraints, _build_model


@dataclass
class Preferences:
    preferred_start: int = 9 * 60    # classes starting earlier than this are penalised
    preferred_end: int = 17 * 60     # classes ending later than this are penalised
    preferred_instructors: set[str] = field(default_factory=set)
    avoided_instructors: set[str] = field(default_factory=set)
    # Weights must be whole numbers. 0 switches a preference off.
    w_early: int = 1         # per minute, per class day, before preferred_start
    w_late: int = 1          # per minute, per class day, after preferred_end
    w_days: int = 60         # per day on campus
    w_spread: int = 1        # per minute from a day's first start to its last end
    w_instructor: int = 100  # bonus per section with a preferred instructor, penalty per avoided


@dataclass
class RankedResult:
    schedules: list          # best first
    breakdowns: list         # one dict per schedule: early, late, days, spread, instructor, total
    message: str = ""
    proven_optimal: bool = True


def _timed(m):
    return m["start"] is not None and m["end"] is not None


def evaluate(schedule, p):
    """Score one schedule in plain Python. The solver's objective must equal this."""
    early = late = instr = 0
    day_first, day_last = {}, {}
    for s in schedule:
        for m in s["meetings"]:
            if not _timed(m):
                continue
            n_days = len(m["days"])
            early += n_days * max(0, p.preferred_start - m["start"])
            late += n_days * max(0, m["end"] - p.preferred_end)
            for d in m["days"]:
                day_first[d] = min(day_first.get(d, m["start"]), m["start"])
                day_last[d] = max(day_last.get(d, m["end"]), m["end"])
        names = {n for m in s["meetings"] for n in m["instructors"]}
        if names & p.preferred_instructors:
            instr -= 1
        if names & p.avoided_instructors:
            instr += 1
    parts = {
        "early": p.w_early * early,
        "late": p.w_late * late,
        "days": p.w_days * len(day_first),
        "spread": p.w_spread * sum(day_last[d] - day_first[d] for d in day_first),
        "instructor": p.w_instructor * instr,
    }
    parts["total"] = sum(parts.values())
    return parts


def rank_schedules(term, codes, constraints=None, prefs=None, top_n=5,
                   link_by_class=True, time_limit=10.0):
    c = constraints or Constraints()
    p = prefs or Preferences()
    model, x, sec, problem = _build_model(term, codes, c, link_by_class)
    if problem:
        return RankedResult([], [], problem)

    terms = []  # pieces of the objective

    # 1. Costs that depend on a single section: early, late, instructors.
    for crn, v in x.items():
        s = sec[crn]
        cost = 0
        for m in s["meetings"]:
            if not _timed(m):
                continue
            n_days = len(m["days"])
            cost += p.w_early * n_days * max(0, p.preferred_start - m["start"])
            cost += p.w_late * n_days * max(0, m["end"] - p.preferred_end)
        names = {n for m in s["meetings"] for n in m["instructors"]}
        if names & p.preferred_instructors:
            cost -= p.w_instructor
        if names & p.avoided_instructors:
            cost += p.w_instructor
        if cost:
            terms.append(cost * v)

    # 2. Costs that depend on the whole day: days on campus and time on campus.
    for d in range(7):
        timed = [(crn, m) for crn, s in sec.items() for m in s["meetings"]
                 if _timed(m) and d in m["days"]]
        if not timed:
            continue
        used = model.new_bool_var(f"used_{d}")        # any class on day d?
        first = model.new_int_var(0, 1440, f"first_{d}")
        last = model.new_int_var(0, 1440, f"last_{d}")
        span = model.new_int_var(0, 1440, f"span_{d}")
        for crn, m in timed:
            model.add_implication(x[crn], used)
            model.add(first <= m["start"]).only_enforce_if(x[crn])
            model.add(last >= m["end"]).only_enforce_if(x[crn])
        model.add(span >= last - first).only_enforce_if(used)
        terms.append(p.w_days * used)
        terms.append(p.w_spread * span)

    total = model.new_int_var(-10**9, 10**9, "total")
    model.add(total == sum(terms))
    model.minimize(total)

    # Best schedule, then forbid it and ask for the next best, top_n times.
    schedules, breakdowns = [], []
    all_optimal = True
    for _ in range(top_n):
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit
        status = solver.solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break  # no more schedules
        chosen = [crn for crn, v in x.items() if solver.boolean_value(v)]
        schedule = [sec[crn] for crn in chosen]
        breakdown = evaluate(schedule, p)
        if status == cp_model.OPTIMAL:
            if breakdown["total"] != solver.value(total):
                raise RuntimeError("Scoring mismatch between solver and evaluate() (a bug).")
        else:
            all_optimal = False
        schedules.append(schedule)
        breakdowns.append(breakdown)
        model.add_bool_or([x[crn].negated() for crn in chosen])  # forbid this exact schedule

    if not schedules:
        return RankedResult([], [], "No conflict-free schedule exists for these courses and constraints.")
    msg = f"Top {len(schedules)} schedule(s), best first (lower score is better)."
    if not all_optimal:
        msg += " Time limit reached, so the order may not be perfect."
    return RankedResult(schedules, breakdowns, msg, all_optimal)
