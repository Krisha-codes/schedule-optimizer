"""Show the newest terms on Purdue.io and whether each one has classes for your campus."""
from config import CAMPUS_CODE, TERM_CODE
from fetch_data import BASE, get_all

terms = get_all(f"{BASE}/Terms", {
    "$filter": "Code ne '999999'",   # 999999 is a placeholder ("The End of Time")
    "$orderby": "Code desc",
    "$top": "8",
})

print(f"Newest terms on Purdue.io (campus {CAMPUS_CODE}). config.py uses {TERM_CODE}.\n")
for t in terms:
    probe = get_all(f"{BASE}/Classes", {
        "$filter": f"Term/Code eq '{t['Code']}' and Campus/Code eq '{CAMPUS_CODE}'",
        "$top": "1",
    })
    status = "has classes" if probe else "no classes yet"
    mark = "   <- config.py" if t["Code"] == TERM_CODE else ""
    print(f"{t['Code']}  {t['Name']:<14} {status}{mark}")
