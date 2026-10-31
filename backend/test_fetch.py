import json
import re

import pytest
import requests

import fetch_data


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"HTTP {self.status_code}")
            err.response = self
            raise err


def raw_class(subject, number, crn, days="Monday, Wednesday, Friday",
              start="10:30:00.0000000", duration="PT50M", title="A course"):
    """A Class shaped like the real Purdue.io response."""
    return {
        "Id": f"class-{subject}-{number}",
        "Course": {"Number": number, "Title": title, "CreditHours": 3.0,
                   "Subject": {"Abbreviation": subject}},
        "Sections": [{"Crn": crn, "Type": "Lecture", "Meetings": [{
            "DaysOfWeek": days, "StartTime": start, "Duration": duration,
            "StartDate": "2026-08-24", "EndDate": "2026-12-12",
            "Room": {"Number": "105", "Building": {"ShortCode": "IO"}},
            "Instructors": [{"Name": "Ada Lovelace"}]}]}],
    }


@pytest.fixture(autouse=True)
def no_sleeping(monkeypatch):
    monkeypatch.setattr(fetch_data.time, "sleep", lambda seconds: None)


def test_normalize_parses_days_times_and_rooms():
    courses = fetch_data.normalize([raw_class("CS", "18000", "111")])
    meeting = courses["CS 18000"]["sections"][0]["meetings"][0]
    assert meeting["days"] == [0, 2, 4]
    assert (meeting["start"], meeting["end"]) == (630, 680)
    assert meeting["building"] == "IO" and meeting["room"] == "105"
    assert meeting["instructors"] == ["Ada Lovelace"]


def test_normalize_keeps_online_sections_without_times():
    online = raw_class("MA", "26100", "222", days=None, start=None, duration=None)
    meeting = fetch_data.normalize([online])["MA 26100"]["sections"][0]["meetings"][0]
    assert meeting["days"] == [] and meeting["start"] is None and meeting["end"] is None


def test_get_all_follows_next_link_and_retries_after_a_network_error(monkeypatch):
    replies = iter([
        requests.ConnectionError("network blip"),
        FakeResponse({"value": [1, 2], "@odata.nextLink": "https://next-page"}),
        FakeResponse({"value": [3]}),
    ])
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        reply = next(replies)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(fetch_data.requests, "get", fake_get)
    assert fetch_data.get_all("https://first-page") == [1, 2, 3]
    assert calls == ["https://first-page", "https://first-page", "https://next-page"]


def test_get_all_does_not_retry_a_client_error(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        return FakeResponse({}, status=400)

    monkeypatch.setattr(fetch_data.requests, "get", fake_get)
    with pytest.raises(requests.HTTPError):
        fetch_data.get_all("https://bad-query")
    assert len(calls) == 1


def fake_api(monkeypatch, classes_by_subject, failing=()):
    """Pretend to be Purdue.io: a Subjects endpoint and a Classes endpoint."""
    def fake_get(url, params=None, timeout=None):
        if url.endswith("/Subjects"):
            return FakeResponse({"value": [{"Abbreviation": s} for s in classes_by_subject]})
        subject = re.search(r"Abbreviation eq '(\w+)'", params["$filter"]).group(1)
        if subject in failing:
            raise requests.ConnectionError("down")
        return FakeResponse({"value": classes_by_subject[subject]})

    monkeypatch.setattr(fetch_data.requests, "get", fake_get)


def test_main_fetches_every_subject_and_skips_empty_ones(monkeypatch, tmp_path):
    fake_api(monkeypatch, {"CS": [raw_class("CS", "18000", "1")],
                           "MA": [raw_class("MA", "16100", "2")],
                           "EMPTY": []})
    assert fetch_data.main(["--term", "202710"], data_dir=tmp_path) == 0
    saved = json.loads((tmp_path / "term_202710.json").read_text())
    assert sorted(saved) == ["CS 18000", "MA 16100"]


def test_partial_refresh_replaces_only_the_named_subjects(monkeypatch, tmp_path):
    fake_api(monkeypatch, {"CS": [raw_class("CS", "18000", "1")],
                           "MA": [raw_class("MA", "16100", "2")]})
    fetch_data.main(["--term", "202710"], data_dir=tmp_path)

    fake_api(monkeypatch, {"CS": [raw_class("CS", "24000", "3")]})
    assert fetch_data.main(["--term", "202710", "--subjects", "CS"], data_dir=tmp_path) == 0
    saved = json.loads((tmp_path / "term_202710.json").read_text())
    assert sorted(saved) == ["CS 24000", "MA 16100"]   # CS replaced, MA untouched


def test_a_failing_subject_is_reported_but_the_rest_is_saved(monkeypatch, tmp_path, capsys):
    fake_api(monkeypatch, {"CS": [raw_class("CS", "18000", "1")],
                           "MA": [raw_class("MA", "16100", "2")]}, failing={"MA"})
    assert fetch_data.main(["--term", "202710"], data_dir=tmp_path) == 1
    out = capsys.readouterr().out
    assert "FAILED" in out and "--subjects MA" in out
    assert sorted(json.loads((tmp_path / "term_202710.json").read_text())) == ["CS 18000"]


def test_nothing_found_saves_no_file(monkeypatch, tmp_path, capsys):
    fake_api(monkeypatch, {"CS": []})
    assert fetch_data.main(["--term", "209999"], data_dir=tmp_path) == 1
    assert not (tmp_path / "term_209999.json").exists()
    assert "check_term.py" in capsys.readouterr().out
