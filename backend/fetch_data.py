"""Download one term of Purdue.io data and save it as data/term_<code>.json.

Usage:
    python fetch_data.py                     # every subject; term and campus from config.py
    python fetch_data.py --term 202720       # a different term
    python fetch_data.py --subjects CS MA    # only refresh these subjects (keeps the others)
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

from config import CAMPUS_CODE, TERM_CODE

BASE = "https://api.purdue.io/odata"
DATA_DIR = Path(__file__).parent / "data"
DAY_MAP = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
           "Friday": 4, "Saturday": 5, "Sunday": 6}


def get_all(url, params=None, tries=3, max_pages=None):
    """Follow OData paging until every row is fetched (or max_pages pages, if given).

    A request that fails because of the network or a server error is retried a few
    times; a 4xx error (a mistake in our query) is raised straight away.
    """
    rows = []
    pages = 0
    while url:
        for attempt in range(1, tries + 1):
            try:
                r = requests.get(url, params=params, timeout=60)
                r.raise_for_status()
                break
            except requests.RequestException as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                client_error = status is not None and status < 500
                if client_error or attempt == tries:
                    raise
                time.sleep(2 * attempt)
        data = r.json()
        rows.extend(data["value"])
        pages += 1
        url = data.get("@odata.nextLink")
        params = None  # nextLink already contains the query
        if max_pages is not None and pages >= max_pages:
            break
        time.sleep(0.3)  # be polite to a community-run API
    return rows


def parse_time(s):
    """'10:30:00.0000000' -> 630 (minutes after midnight)"""
    if not s:
        return None
    h, m = s.split(":")[:2]
    return int(h) * 60 + int(m)


def parse_duration(s):
    """'PT50M' or 'PT1H50M' -> minutes"""
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?", s or "")
    if not m:
        return None
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


def parse_days(s):
    """'Monday, Wednesday, Friday' -> [0, 2, 4]"""
    return sorted(DAY_MAP[d] for d in DAY_MAP if d in (s or ""))


def normalize_meeting(m):
    start = parse_time(m.get("StartTime"))
    dur = parse_duration(m.get("Duration"))
    room = m.get("Room") or {}
    bldg = room.get("Building") or {}
    return {
        "days": parse_days(m.get("DaysOfWeek")),
        "start": start,
        "end": start + dur if start is not None and dur is not None else None,
        "start_date": m.get("StartDate"),
        "end_date": m.get("EndDate"),
        "building": bldg.get("ShortCode"),
        "room": room.get("Number"),
        "instructors": [i["Name"] for i in m.get("Instructors", []) if i.get("Name")],
    }


def normalize(classes):
    courses = {}
    for cl in classes:
        c = cl["Course"]
        code = f"{c['Subject']['Abbreviation']} {c['Number']}"
        course = courses.setdefault(code, {
            "code": code, "title": c.get("Title"),
            "credits": c.get("CreditHours"), "sections": []})
        for s in cl.get("Sections", []):
            course["sections"].append({
                "crn": s.get("Crn"),
                "class_id": cl["Id"],
                "type": s.get("Type"),
                "meetings": [normalize_meeting(m) for m in s.get("Meetings", [])],
            })
    return courses


def fetch_subjects():
    """Every subject abbreviation Purdue.io knows about (CS, MA, ENGL, ...)."""
    rows = get_all(f"{BASE}/Subjects", {"$orderby": "Abbreviation"})
    return [r["Abbreviation"] for r in rows if r.get("Abbreviation")]

def term_has_classes(term_code):
    """Cheap check: does Purdue.io list any classes for this term on our campus? (first page only)"""
    rows = get_all(f"{BASE}/Classes",
                   {"$filter": f"Term/Code eq '{term_code}' and Campus/Code eq '{CAMPUS_CODE}'"},
                   max_pages=1)
    return len(rows) > 0

def fetch_subject(subject, term_code):
    params = {
        "$filter": (f"Term/Code eq '{term_code}' and Campus/Code eq '{CAMPUS_CODE}'"
                    f" and Course/Subject/Abbreviation eq '{subject}'"),
        "$expand": ("Course($expand=Subject),"
                    "Sections($expand=Meetings($expand=Room($expand=Building),Instructors))"),
    }
    return get_all(f"{BASE}/Classes", params)


def main(argv=None, data_dir=DATA_DIR):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--term", default=TERM_CODE)
    parser.add_argument("--subjects", nargs="+", help="only refresh these subjects")
    args = parser.parse_args(argv)

    subjects = args.subjects or fetch_subjects()
    print(f"Term {args.term}, campus {CAMPUS_CODE}: {len(subjects)} subject(s) to fetch")

    courses, failed = {}, []
    for i, subject in enumerate(subjects, 1):
        try:
            classes = fetch_subject(subject, args.term)
        except requests.RequestException as e:
            print(f"[{i}/{len(subjects)}] {subject}: FAILED ({e})")
            failed.append(subject)
            continue
        found = normalize(classes)
        courses.update(found)
        if found:
            print(f"[{i}/{len(subjects)}] {subject}: {len(classes)} classes -> {len(found)} courses")

    if not courses:
        print("Nothing found. The term may not be published yet; "
              "run `python check_term.py` to see which terms have data.")
        return 1

    data_dir.mkdir(exist_ok=True)
    path = data_dir / f"term_{args.term}.json"
    if args.subjects and path.exists():
        # a partial refresh: keep the other subjects, replace only the ones we just fetched
        refreshed = set(args.subjects)
        kept = {code: c for code, c in json.loads(path.read_text()).items()
                if code.split()[0] not in refreshed}
        kept.update(courses)
        courses = kept

    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(courses, indent=1))
    tmp.replace(path)  # only replace the old file once the new one is fully written
    n_sections = sum(len(c["sections"]) for c in courses.values())
    print(f"Saved {len(courses)} courses, {n_sections} sections -> {path}")

    if failed:
        print(f"WARNING: {len(failed)} subject(s) failed: {' '.join(failed)}")
        print(f"Retry just those with: python fetch_data.py --subjects {' '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())