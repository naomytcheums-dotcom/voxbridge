"""SQLite-backed call log.

Every call and every turn of the conversation is recorded here — this is
what a dashboard (or a recruiter) actually looks at, since a phone call
itself leaves no visual trace. Deliberately synchronous: call volume for a
single small business is nowhere near enough to need async DB access, and
sqlite3 needs no extra dependency.
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    caller_number TEXT,
    started_at REAL NOT NULL,
    ended_at REAL,
    first_audio_latency_ms REAL
);

CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id INTEGER NOT NULL REFERENCES calls(id),
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    at REAL NOT NULL
);
"""


@dataclass
class Call:
    id: int
    caller_number: str | None
    started_at: float
    ended_at: float | None
    first_audio_latency_ms: float | None


class CallLog:
    def __init__(self, db_path: str):
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def start_call(self, caller_number: str | None = None) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO calls (caller_number, started_at) VALUES (?, ?)",
                (caller_number, time.time()),
            )
            return cur.lastrowid

    def end_call(self, call_id: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE calls SET ended_at = ? WHERE id = ?", (time.time(), call_id))

    def log_turn(self, call_id: int, role: str, text: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO turns (call_id, role, text, at) VALUES (?, ?, ?, ?)",
                (call_id, role, text, time.time()),
            )

    def log_first_audio_latency(self, call_id: int, latency_ms: float) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE calls SET first_audio_latency_ms = ? WHERE id = ? AND first_audio_latency_ms IS NULL",
                (latency_ms, call_id),
            )

    def list_calls(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM calls ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_call(self, call_id: int) -> dict | None:
        with self._connect() as conn:
            call = conn.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
            if not call:
                return None
            turns = conn.execute(
                "SELECT role, text, at FROM turns WHERE call_id = ? ORDER BY at ASC", (call_id,)
            ).fetchall()
            return {**dict(call), "turns": [dict(t) for t in turns]}

    def latency_stats(self) -> dict:
        with self._connect() as conn:
            rows = [
                r["first_audio_latency_ms"]
                for r in conn.execute(
                    "SELECT first_audio_latency_ms FROM calls WHERE first_audio_latency_ms IS NOT NULL"
                ).fetchall()
            ]
        if not rows:
            return {"count": 0, "p50_ms": None, "p95_ms": None}
        ordered = sorted(rows)
        return {
            "count": len(ordered),
            "p50_ms": _percentile(ordered, 0.50),
            "p95_ms": _percentile(ordered, 0.95),
        }


def _percentile(sorted_values: list[float], p: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    idx = min(len(sorted_values) - 1, int(round(p * (len(sorted_values) - 1))))
    return sorted_values[idx]
