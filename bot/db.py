"""SQLite database — schema + CRUD for the Turkish tutor."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "tutor.db"


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db() -> None:
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS profile (
            user_id     INTEGER PRIMARY KEY,
            level       TEXT    DEFAULT 'A1',
            xp          INTEGER DEFAULT 0,
            streak      INTEGER DEFAULT 0,
            last_active TEXT,
            current_focus TEXT  DEFAULT 'التحية والمفردات الأساسية'
        );

        CREATE TABLE IF NOT EXISTS messages (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER NOT NULL,
            role      TEXT    NOT NULL,
            content   TEXT    NOT NULL,
            timestamp TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS weaknesses (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER NOT NULL,
            topic     TEXT    NOT NULL,
            count     INTEGER DEFAULT 1,
            last_seen TEXT    DEFAULT (datetime('now')),
            example   TEXT,
            UNIQUE(user_id, topic)
        );

        CREATE TABLE IF NOT EXISTS strengths (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            topic        TEXT    NOT NULL,
            confirmed_at TEXT    DEFAULT (datetime('now')),
            review_due   TEXT,
            UNIQUE(user_id, topic)
        );

        CREATE TABLE IF NOT EXISTS vocab_srs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            word        TEXT    NOT NULL,
            translation TEXT    NOT NULL,
            ease_factor REAL    DEFAULT 2.5,
            interval    INTEGER DEFAULT 1,
            due_date    TEXT    DEFAULT (date('now')),
            repetitions INTEGER DEFAULT 0,
            UNIQUE(user_id, word)
        );
        """)


# ─── Profile ──────────────────────────────────────────────────────────────────

def get_or_create_profile(user_id: int) -> dict:
    with conn() as c:
        row = c.execute("SELECT * FROM profile WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            c.execute("INSERT INTO profile (user_id) VALUES (?)", (user_id,))
            row = c.execute("SELECT * FROM profile WHERE user_id=?", (user_id,)).fetchone()
        _update_streak(c, user_id)
        return dict(row)


def _update_streak(c: sqlite3.Connection, user_id: int) -> None:
    today = date.today().isoformat()
    row = c.execute("SELECT last_active, streak FROM profile WHERE user_id=?", (user_id,)).fetchone()
    if not row:
        return
    last = row["last_active"]
    streak = row["streak"]
    if last == today:
        return
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    new_streak = streak + 1 if last == yesterday else 1
    c.execute("UPDATE profile SET streak=?, last_active=? WHERE user_id=?",
              (new_streak, today, user_id))


def update_focus(user_id: int, focus: str) -> None:
    with conn() as c:
        c.execute("UPDATE profile SET current_focus=? WHERE user_id=?", (focus, user_id))


def add_xp(user_id: int, amount: int = 5) -> None:
    with conn() as c:
        c.execute("UPDATE profile SET xp=xp+? WHERE user_id=?", (amount, user_id))


# ─── Messages ─────────────────────────────────────────────────────────────────

def save_message(user_id: int, role: str, content: str) -> None:
    with conn() as c:
        c.execute("INSERT INTO messages (user_id, role, content) VALUES (?,?,?)",
                  (user_id, role, content))


def get_recent_messages(user_id: int, n: int = 20) -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT role, content FROM messages WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, n)
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


# ─── Weaknesses ───────────────────────────────────────────────────────────────

def upsert_weakness(user_id: int, topic: str, example: str = "") -> None:
    with conn() as c:
        c.execute("""
        INSERT INTO weaknesses (user_id, topic, count, last_seen, example)
        VALUES (?, ?, 1, datetime('now'), ?)
        ON CONFLICT(user_id, topic) DO UPDATE SET
            count    = count + 1,
            last_seen = datetime('now'),
            example  = excluded.example
        """, (user_id, topic, example))


def get_top_weaknesses(user_id: int, n: int = 3) -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT topic, count, example FROM weaknesses WHERE user_id=? ORDER BY count DESC LIMIT ?",
            (user_id, n)
        ).fetchall()
    return [dict(r) for r in rows]


# ─── Strengths ────────────────────────────────────────────────────────────────

def upsert_strength(user_id: int, topic: str) -> None:
    review_due = (date.today() + timedelta(days=7)).isoformat()
    with conn() as c:
        c.execute("""
        INSERT INTO strengths (user_id, topic, confirmed_at, review_due)
        VALUES (?, ?, datetime('now'), ?)
        ON CONFLICT(user_id, topic) DO UPDATE SET
            confirmed_at = datetime('now'),
            review_due   = excluded.review_due
        """, (user_id, topic, review_due))


def get_due_strengths(user_id: int) -> list[dict]:
    today = date.today().isoformat()
    with conn() as c:
        rows = c.execute(
            "SELECT topic FROM strengths WHERE user_id=? AND review_due <= ?",
            (user_id, today)
        ).fetchall()
    return [dict(r) for r in rows]


# ─── Vocab SRS (SM-2) ─────────────────────────────────────────────────────────

def add_vocab(user_id: int, word: str, translation: str) -> None:
    with conn() as c:
        c.execute("""
        INSERT OR IGNORE INTO vocab_srs (user_id, word, translation) VALUES (?,?,?)
        """, (user_id, word, translation))


def get_due_vocab(user_id: int, n: int = 5) -> list[dict]:
    today = date.today().isoformat()
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM vocab_srs WHERE user_id=? AND due_date<=? ORDER BY due_date LIMIT ?",
            (user_id, today, n)
        ).fetchall()
    return [dict(r) for r in rows]


def update_vocab_srs(user_id: int, word: str, quality: int) -> None:
    """quality: 0-5 (SM-2 standard). 0-2=fail, 3-5=pass."""
    with conn() as c:
        row = c.execute(
            "SELECT ease_factor, interval, repetitions FROM vocab_srs WHERE user_id=? AND word=?",
            (user_id, word)
        ).fetchone()
        if not row:
            return
        ef, interval, reps = row["ease_factor"], row["interval"], row["repetitions"]
        if quality < 3:
            interval, reps = 1, 0
        else:
            if reps == 0:
                interval = 1
            elif reps == 1:
                interval = 6
            else:
                interval = round(interval * ef)
            reps += 1
        ef = max(1.3, ef + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        due = (date.today() + timedelta(days=interval)).isoformat()
        c.execute("""
        UPDATE vocab_srs SET ease_factor=?, interval=?, repetitions=?, due_date=?
        WHERE user_id=? AND word=?
        """, (ef, interval, reps, due, user_id, word))


# ─── Stats ────────────────────────────────────────────────────────────────────

def get_stats(user_id: int) -> dict:
    with conn() as c:
        profile = dict(c.execute("SELECT * FROM profile WHERE user_id=?", (user_id,)).fetchone() or {})
        vocab_count = c.execute(
            "SELECT COUNT(*) as n FROM vocab_srs WHERE user_id=?", (user_id,)
        ).fetchone()["n"]
        weaknesses = [dict(r) for r in c.execute(
            "SELECT topic, count FROM weaknesses WHERE user_id=? ORDER BY count DESC LIMIT 3",
            (user_id,)
        ).fetchall()]
    return {**profile, "vocab_count": vocab_count, "top_weaknesses": weaknesses}
