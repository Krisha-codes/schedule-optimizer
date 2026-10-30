from ranking import Preferences, evaluate, rank_schedules
from solver import Constraints
from test_solver import MWF, TERM, TR, course, sec, t


def only(**weights):
    """Preferences with every weight zero except the ones given."""
    base = dict(w_early=0, w_late=0, w_days=0, w_spread=0, w_instructor=0)
    base.update(weights)
    return Preferences(**base)


def crn_lists(result):
    return [sorted(s["crn"] for s in sched) for sched in result.schedules]


def totals(result):
    return [b["total"] for b in result.breakdowns]


def test_fewer_days_on_campus_wins():
    term = {"A": course("A", sec("A1", "Lecture", MWF, t(9), t(9, 50)),
                             sec("A2", "Lecture", TR, t(9), t(10, 15))),
            "B": course("B", sec("B1", "Lecture", MWF, t(13), t(13, 50)))}
    r = rank_schedules(term, ["A", "B"], prefs=only(w_days=10))
    assert crn_lists(r) == [["A1", "B1"], ["A2", "B1"]]
    assert totals(r) == [30, 50]          # 3 days vs 5 days, 10 points each


def test_smaller_time_on_campus_wins():
    term = {"A": course("A", sec("A1", "Lecture", MWF, t(9), t(9, 50)),
                             sec("A2", "Lecture", MWF, t(15), t(15, 50))),
            "B": course("B", sec("B1", "Lecture", MWF, t(10), t(10, 50)))}
    r = rank_schedules(term, ["A", "B"], prefs=only(w_spread=1))
    assert crn_lists(r) == [["A1", "B1"], ["A2", "B1"]]
    assert totals(r) == [330, 1050]       # 110 min x 3 days vs 350 min x 3 days


def test_early_classes_are_penalised():
    term = {"A": course("A", sec("A1", "Lecture", MWF, t(8), t(8, 50)),
                             sec("A2", "Lecture", MWF, t(11), t(11, 50)))}
    r = rank_schedules(term, ["A"], prefs=only(w_early=1))   # preferred start 9:00
    assert crn_lists(r) == [["A2"], ["A1"]]
    assert totals(r) == [0, 180]          # 60 min early x 3 days


def test_preferred_instructor_wins():
    s1 = sec("A1", "Lecture", MWF, t(9), t(9, 50))
    s1["meetings"][0]["instructors"] = ["Smith"]
    s2 = sec("A2", "Lecture", MWF, t(9), t(9, 50))
    s2["meetings"][0]["instructors"] = ["Jones"]
    p = only(w_instructor=5)
    p.preferred_instructors = {"Jones"}
    r = rank_schedules({"A": course("A", s1, s2)}, ["A"], prefs=p)
    assert crn_lists(r) == [["A2"], ["A1"]]
    assert totals(r) == [-5, 0]


def test_scores_are_sorted_and_match_evaluate():
    p = Preferences()                     # all default weights switched on
    r = rank_schedules(TERM, ["A", "B"], prefs=p)
    assert totals(r) == sorted(totals(r))
    for sched, b in zip(r.schedules, r.breakdowns):
        assert evaluate(sched, p)["total"] == b["total"]


def test_hard_constraints_still_apply():
    r = rank_schedules(TERM, ["A"], Constraints(earliest_start=t(10)), only(w_days=1))
    assert crn_lists(r) == [["A2"]]
    r2 = rank_schedules(TERM, ["A"], Constraints(free_days={4}))
    assert r2.schedules == [] and r2.message.startswith("No option for A")


def test_top_n_returns_distinct_schedules():
    term = {"M": course("M", *[sec(f"M{d}", "Lecture", [d], t(9), t(9, 50)) for d in range(5)])}
    r = rank_schedules(term, ["M"], top_n=3)
    got = [s[0]["crn"] for s in r.schedules]
    assert len(got) == 3 and len(set(got)) == 3
