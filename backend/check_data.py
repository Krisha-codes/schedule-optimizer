import json
from collections import Counter
from pathlib import Path
from config import TERM_CODE

term = json.loads((Path(__file__).parent / "data" / f"term_{TERM_CODE}.json").read_text())

types = Counter(s["type"] for c in term.values() for s in c["sections"])
print("Section types:", dict(types))

total = sum(len(c["sections"]) for c in term.values())
no_time = sum(1 for c in term.values() for s in c["sections"]
              if not any(m["start"] is not None for m in s["meetings"]))
print("Sections with no meeting time:", no_time, "of", total)

for code in ["CS 18000", "MA 16100", "ENGL 10600", "CS 24000"]:
    if code not in term:
        print(code, "-> not in data")
        continue
    by_class = {}
    for s in term[code]["sections"]:
        by_class.setdefault(s["class_id"], Counter())[s["type"]] += 1
    print(code, "->", len(by_class), "class(es)")
    for cid, counts in by_class.items():
        print("   ", cid[:8], dict(counts))
