import os
import time
from datetime import date

import fetch_data
import refresh_data
from test_fetch import FakeResponse, raw_class, no_sleeping  # noqa: F401  (fixture reused)

TERMS = [
    {"Code": "202713", "Name": "Winter 2026", "EndDate": "2027-01-08"},
    {"Code": "202710", "Name": "Fall 2026", "EndDate": "2026-12-20"},
    {"Code": "202630", "Name": "Summer 2026", "EndDate": "2026-08-22"},
    {"Code": "999999", "Name": "The End of Time", "EndDate": None},
    {"Code": "202720", "Name": "Spring 2027", "EndDate": "2027-05-14"},
]


def test_candidate_terms_keeps_current_and_upcoming_newest_first():
    codes = [t["Code"] for t in refresh_data.candidate_terms(TERMS, date(2026, 10, 31))]
    assert codes == ["202720", "202713", "202710"]   # no placeholder, no ended summer term


def test_candidate_terms_only_looks_at_the_newest_few():
    many = [{"Code": f"2025{n:02d}", "Name": "x", "EndDate": None} for n in range(10, 30)]
    assert len(refresh_data.candidate_terms(many, date(2026, 1, 1), limit=3)) == 3


def test_needs_download(tmp_path):
    path = tmp_path / "term_1.json"
    assert refresh_data.needs_download(path, 7)               # missing
    path.write_text("{}")
    assert not refresh_data.needs_download(path, 7)           # just written
    old = time.time() - 8 * 86400
    os.utime(path, (old, old))
    assert refresh_data.needs_download(path, 7)               # 8 days old


def fake_purdue(monkeypatch, published):
    """Purdue.io with a Terms list; only the terms in `published` have classes."""
    def fake_get(url, params=None, timeout=None):
        if url.endswith("/Terms"):
            return FakeResponse({"value": TERMS})
        if url.endswith("/Subjects"):
            return FakeResponse({"value": [{"Abbreviation": "CS"}]})
        code = params["$filter"].split("'")[1]            # Term/Code eq '<code>' ...
        if code not in published:
            return FakeResponse({"value": []})
        return FakeResponse({"value": [raw_class("CS", "18000", f"crn{code}")]})

    monkeypatch.setattr(fetch_data.requests, "get", fake_get)


def test_downloads_only_published_terms_then_skips_fresh_files(monkeypatch, tmp_path, capsys):
    fake_purdue(monkeypatch, published={"202710", "202713"})
    today = date(2026, 10, 31)
    assert refresh_data.main([], data_dir=tmp_path, today=today) == 0
    assert sorted(p.name for p in tmp_path.glob("term_*.json")) == [
        "term_202710.json", "term_202713.json"]
    out = capsys.readouterr().out
    assert "202720" in out and "no classes published yet" in out

    # second run: files are fresh, nothing downloaded again
    refresh_data.main([], data_dir=tmp_path, today=today)
    assert out.count("downloading") == 2
    assert capsys.readouterr().out.count("up to date") == 2


def test_a_newly_published_term_is_picked_up_automatically(monkeypatch, tmp_path):
    today = date(2026, 10, 31)
    fake_purdue(monkeypatch, published={"202710"})
    refresh_data.main([], data_dir=tmp_path, today=today)
    assert not (tmp_path / "term_202720.json").exists()

    fake_purdue(monkeypatch, published={"202710", "202720"})   # Purdue publishes Spring 2027
    refresh_data.main([], data_dir=tmp_path, today=today)
    assert (tmp_path / "term_202720.json").exists()


def test_dry_run_downloads_nothing(monkeypatch, tmp_path, capsys):
    fake_purdue(monkeypatch, published={"202710"})
    refresh_data.main(["--dry-run"], data_dir=tmp_path, today=date(2026, 10, 31))
    assert list(tmp_path.glob("term_*.json")) == []
    assert "dry run" in capsys.readouterr().out


def test_force_downloads_again(monkeypatch, tmp_path, capsys):
    fake_purdue(monkeypatch, published={"202710"})
    today = date(2026, 10, 31)
    refresh_data.main([], data_dir=tmp_path, today=today)
    capsys.readouterr()
    refresh_data.main(["--force"], data_dir=tmp_path, today=today)
    assert "downloading" in capsys.readouterr().out


def test_get_all_can_stop_after_the_first_page(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        return FakeResponse({"value": [1], "@odata.nextLink": "https://next"})

    monkeypatch.setattr(fetch_data.requests, "get", fake_get)
    assert fetch_data.get_all("https://first", max_pages=1) == [1]
    assert calls == ["https://first"]