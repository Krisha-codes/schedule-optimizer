import json
import os

import pytest
from fastapi.testclient import TestClient

import api
from api import app, default_term, get_term, term_name
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


@pytest.fixture
def data_folder(tmp_path, monkeypatch):
    """Use the real term-loading code against a temporary data folder."""
    monkeypatch.setattr(api, "DATA_DIR", tmp_path)
    api._load.cache_clear()
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()           # stop using the hand-made TERM
    yield tmp_path
    app.dependency_overrides.update(saved)


def write_term(folder, code, courses):
    (folder / f"term_{code}.json").write_text(json.dumps(courses))


def test_default_term_prefers_fall_or_spring():
    assert default_term(["202720", "202713", "202710"]) == "202720"
    assert default_term(["202713", "202710"]) == "202710"
    assert default_term(["202730", "202713"]) == "202730"   # nothing better: take the newest


def test_terms_are_listed_newest_first(data_folder):
    write_term(data_folder, "202710", {"A": TERM["A"]})
    write_term(data_folder, "202720", {"B": TERM["B"]})
    (data_folder / "notes.txt").write_text("not a term file")
    assert client.get("/api/terms").json() == [
        {"code": "202720", "name": "Spring 2027", "default": True},
        {"code": "202710", "name": "Fall 2026", "default": False},
    ]


def test_a_short_winter_term_is_listed_but_is_not_the_default(data_folder):
    write_term(data_folder, "202710", {"A": TERM["A"]})
    write_term(data_folder, "202713", {"B": TERM["B"]})
    terms = client.get("/api/terms").json()
    assert [t["code"] for t in terms] == ["202713", "202710"]       # newest first
    assert [t["code"] for t in terms if t["default"]] == ["202710"]  # but Fall is suggested


def test_term_query_picks_the_data_and_the_default_is_newest(data_folder):
    write_term(data_folder, "202710", {"A": TERM["A"]})
    write_term(data_folder, "202720", {"B": TERM["B"]})
    codes = lambda **params: [c["code"] for c in client.get("/api/courses", params=params).json()]
    assert codes() == ["B"]                      # no ?term=  ->  newest (Spring 2027)
    assert codes(term="202710") == ["A"]
    r = client.post("/api/schedules?term=202710", json={"courses": ["A"]})
    assert r.status_code == 200 and r.json()["schedules"]
    r = client.post("/api/schedules?term=202710", json={"courses": ["B"]})
    assert r.status_code == 422                  # B only exists in the other term


def test_term_info_for_the_chosen_term(data_folder):
    write_term(data_folder, "202710", {"A": TERM["A"], "B": TERM["B"]})
    assert client.get("/api/term").json() == {
        "term_code": "202710", "name": "Fall 2026", "campus": "PWL", "courses": 2}


def test_unknown_term_is_a_404_and_no_data_is_a_503(data_folder):
    assert client.get("/api/courses").status_code == 503
    write_term(data_folder, "202710", {"A": TERM["A"]})
    r = client.get("/api/courses", params={"term": "209999"})
    assert r.status_code == 404 and "209999" in r.json()["detail"]


def test_a_refreshed_data_file_is_picked_up_without_restarting(data_folder):
    path = data_folder / "term_202710.json"
    write_term(data_folder, "202710", {"A": TERM["A"]})
    assert [c["code"] for c in client.get("/api/courses").json()] == ["A"]

    write_term(data_folder, "202710", {"B": TERM["B"]})   # refresh_data.py rewrites the file
    later = path.stat().st_mtime + 5
    os.utime(path, (later, later))
    assert [c["code"] for c in client.get("/api/courses").json()] == ["B"]