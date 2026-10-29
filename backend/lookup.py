import json, sys
from pathlib import Path
from config import TERM_CODE

DAYS = "MTWRFSU"  # R = Thursday, the usual Purdue shorthand


def hhmm(mins):
    return "TBA" if mins is None else f"{mins // 60:02d}:{mins % 60:02d}"


path = Path(__file__).parent / "data" / f"term_{TERM_CODE}.json"
data = json.loads(path.read_text())
code = sys.argv[1]
if code not in data:
    print(f"{code} not found. Try one of: {list(data)[:10]}")
    sys.exit(1)

course = data[code]
print(f"{course['code']} - {course['title']} ({course['credits']} cr)")
for s in course["sections"]:
    print(f"CRN {s['crn']} | {s['type']}")
    for m in s["meetings"]:
        days = "".join(DAYS[d] for d in m["days"]) or "-"
        who = ", ".join(m["instructors"])
        print(f"   {days} {hhmm(m['start'])}-{hhmm(m['end'])} "
              f"{m['building']} {m['room']} {who}")