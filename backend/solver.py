"""Schedule solver.

For every requested course the student needs ONE complete "option":
  - an option is a Class (a lecture plus the labs/recitations linked to it)
  - inside it, exactly one section of each type (one Lecture, one Laboratory, ...)
Then no two chosen sections may overlap in time, and the hard constraints must hold.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

from ortools.sat.python import cp_model

# If two section types are alternatives to each other (e.g. in-person vs online),
# map them to the same name here. Empty for now; we fill it in after inspecting the data.
TYPE_ALIASES: dict[str, str] = {}


@dataclass
class Constraints:
    earliest_start: int | None = None   # minutes after midnight, e.g. 9 * 60
    latest_end: int | None = None
    free_days: set[int] = field(default_factory=set)                   # 0 = Monday ... 6 = Sunday
    blocked: list[tuple[int, int, int]] = field(default_factory=list)  # (day, start, end)
    avoid_crns: set[str] = field(default_factory=set)
    required_crns: set[str] = field(default_factory=set)


@dataclass
class Result:
    schedules: list          # each schedule is a list of section dicts (with a "course" key added)
    message: str = ""
    hit_cap: bool = False    # True if we stopped at max_solutions (more may exist)


def load_term(path):
    return json.loads(Path(path).read_text())


def meetings_overlap(a, b):
    if None in (a["start"], a["end"], b["start"], b["end"]):
        return False  # online / TBA meetings can't collide with anything
    if not set(a["days"]) & set(b["days"]):
        return False
    if not (a["start"] < b["end"] and b["start"] < a["end"]):
        return False  # back-to-back (end == start) is NOT a conflict
    # Half-semester sections only conflict if their date ranges overlap.
    if a["start_date"] and a["end_date"] and b["start_date"] and b["end_date"]:
        return a["start_date"] <= b["end_date"] and b["start_date"] <= a["end_date"]
    return True


def sections_conflict(s1, s2):
    return any(meetings_overlap(m1, m2) for m1 in s1["meetings"] for m2 in s2["meetings"])


def section_allowed(sec, c):
    """Does this section satisfy the hard constraints on its own?"""
    if sec["crn"] in c.avoid_crns:
        return False
    for m in sec["meetings"]:
        if m["start"] is None or m["end"] is None:
            continue
        if c.earliest_start is not None and m["start"] < c.earliest_start:
            return False
        if c.latest_end is not None and m["end"] > c.latest_end:
            return False
        if set(m["days"]) & c.free_days:
            return False
        for day, b_start, b_end in c.blocked:
            if day in m["days"] and m["start"] < b_end and b_start < m["end"]:
                return False
    return True


def build_options(term, codes, c, link_by_class):
    """For each course: a list of usable options. An option maps type -> allowed sections."""
    all_crns = {s["crn"] for code in codes for s in term[code]["sections"]}
    missing = c.required_crns - all_crns
    if missing:
        raise ValueError(f"Required CRN(s) not found in the chosen courses: {sorted(missing)}")

    options = {}
    for code in codes:
        required_here = {s["crn"] for s in term[code]["sections"]} & c.required_crns
        raw = {}  # option id -> type -> sections
        for s in term[code]["sections"]:
            opt_id = s["class_id"] if link_by_class else "all"
            typ = TYPE_ALIASES.get(s["type"], s["type"])
            raw.setdefault(opt_id, {}).setdefault(typ, []).append(s)

        usable = []
        for opt_id, by_type in raw.items():
            if required_here and not any(
                    s["crn"] in required_here for secs in by_type.values() for s in secs):
                continue  # this option doesn't contain the section the student locked in
            filtered = {}
            for typ, secs in by_type.items():
                pinned = [s for s in secs if s["crn"] in required_here]
                filtered[typ] = [s for s in (pinned or secs) if section_allowed(s, c)]
            if all(filtered.values()):  # every component still has at least one section
                usable.append((opt_id, filtered))
        options[code] = usable
    return options


class _Collector(cp_model.CpSolverSolutionCallback):
    """Called by the solver each time it finds a valid schedule."""

    def __init__(self, x, limit):
        super().__init__()
        self._x = x
        self._limit = limit
        self.solutions = []

    def on_solution_callback(self):
        if len(self.solutions) < self._limit:
            self.solutions.append([crn for crn, v in self._x.items() if self.boolean_value(v)])
        if len(self.solutions) >= self._limit:
            self.stop_search()


def _build_model(term, codes, c, link_by_class):
    """Build the CP-SAT model containing all the hard rules.

    Returns (model, x, sec, problem). If some course has no usable option at all,
    returns (None, None, None, "explanation") instead.
    """
    codes = list(dict.fromkeys(codes))  # drop duplicates, keep order
    for code in codes:
        if code not in term:
            raise ValueError(f"Unknown course: {code}")

    options = build_options(term, codes, c, link_by_class)
    for code, usable in options.items():
        if not usable:
            return None, None, None, f"No option for {code} fits your constraints."

    model = cp_model.CpModel()
    x = {}    # crn -> BoolVar ("this section is chosen")
    sec = {}  # crn -> section dict
    grp = {}  # crn -> (course, option id, type)

    for code, usable in options.items():
        picks = []  # one BoolVar per usable option of this course
        for opt_id, by_type in usable:
            chosen = model.new_bool_var(f"opt_{code}_{opt_id}")
            picks.append(chosen)
            for typ, secs in by_type.items():
                lits = []
                for s in secs:
                    crn = s["crn"]
                    if crn in x:
                        raise ValueError(f"CRN {crn} appears twice in the data")
                    x[crn] = model.new_bool_var(f"x_{crn}")
                    sec[crn] = {**s, "course": code}
                    grp[crn] = (code, opt_id, typ)
                    lits.append(x[crn])
                model.add(sum(lits) == chosen)  # one section of this type iff the option is picked
        model.add_exactly_one(picks)            # exactly one option per course

    # No two chosen sections may overlap.
    crns = list(x)
    for i in range(len(crns)):
        for j in range(i + 1, len(crns)):
            a, b = crns[i], crns[j]
            (ca, pa, ta), (cb, pb, tb) = grp[a], grp[b]
            if ca == cb and (pa != pb or ta == tb):
                continue  # same group, or two different options of one course
            if sections_conflict(sec[a], sec[b]):
                model.add_at_most_one([x[a], x[b]])
    return model, x, sec, None


def generate_schedules(term, codes, constraints=None, max_solutions=20, link_by_class=True):
    c = constraints or Constraints()
    model, x, sec, problem = _build_model(term, codes, c, link_by_class)
    if problem:
        return Result([], problem)

    solver = cp_model.CpSolver()
    solver.parameters.enumerate_all_solutions = True
    solver.parameters.num_workers = 1
    collector = _Collector(x, max_solutions)
    status = solver.solve(model, collector)
    if status == cp_model.MODEL_INVALID:
        raise RuntimeError("The solver rejected the model (this is a bug).")

    schedules = [[sec[crn] for crn in sol] for sol in collector.solutions]
    if not schedules:
        return Result([], "No conflict-free schedule exists for these courses and constraints.")
    hit_cap = len(schedules) >= max_solutions
    msg = f"Found {len(schedules)} schedule(s)"
    if hit_cap:
        msg += " (stopped at the limit; more may exist)"
    return Result(schedules, msg, hit_cap)