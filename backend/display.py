DAYS = "MTWRFSU"


def hhmm(mins):
    return "TBA" if mins is None else f"{mins // 60:02d}:{mins % 60:02d}"


def show(schedule):
    for s in sorted(schedule, key=lambda s: (s["course"], s["type"] or "")):
        label = f"   {s['course']:<11}{(s['type'] or ''):<12}CRN {s['crn']}"
        if not s["meetings"]:
            print(label, " (no meeting time)")
        for m in s["meetings"]:
            days = "".join(DAYS[d] for d in m["days"]) or "-"
            print(label, f" {days:<5}{hhmm(m['start'])}-{hhmm(m['end'])}")