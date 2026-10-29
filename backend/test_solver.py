import pytest
from solver import Constraints, generate_schedules, meetings_overlap

SD, ED = "2026-08-24", "2026-12-12"
MWF, TR = [0, 2, 4], [1, 3]


def t(h, m=0):
    return h * 60 + m


def sec(crn, typ, days, start, end, sd=SD, ed=ED, class_id="x"):
    return {"crn": crn, "class_id": class_id, "type": typ,
            "meetings": [{"days": days, "start": start, "end": end,
                          "start_date": sd, "end_date": ed,
                          "building": "T", "room": "1", "instructors": []}]}


def course(code, *sections):
    return {"code": code, "title": code, "credits": 3, "sections": list(sections)}


def crns(result):
    return sorted(sorted(s["crn"] for s in sched) for sched in result.schedules)


TERM = {
    "A": course("A", sec("A1", "Lecture", MWF, t(9), t(9, 50)),
                     sec("A2", "Lecture", MWF, t(10), t(10, 50))),
    "B": course("B", sec("B1", "Lecture", MWF, t(9, 30), t(10, 20)),
                     sec("B2", "Lecture", TR, t(9), t(10, 15))),
}


def test_overlap_basics():
    a = sec("a", "Lecture", MWF, t(9), t(9, 50))["meetings"][0]
    back_to_back = sec("b", "Lecture", MWF, t(9, 50), t(10, 40))["meetings"][0]
    overlapping = sec("c", "Lecture", MWF, t(9, 30), t(10, 20))["meetings"][0]
    other_days = sec("d", "Lecture", TR, t(9), t(9, 50))["meetings"][0]
    assert not meetings_overlap(a, back_to_back)
    assert meetings_overlap(a, overlapping)
    assert not meetings_overlap(a, other_days)


def test_half_semester_sections_do_not_conflict():
    first = sec("a", "Lecture", MWF, t(9), t(9, 50), "2026-08-24", "2026-10-16")["meetings"][0]
    second = sec("b", "Lecture", MWF, t(9), t(9, 50), "2026-10-19", "2026-12-12")["meetings"][0]
    assert not meetings_overlap(first, second)


def test_conflicting_section_is_never_chosen():
    assert crns(generate_schedules(TERM, ["A", "B"])) == [["A1", "B2"], ["A2", "B2"]]


def test_one_section_per_component():
    term = {"L": course("L",
                        sec("X", "Lecture", MWF, t(9), t(9, 50)),
                        sec("Y1", "Laboratory", MWF, t(9, 30), t(10, 20)),
                        sec("Y2", "Laboratory", TR, t(9), t(10, 15)))}
    assert crns(generate_schedules(term, ["L"])) == [["X", "Y2"]]


def test_earliest_start():
    assert crns(generate_schedules(TERM, ["A"], Constraints(earliest_start=t(10)))) == [["A2"]]


def test_free_day_with_no_options_explains_why():
    r = generate_schedules(TERM, ["A"], Constraints(free_days={4}))
    assert r.schedules == []
    assert r.message.startswith("No option for A")


def test_blocked_time():
    r = generate_schedules(TERM, ["A"], Constraints(blocked=[(0, t(10), t(11))]))
    assert crns(r) == [["A1"]]


def test_required_section_is_locked_in():
    r = generate_schedules(TERM, ["A", "B"], Constraints(required_crns={"A2"}))
    assert crns(r) == [["A2", "B2"]]


def test_no_possible_schedule():
    term = {"P": course("P", sec("P1", "Lecture", MWF, t(9), t(9, 50))),
            "Q": course("Q", sec("Q1", "Lecture", MWF, t(9), t(9, 50)))}
    assert generate_schedules(term, ["P", "Q"]).schedules == []


def test_solution_cap():
    term = {"M": course("M", *[sec(f"M{d}", "Lecture", [d], t(9), t(9, 50)) for d in range(5)])}
    assert len(generate_schedules(term, ["M"], max_solutions=3).schedules) == 3
    assert len(generate_schedules(term, ["M"], max_solutions=50).schedules) == 5


def test_labs_pair_only_with_their_own_lecture_when_linked():
    term = {"L": course("L",
                        sec("LEC1", "Lecture", MWF, t(9), t(9, 50), class_id="c1"),
                        sec("LAB1", "Laboratory", TR, t(9), t(10, 50), class_id="c1"),
                        sec("LEC2", "Lecture", MWF, t(13), t(13, 50), class_id="c2"),
                        sec("LAB2", "Laboratory", TR, t(13), t(14, 50), class_id="c2"))}
    assert crns(generate_schedules(term, ["L"])) == [["LAB1", "LEC1"], ["LAB2", "LEC2"]]
    assert len(generate_schedules(term, ["L"], link_by_class=False).schedules) == 4


def test_unknown_course():
    with pytest.raises(ValueError):
        generate_schedules(TERM, ["ZZZ"])