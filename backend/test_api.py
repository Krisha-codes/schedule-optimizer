from fastapi.testclient import TestClient

from api import app, get_term, term_name
from config import TERM_CODE
from test_solver import MWF, TERM, course, sec, t

app.dependency_overrides[get_term] = lambda: TERM   # use the tiny hand-made term
client = TestClient(app)


def test_course_search():
    r = client.get("/api/courses", params={"q": "a"})
    assert r.status_code == 200
    assert [c["code"] for c in r.json()] == ["A"]


def test_schedules_are_ranked_best_first():
    r = client.post("/api/schedules", json={"courses": ["A", "B"]})
    assert r.status_code == 200
    scores = [s["score"]["total"] for s in r.json()["schedules"]]
    assert len(scores) == 2 and scores == sorted(scores)


def test_unknown_course_gives_422_with_message():
    r = client.post("/api/schedules", json={"courses": ["ZZZ"]})
    assert r.status_code == 422 and "Unknown course" in str(r.json())


def test_bad_input_is_rejected():
    assert client.post("/api/schedules", json={"courses": []}).status_code == 422
    assert client.post("/api/schedules", json={"courses": ["A"], "top_n": 500}).status_code == 422


def test_course_search_ignores_spaces():
    big = {"CS 18000": course("CS 18000", sec("1", "Lecture", MWF, t(9), t(9, 50)))}
    app.dependency_overrides[get_term] = lambda: big
    try:
        found = client.get("/api/courses", params={"q": "cs180"}).json()
    finally:
        app.dependency_overrides[get_term] = lambda: TERM
    assert [c["code"] for c in found] == ["CS 18000"]


def test_locked_and_avoided_sections_reach_the_solver():
    r = client.post("/api/schedules",
                    json={"courses": ["A", "B"], "constraints": {"required_crns": ["A2"]}})
    assert r.status_code == 200 and r.json()["schedules"]
    for sched in r.json()["schedules"]:
        assert "A2" in [s["crn"] for s in sched["sections"]]

    r = client.post("/api/schedules",
                    json={"courses": ["A", "B"], "constraints": {"avoid_crns": ["A1"]}})
    assert r.status_code == 200 and r.json()["schedules"]
    for sched in r.json()["schedules"]:
        assert "A1" not in [s["crn"] for s in sched["sections"]]


def test_locking_a_crn_from_an_unselected_course_is_a_422():
    r = client.post("/api/schedules",
                    json={"courses": ["A"], "constraints": {"required_crns": ["B2"]}})
    assert r.status_code == 422 and "not found" in str(r.json())


def test_term_names():
    assert term_name("202710") == "Fall 2026"
    assert term_name("202720") == "Spring 2027"
    assert term_name("202630") == "Summer 2026"
    assert term_name("202713") == "Winter 2026"
    assert term_name("202699") == "Term 2026"


def test_term_info_includes_the_name():
    info = client.get("/api/term").json()
    assert info["term_code"] == TERM_CODE and info["name"] == term_name(TERM_CODE)