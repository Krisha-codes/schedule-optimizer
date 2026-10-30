from fastapi.testclient import TestClient

from api import app, get_term
from test_solver import TERM

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