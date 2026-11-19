"""Storage layer for GDGoC AASTMT Python From Zero.

Uses PostgreSQL (via DATABASE_URL) with SQLAlchemy + NullPool for serverless.
Falls back to local SQLite when DATABASE_URL is not set (local dev / tests).
Keeps the same public interface as the original JsonStore so main.py is unchanged.
"""
from __future__ import annotations

import contextlib
import copy
import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool, StaticPool

logger = logging.getLogger("app.storage")

T = TypeVar("T")


@contextlib.contextmanager
def _nullctx():
    yield

def _get_engine():
    raw_url = os.environ.get("DATABASE_URL", "")
    if raw_url:
        # Convert legacy postgres:// scheme
        if raw_url.startswith("postgres://"):
            raw_url = "postgresql://" + raw_url[len("postgres://"):]
        # For transaction-mode Supabase pooler: disable prepared statements
        engine = create_engine(
            raw_url,
            poolclass=NullPool,
            connect_args={"sslmode": "require"} if "supabase.com" in raw_url or "neon.tech" in raw_url else {},
        )
    else:
        # Local SQLite fallback
        db_path = os.environ.get("LEADERBOARD_PATH", "leaderboard.db")
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return engine


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _quiz_meta(quiz_id: int) -> dict[str, int]:
    try:
        from app.question_bank import quiz_questions
        qs = quiz_questions(quiz_id)
        return {"possible_points": sum(q["points"] for q in qs), "question_count": len(qs)}
    except Exception:
        return {"possible_points": 40, "question_count": 20}


def _init_db(engine) -> None:
    """Create tables if they don't exist. Safe for cold-start serverless."""
    is_sqlite = engine.dialect.name == "sqlite"
    if is_sqlite:
        create_sql = """
        CREATE TABLE IF NOT EXISTS sessions (
            student_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS progress (
            student_id TEXT NOT NULL,
            quiz_id INTEGER NOT NULL,
            answers_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (student_id, quiz_id)
        );
        CREATE TABLE IF NOT EXISTS submissions (
            student_id TEXT NOT NULL,
            quiz_id INTEGER NOT NULL,
            points INTEGER NOT NULL DEFAULT 0,
            solved INTEGER NOT NULL DEFAULT 0,
            submitted_at TEXT DEFAULT (datetime('now')),
            UNIQUE (student_id, quiz_id)
        );
        """
    else:
        create_sql = """
        CREATE TABLE IF NOT EXISTS sessions (
            student_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS progress (
            student_id TEXT NOT NULL,
            quiz_id INT NOT NULL,
            answers_json JSONB NOT NULL DEFAULT '{}',
            updated_at TIMESTAMPTZ DEFAULT now(),
            PRIMARY KEY (student_id, quiz_id)
        );
        CREATE TABLE IF NOT EXISTS submissions (
            student_id TEXT NOT NULL,
            quiz_id INT NOT NULL,
            points INT NOT NULL DEFAULT 0,
            solved INT NOT NULL DEFAULT 0,
            submitted_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE (student_id, quiz_id)
        );
        """
    with engine.begin() as conn:
        for stmt in [s.strip() for s in create_sql.split(";") if s.strip()]:
            conn.execute(text(stmt))


# Module-level engine (created once per process / Lambda instance)
_engine = None


def _get_or_init_engine():
    global _engine
    if _engine is None:
        _engine = _get_engine()
        try:
            _init_db(_engine)
        except Exception as exc:
            logger.warning("DB init warning (may already exist): %s", exc)
    return _engine


class JsonStore:
    """SQLAlchemy-backed store with the same interface as the original JsonStore.

    Public methods used by main.py:
      - read()   -> dict[str, Any]   (compatible leaderboard data structure)
      - update(operation) -> T       (read-modify-write in a transaction)
    """

    def __init__(self, path=None) -> None:
        # `path` parameter kept for test compatibility — ignored when DATABASE_URL is set
        self._test_path = path  # used only in tests to create an isolated SQLite DB
        self._engine = None
        self._init_lock = threading.Lock()  # protect lazy engine + schema init

    def _get_engine(self):
        with self._init_lock:
            if self._engine is None:
                if self._test_path is not None:
                    # Test mode: isolated SQLite file with per-thread connections, WAL mode for concurrency
                    eng = create_engine(
                        f"sqlite:///{self._test_path}",
                        connect_args={"check_same_thread": False, "timeout": 30},
                    )
                    # Enable WAL mode so reads don't block writes
                    with eng.connect() as conn:
                        conn.execute(text("PRAGMA journal_mode=WAL"))
                    _init_db(eng)
                    self._engine = eng
                else:
                    self._engine = _get_or_init_engine()
        return self._engine

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _load_data(self, conn) -> dict[str, Any]:
        """Load all data into the legacy JsonStore dict structure."""
        # Sessions
        sessions = {
            row.student_id: {"name": row.name}
            for row in conn.execute(text("SELECT student_id, name FROM sessions")).fetchall()
        }

        # Progress
        for row in conn.execute(text("SELECT student_id, quiz_id, answers_json FROM progress")).fetchall():
            sid = row.student_id
            if sid in sessions:
                sessions[sid].setdefault("progress", {})[str(row.quiz_id)] = json.loads(
                    row.answers_json if isinstance(row.answers_json, str) else json.dumps(row.answers_json)
                )

        # Submissions
        for row in conn.execute(text(
            "SELECT student_id, quiz_id, points, solved, submitted_at FROM submissions"
        )).fetchall():
            sid = row.student_id
            if sid in sessions:
                qid = row.quiz_id
                meta = _quiz_meta(qid)
                sessions[sid].setdefault("quizzes", {})[str(qid)] = {
                    "score_points": row.points,
                    "possible_points": meta["possible_points"],
                    "solved": row.solved,
                    "question_count": meta["question_count"],
                    "completed_at": str(row.submitted_at),
                    "results": [],
                }

        # Ensure defaults
        for sid in sessions:
            sessions[sid].setdefault("quizzes", {})
            sessions[sid].setdefault("progress", {})
            sessions[sid].setdefault("last_seen", _utc_now())

        return {"schema_version": 1, "students": sessions}

    def _apply_diff(self, conn, old_data: dict, new_data: dict) -> None:
        """Persist changes from new_data back to the database."""
        old_students = old_data.get("students", {})
        new_students = new_data.get("students", {})

        for sid, student in new_students.items():
            name = student.get("name", "")
            if sid not in old_students:
                # New session
                conn.execute(text(
                    "INSERT INTO sessions (student_id, name) VALUES (:sid, :name) "
                    "ON CONFLICT (student_id) DO UPDATE SET name = EXCLUDED.name"
                ), {"sid": sid, "name": name})
            else:
                # Update name if changed
                if old_students[sid].get("name") != name:
                    conn.execute(text(
                        "UPDATE sessions SET name = :name WHERE student_id = :sid"
                    ), {"sid": sid, "name": name})

            # Sync progress
            new_progress = student.get("progress", {})
            old_progress = old_students.get(sid, {}).get("progress", {})
            for quiz_id_str, prog in new_progress.items():
                quiz_id = int(quiz_id_str)
                answers_str = json.dumps(prog)
                if quiz_id_str not in old_progress or old_progress[quiz_id_str] != prog:
                    conn.execute(text(
                        "INSERT INTO progress (student_id, quiz_id, answers_json) "
                        "VALUES (:sid, :qid, :aj) "
                        "ON CONFLICT (student_id, quiz_id) DO UPDATE SET answers_json = EXCLUDED.answers_json"
                    ), {"sid": sid, "qid": quiz_id, "aj": answers_str})

            # Sync submissions (first-score-only via ON CONFLICT DO NOTHING)
            new_quizzes = student.get("quizzes", {})
            old_quizzes = old_students.get(sid, {}).get("quizzes", {})
            for quiz_id_str, quiz in new_quizzes.items():
                if quiz_id_str not in old_quizzes:
                    quiz_id = int(quiz_id_str)
                    conn.execute(text(
                        "INSERT INTO submissions (student_id, quiz_id, points, solved) "
                        "VALUES (:sid, :qid, :pts, :slv) "
                        "ON CONFLICT (student_id, quiz_id) DO NOTHING"
                    ), {
                        "sid": sid,
                        "qid": quiz_id,
                        "pts": quiz.get("score_points", 0),
                        "slv": quiz.get("solved", 0),
                    })

    # ------------------------------------------------------------------ #
    # Public interface                                                     #
    # ------------------------------------------------------------------ #

    def read(self) -> dict[str, Any]:
        engine = self._get_engine()
        with engine.connect() as conn:
            return self._load_data(conn)

    def update(self, operation: Callable[[dict[str, Any]], T]) -> T:
        engine = self._get_engine()
        # For SQLite (tests), serialize concurrent writes to avoid SQLITE_BUSY
        is_sqlite = engine.dialect.name == "sqlite"
        ctx = self._init_lock if is_sqlite else _nullctx()
        with ctx:
            with engine.begin() as conn:
                data = self._load_data(conn)
                old_data = copy.deepcopy(data)
                result = operation(data)
                self._apply_diff(conn, old_data, data)
        return result
