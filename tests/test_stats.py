import sqlite3
from datetime import datetime, timezone

import unittest
from unittest.mock import patch
from fastapi import HTTPException

from app.routers import stats


NOW = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)


def make_connection():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE user_settings (user_id INTEGER PRIMARY KEY, collect_stats INTEGER NOT NULL);
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            visibility TEXT NOT NULL
        );
        CREATE TABLE reading_sessions (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            document_id INTEGER NOT NULL,
            mode TEXT NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            updated_at TEXT NOT NULL,
            words_advanced INTEGER,
            avg_wpm REAL
        );
        CREATE TABLE reading_progress (
            user_id INTEGER NOT NULL,
            document_id INTEGER NOT NULL,
            status TEXT NOT NULL
        );
        """
    )
    conn.executemany(
        "INSERT INTO user_settings(user_id, collect_stats) VALUES (?, ?)",
        [(1, 1), (2, 1), (3, 0)],
    )
    conn.executemany(
        "INSERT INTO documents(id, title, visibility) VALUES (?, ?, ?)",
        [
            (10, "Meu livro", "private"),
            (20, "Livro da casa", "house"),
            (30, "Diario privado", "private"),
        ],
    )
    conn.executemany(
        """
        INSERT INTO reading_sessions(
            id, user_id, document_id, mode, started_at, ended_at, updated_at,
            words_advanced, avg_wpm
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (1, 1, 10, "focus", "2026-07-16T10:00:00Z", "2026-07-16T10:10:00Z", "2026-07-16T10:10:00Z", 100, 300),
            (2, 1, 20, "flow", "2026-07-15T10:00:00Z", "2026-07-15T10:05:00Z", "2026-07-15T10:05:00Z", 50, 200),
            (3, 2, 20, "focus", "2026-07-16T09:00:00Z", "2026-07-16T09:20:00Z", "2026-07-16T09:20:00Z", 200, 400),
            (4, 2, 30, "focus", "2026-07-16T08:00:00Z", "2026-07-16T08:03:00Z", "2026-07-16T08:03:00Z", 70, 350),
            (5, 3, 20, "focus", "2026-07-16T07:00:00Z", "2026-07-16T07:30:00Z", "2026-07-16T07:30:00Z", 999, 500),
            (6, 1, 20, "focus", "2026-07-16T11:00:00Z", "2026-07-16T10:59:00Z", "2026-07-16T11:00:00Z", -40, 250),
        ],
    )
    conn.executemany(
        "INSERT INTO reading_progress(user_id, document_id, status) VALUES (?, ?, ?)",
        [(1, 10, "lido"), (1, 20, "lendo"), (2, 20, "lido"), (2, 30, "abandonado"), (3, 20, "lido")],
    )
    return conn


class StatsAggregationTests(unittest.TestCase):
 def test_personal_dashboard_calculates_weighted_metrics_and_streak(self):
    conn = make_connection()
    try:
        result = stats.build_dashboard(conn, {"id": 1}, "me", 30, now=NOW)
    finally:
        conn.close()

    assert result["summary"]["words"] == 150
    assert result["summary"]["reading_seconds"] == 900
    self.assertAlmostEqual(result["summary"]["avg_wpm"], 266.7)
    assert result["summary"]["streak_days"] == 2
    assert result["summary"]["completion_rate"] == 50.0
    assert result["summary"]["sessions"] == 3
    assert {item["title"] for item in result["documents"]} == {"Meu livro", "Livro da casa"}


 def test_house_excludes_opt_out_and_never_discloses_private_titles(self):
    conn = make_connection()
    try:
        result = stats.build_dashboard(conn, {"id": 1}, "house", 30, now=NOW)
    finally:
        conn.close()

    assert result["participants"] == 2
    assert result["summary"]["words"] == 420
    assert result["summary"]["reading_seconds"] == 2280
    assert {item["title"] for item in result["documents"]} == {"Livro da casa"}
    assert "Diario privado" not in str(result)
    assert "Meu livro" not in str(result)


 def test_house_with_no_opted_in_profiles_reports_zero_participants(self):
    conn = make_connection()
    conn.execute("UPDATE user_settings SET collect_stats = 0")
    try:
        result = stats.build_dashboard(conn, {"id": 1}, "house", 7, now=NOW)
    finally:
        conn.close()

    assert result["participants"] == 0
    assert result["summary"]["words"] == 0
    assert result["daily"] == []


class TrackingConnection:
    def __init__(self, connection):
        self.connection = connection
        self.closed = False

    def execute(self, *args, **kwargs):
        return self.connection.execute(*args, **kwargs)

    def close(self):
        self.closed = True
        self.connection.close()


class StatsEndpointTests(unittest.TestCase):
 def test_dashboard_endpoint_always_closes_connection(self):
    tracked = TrackingConnection(make_connection())

    with patch.object(stats, "get_connection", return_value=tracked):
        result = stats.dashboard(scope="me", days=30, user={"id": 1})

    assert result["scope"] == "me"
    assert tracked.closed is True


 def test_dashboard_rejects_unknown_period_before_opening_connection(self):
    def fail_connection():
        self.fail("connection should not open")

    with patch.object(stats, "get_connection", side_effect=fail_connection):
        with self.assertRaises(HTTPException) as error:
            stats.dashboard(scope="me", days=12, user={"id": 1})

    assert error.exception.status_code == 422

