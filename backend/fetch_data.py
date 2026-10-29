import json, re, time
from pathlib import Path
import requests
from config import TERM_CODE, CAMPUS_CODE, SUBJECTS

BASE = "https://api.purdue.io/odata"
DATA_DIR = Path(__file__).parent / "data"
DAY_MAP = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
           "Friday": 4, "Saturday": 5, "Sunday": 6}


def get_all(url, params=None):
    """Follow OData paging until every row is fetched."""
    rows = []
    while url:
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        rows.extend(data["value"])
        url = data.get("@odata.nextLink")
        params = None  # nextLink already contains the query
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


def fetch_subject(subject):
    params = {
        "$filter": (f"Term/Code eq '{TERM_CODE}' and Campus/Code eq '{CAMPUS_CODE}'"
                    f" and Course/Subject/Abbreviation eq '{subject}'"),
        "$expand": ("Course($expand=Subject),"
                    "Sections($expand=Meetings($expand=Room($expand=Building),Instructors))"),
    }
    return get_all(f"{BASE}/Classes", params)


if __name__ == "__main__":
    DATA_DIR.mkdir(exist_ok=True)
    all_courses = {}
    for subj in SUBJECTS:
        classes = fetch_subject(subj)
        found = normalize(classes)
        print(f"{subj}: {len(classes)} classes -> {len(found)} courses")
        if not found:
            print(f"  WARNING: nothing found for {subj}. Check the abbreviation.")
        all_courses.update(found)
    path = DATA_DIR / f"term_{TERM_CODE}.json"
    path.write_text(json.dumps(all_courses, indent=1))
    n = sum(len(c["sections"]) for c in all_courses.values())
    print(f"Saved {len(all_courses)} courses, {n} sections -> {path}")