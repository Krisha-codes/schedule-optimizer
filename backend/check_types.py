import json
from collections import Counter
from pathlib import Path
from config import TERM_CODE

term = json.loads((Path(__file__).parent / "data" / f"term_{TERM_CODE}.json").read_text())

combos = Counter()
examples = {}
for code, c in term.items():
    by_class = {}
    for s in c["sections"]:
        by_class.setdefault(s["class_id"], set()).add(s["type"])
    for types in by_class.values():
        key = tuple(sorted(t or "?" for t in types))
        combos[key] += 1
        examples.setdefault(key, code)

for key, n in combos.most_common():
    print(f"{n:>4} classes  {' + '.join(key):<60} e.g. {examples[key]}")
    