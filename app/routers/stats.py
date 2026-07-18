from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.database import get_connection
from app.schemas import StatsDashboard

router = APIRouter()

PERIODS = {7, 30, 90, 365}


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _session_values(row) -> tuple[int, int, float | None]:
    words = max(0, int(row["words_advanced"] or 0))
    started = _parse_utc(row["started_at"])
    finished = _parse_utc(row["ended_at"] or row["updated_at"])
    seconds = max(0, int((finished - started).total_seconds())) if started and finished else 0
    raw_wpm = row["avg_wpm"]
    wpm = float(raw_wpm) if raw_wpm is not None and float(raw_wpm) > 0 else None
    return words, seconds, wpm


def _weighted_wpm(samples: list[tuple[float, int]]) -> float | None:
    weight = sum(words for _, words in samples if words > 0)
    if weight <= 0:
        return None
    return round(sum(wpm * words for wpm, words in samples if words > 0) / weight, 1)


def _current_streak(active_dates: set[date], today: date) -> int:
    if not active_dates:
        return 0
    cursor = today if today in active_dates else today - timedelta(days=1)
    if cursor not in active_dates:
        return 0
    streak = 0
    while cursor in active_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def build_dashboard(conn, user: dict, scope: str, days: int | None, *, now: datetime | None = None):
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    settings = conn.execute(
        "SELECT collect_stats FROM user_settings WHERE user_id = ?", (user["id"],)
    ).fetchone()
    collecting = bool(settings and settings["collect_stats"])

    if scope == "house":
        eligible = conn.execute(
            "SELECT user_id FROM user_settings WHERE collect_stats = 1 ORDER BY user_id"
        ).fetchall()
        user_ids = [int(row["user_id"]) for row in eligible]
    else:
        user_ids = [int(user["id"])]

    participant_count = len(user_ids) if scope == "house" else 1
    if not user_ids:
        user_ids = [-1]
    placeholders = ",".join("?" for _ in user_ids)
    params: list[object] = list(user_ids)
    period_sql = ""
    if days is not None:
        cutoff = (now - timedelta(days=days - 1)).strftime("%Y-%m-%dT00:00:00Z")
        period_sql = " AND rs.started_at >= ?"
        params.append(cutoff)

    rows = conn.execute(
        "SELECT rs.*, d.title, d.visibility FROM reading_sessions rs "
        "JOIN documents d ON d.id = rs.document_id "
        f"WHERE rs.user_id IN ({placeholders}){period_sql} ORDER BY rs.started_at",
        params,
    ).fetchall()

    daily = defaultdict(lambda: {"words": 0, "reading_seconds": 0, "sessions": 0})
    modes = defaultdict(lambda: {"words": 0, "reading_seconds": 0, "sessions": 0, "wpm": []})
    documents = defaultdict(
        lambda: {"title": "", "words": 0, "reading_seconds": 0, "sessions": 0, "wpm": []}
    )
    total_words = 0
    total_seconds = 0
    wpm_samples: list[tuple[float, int]] = []

    for row in rows:
        words, seconds, wpm = _session_values(row)
        started = _parse_utc(row["started_at"])
        if started is None:
            continue
        day_key = started.date().isoformat()
        daily[day_key]["words"] += words
        daily[day_key]["reading_seconds"] += seconds
        daily[day_key]["sessions"] += 1

        mode = row["mode"] if row["mode"] in {"focus", "flow"} else "other"
        modes[mode]["words"] += words
        modes[mode]["reading_seconds"] += seconds
        modes[mode]["sessions"] += 1
        if wpm is not None:
            modes[mode]["wpm"].append((wpm, words))
            wpm_samples.append((wpm, words))

        # House totals may include opted-in private reading, but its title must
        # never be disclosed to another profile through the ranking.
        if scope != "house" or row["visibility"] == "house":
            doc = documents[int(row["document_id"])]
            doc["title"] = row["title"]
            doc["words"] += words
            doc["reading_seconds"] += seconds
            doc["sessions"] += 1
            if wpm is not None:
                doc["wpm"].append((wpm, words))

        total_words += words
        total_seconds += seconds

    progress_rows = conn.execute(
        f"SELECT status FROM reading_progress WHERE user_id IN ({placeholders})",
        list(user_ids),
    ).fetchall()
    engaged = sum(row["status"] in {"lendo", "lido", "abandonado"} for row in progress_rows)
    completed = sum(row["status"] == "lido" for row in progress_rows)

    daily_points = [{"date": key, **values} for key, values in sorted(daily.items())]
    mode_points = [
        {
            "mode": mode,
            "words": values["words"],
            "reading_seconds": values["reading_seconds"],
            "sessions": values["sessions"],
            "avg_wpm": _weighted_wpm(values["wpm"]),
        }
        for mode, values in sorted(modes.items())
    ]
    document_points = sorted(
        (
            {
                "document_id": document_id,
                "title": values["title"],
                "words": values["words"],
                "reading_seconds": values["reading_seconds"],
                "sessions": values["sessions"],
                "avg_wpm": _weighted_wpm(values["wpm"]),
            }
            for document_id, values in documents.items()
        ),
        key=lambda item: (-item["words"], item["title"].casefold()),
    )[:10]

    active_dates = {date.fromisoformat(point["date"]) for point in daily_points if point["words"] > 0}
    return {
        "scope": scope,
        "period_days": days,
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "collecting": collecting,
        "participants": participant_count,
        "summary": {
            "words": total_words,
            "reading_seconds": total_seconds,
            "sessions": len(rows),
            "avg_wpm": _weighted_wpm(wpm_samples),
            "streak_days": _current_streak(active_dates, now.date()),
            "completion_rate": round(completed / engaged * 100, 1) if engaged else 0.0,
            "completed_documents": completed,
            "engaged_documents": engaged,
        },
        "daily": daily_points,
        "modes": mode_points,
        "documents": document_points,
    }


@router.get("/stats/dashboard", response_model=StatsDashboard)
def dashboard(
    scope: Literal["me", "house"] = Query("me"),
    days: int = Query(30),
    user: dict = Depends(get_current_user),
):
    if days == 0:
        period_days = None
    elif days in PERIODS:
        period_days = days
    else:
        raise HTTPException(status_code=422, detail="Período inválido")
    conn = get_connection()
    try:
        return build_dashboard(conn, user, scope, period_days)
    finally:
        conn.close()
