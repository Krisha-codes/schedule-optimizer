import os
import re
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from config import CAMPUS_CODE
from ranking import Preferences, rank_schedules
from solver import Constraints, load_term

DATA_DIR = Path(__file__).parent / "data"
TERM_FILE = re.compile(r"term_(\d{6})\.json")

def parse_origins(value):
    """'https://a.github.io, http://localhost:5173/' -> ['https://a.github.io', 'http://localhost:5173']"""
    origins = [o.strip().rstrip("/") for o in (value or "").split(",") if o.strip()]
    return origins or ["http://localhost:5173"]


app = FastAPI(title="Schedule Optimizer")
# Which websites may call this API from a browser. On the server, set ALLOWED_ORIGINS to your
# GitHub Pages address (for example https://your-name.github.io).
app.add_middleware(CORSMiddleware, allow_origins=parse_origins(os.environ.get("ALLOWED_ORIGINS")),
                   allow_methods=["*"], allow_headers=["*"])

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


@app.get("/health", include_in_schema=False)
def health():
    """Lets the hosting service check that the server is up (needs no data)."""
    return {"status": "ok"}

def term_name(code):
    """'202710' -> 'Fall 2026'. Purdue's year digits are the academic year's end year."""
    year, suffix = int(code[:4]), code[4:]
    season, calendar_year = {
        "10": ("Fall", year - 1),
        "13": ("Winter", year - 1),
        "20": ("Spring", year),
        "30": ("Summer", year),
    }.get(suffix, ("Term", year))
    return f"{season} {calendar_year}"


def available_terms():
    """Term codes that have a data file in data/, newest first."""
    codes = []
    for path in DATA_DIR.glob("term_*.json"):
        match = TERM_FILE.fullmatch(path.name)
        if match:
            codes.append(match.group(1))
    return sorted(codes, reverse=True)


def default_term(codes):
    """The newest Fall or Spring term (short winter/summer terms are rarely what people want)."""
    return next((c for c in codes if c[4:] in ("10", "20")), codes[0])


@lru_cache(maxsize=3)
def _load(path, modified_ns):
    return load_term(path)


def get_term_code(term: str | None = None):
    """The term code from ?term=..., or the default. 404 if we have no data for it."""
    codes = available_terms()
    if not codes:
        raise HTTPException(status_code=503,
                            detail="No course data yet. Run `python refresh_data.py` on the server.")
    code = term or default_term(codes)
    if code not in codes:
        raise HTTPException(status_code=404, detail=f"No data for term {code}.")
    return code


def get_term(code: str = Depends(get_term_code)):
    """The course data for the chosen term. Reloaded automatically when the file changes."""
    path = DATA_DIR / f"term_{code}.json"
    return _load(str(path), path.stat().st_mtime_ns)


class ConstraintsIn(BaseModel):
    earliest_start: int | None = None
    latest_end: int | None = None
    free_days: list[int] = []
    blocked: list[tuple[int, int, int]] = []   # (day, start, end), minutes after midnight
    avoid_crns: list[str] = []
    required_crns: list[str] = []


class PreferencesIn(BaseModel):
    preferred_start: int = 9 * 60
    preferred_end: int = 17 * 60
    preferred_instructors: list[str] = []
    avoided_instructors: list[str] = []
    w_early: int = 1
    w_late: int = 1
    w_days: int = 60
    w_spread: int = 1
    w_instructor: int = 100


class ScheduleRequest(BaseModel):
    courses: list[str] = Field(min_length=1, max_length=10)
    constraints: ConstraintsIn = Field(default_factory=ConstraintsIn)
    preferences: PreferencesIn = Field(default_factory=PreferencesIn)
    top_n: int = Field(5, ge=1, le=10)
    min_difference: int = Field(1, ge=1, le=10)


def _schedulable(course):
    """Hide arranged courses (research, individual study...): nothing to put on a calendar."""
    return any(s["type"] == "Distance Learning"
               or any(m["start"] is not None for m in s["meetings"])
               for s in course["sections"])


@app.get("/api/terms")
def list_terms():
    codes = available_terms()
    default = default_term(codes) if codes else None
    return [{"code": c, "name": term_name(c), "default": c == default} for c in codes]


@app.get("/api/term")
def term_info(code: str = Depends(get_term_code), term=Depends(get_term)):
    return {"term_code": code, "name": term_name(code),
            "campus": CAMPUS_CODE, "courses": len(term)}


def _compact(text):
    """'CS 18000' -> 'cs18000', so a search works with or without the space."""
    return "".join(text.lower().split())


@app.get("/api/courses")
def search_courses(q: str = "", limit: int = Query(20, ge=1, le=100), term=Depends(get_term)):
    q = q.strip().lower()
    q_compact = _compact(q)
    found = []
    for code, c in sorted(term.items()):
        matches = (q in code.lower() or q in (c["title"] or "").lower()
                   or (q_compact and q_compact in _compact(code)))
        if _schedulable(c) and matches:
            found.append({"code": code, "title": c["title"], "credits": c["credits"]})
            if len(found) >= limit:
                break
    return found


@app.post("/api/schedules")
def build_schedules(req: ScheduleRequest, term=Depends(get_term)):
    k = req.constraints
    constraints = Constraints(
        earliest_start=k.earliest_start, latest_end=k.latest_end,
        free_days=set(k.free_days), blocked=[tuple(b) for b in k.blocked],
        avoid_crns=set(k.avoid_crns), required_crns=set(k.required_crns))
    prefs = req.preferences.model_dump()
    prefs["preferred_instructors"] = set(prefs["preferred_instructors"])
    prefs["avoided_instructors"] = set(prefs["avoided_instructors"])
    try:
                result = rank_schedules(term, req.courses, constraints, Preferences(**prefs),
                                top_n=req.top_n, min_difference=req.min_difference,
                                time_limit=5.0)  # keep any one request short on a shared server
    except ValueError as e:                     # e.g. unknown course code
        raise HTTPException(status_code=422, detail=str(e))
    return {
        "message": result.message,
        "proven_optimal": result.proven_optimal,
        "schedules": [
            {"score": b, "sections": sorted(sch, key=lambda s: (s["course"], s["type"] or ""))}
            for sch, b in zip(result.schedules, result.breakdowns)
        ],
    }
