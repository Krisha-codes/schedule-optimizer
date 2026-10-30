from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import CAMPUS_CODE, TERM_CODE
from ranking import Preferences, rank_schedules
from solver import Constraints, load_term
from fastapi.responses import RedirectResponse

DATA_PATH = Path(__file__).parent / "data" / f"term_{TERM_CODE}.json"

app = FastAPI(title="Schedule Optimizer")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                   allow_methods=["*"], allow_headers=["*"])  # lets the React dev server call us
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


@lru_cache
def get_term():
    """Load the course data once, then reuse it."""
    return load_term(DATA_PATH)


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
    top_n: int = Field(5, ge=1, le=20)
    min_difference: int = Field(1, ge=1, le=10)


def _schedulable(course):
    """Hide arranged courses (research, individual study...): nothing to put on a calendar."""
    return any(s["type"] == "Distance Learning"
               or any(m["start"] is not None for m in s["meetings"])
               for s in course["sections"])


@app.get("/api/term")
def term_info(term=Depends(get_term)):
    return {"term_code": TERM_CODE, "campus": CAMPUS_CODE, "courses": len(term)}


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
                                top_n=req.top_n, min_difference=req.min_difference)
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
