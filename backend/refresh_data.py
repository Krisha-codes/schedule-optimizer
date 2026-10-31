"""Find the terms Purdue.io has classes for and download the ones we don't have yet.

Usage:
    python refresh_data.py              # download new terms, and terms whose file is over 7 days old
    python refresh_data.py --dry-run    # only show what exists and what would be downloaded
    python refresh_data.py --force      # download every current/upcoming term again now
"""
import argparse
import sys
import time
from datetime import date, timedelta

import fetch_data
from fetch_data import BASE, DATA_DIR, get_all


def candidate_terms(terms, today, limit=6, recent_days=45):
    """The newest few terms that are current, upcoming, or ended only recently.

    Skips Purdue.io's 999999 placeholder ("The End of Time"). Newest first.
    """
    newest = sorted((t for t in terms if t["Code"] != "999999"),
                    key=lambda t: t["Code"], reverse=True)[:limit]
    cutoff = (today - timedelta(days=recent_days)).isoformat()
    return [t for t in newest if not t.get("EndDate") or t["EndDate"] >= cutoff]


def needs_download(path, max_age_days, now=None):
    """True if the file is missing, or at least max_age_days old."""
    if not path.exists():
        return True
    age_days = ((now or time.time()) - path.stat().st_mtime) / 86400
    return age_days >= max_age_days


def main(argv=None, data_dir=DATA_DIR, today=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="show the plan, download nothing")
    parser.add_argument("--force", action="store_true", help="re-download even if the file is fresh")
    parser.add_argument("--max-age-days", type=float, default=7)
    args = parser.parse_args(argv)

    terms = candidate_terms(get_all(f"{BASE}/Terms"), today or date.today())
    if not terms:
        print("Purdue.io lists no current or upcoming terms.")
        return 1

    exit_code = 0
    for t in terms:
        code, name = t["Code"], t["Name"]
        path = data_dir / f"term_{code}.json"
        if not fetch_data.term_has_classes(code):
            print(f"{code}  {name:<12} no classes published yet")
            continue
        if args.force or needs_download(path, args.max_age_days):
            action = "needs download" if not path.exists() else "out of date"
            if args.dry_run:
                print(f"{code}  {name:<12} has classes; {action} (dry run, skipping)")
                continue
            print(f"{code}  {name:<12} has classes; downloading...")
            if fetch_data.main(["--term", code], data_dir=data_dir) != 0:
                exit_code = 1
        else:
            print(f"{code}  {name:<12} has classes; file is up to date")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())