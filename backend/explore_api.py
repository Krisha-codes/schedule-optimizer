import json, requests
from config import TERM_CODE, CAMPUS_CODE

SUBJECT = "CS"
NUMBER = "18000"

BASE = "https://api.purdue.io/odata/Classes"
params = {
    "$filter": (f"Term/Code eq '{TERM_CODE}' and Campus/Code eq '{CAMPUS_CODE}'"
                f" and Course/Subject/Abbreviation eq '{SUBJECT}'"
                f" and Course/Number eq '{NUMBER}'"),
    "$expand": ("Course($expand=Subject),"
                "Sections($expand=Meetings($expand=Room($expand=Building),Instructors))"),
}
r = requests.get(BASE, params=params, timeout=60)
print("Status:", r.status_code)
data = r.json()
classes = data.get("value", [])
print("Classes returned:", len(classes))
for cl in classes:
    for s in cl.get("Sections", []):
        for m in s.get("Meetings", []):
            print(s["Crn"], s["Type"], m.get("DaysOfWeek"), m.get("StartTime"), m.get("Duration"))
print(json.dumps(data, indent=2)[:3000])