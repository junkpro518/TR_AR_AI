"""Supabase database — CRUD for the Turkish tutor."""
from __future__ import annotations

import os
from datetime import date, timedelta

from supabase import Client, create_client

_client: Client | None = None


def _db() -> Client:
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_KEY", "")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
        _client = create_client(url, key)
    return _client


def init_db() -> None:
    """Verify Supabase connection. Tables are created via supabase/schema.sql."""
    _db()


# ─── Profile ──────────────────────────────────────────────────────────────────

def get_or_create_profile(user_id: int) -> dict:
    db = _db()
    res = db.table("profile").select("*").eq("user_id", user_id).execute()
    if not res.data:
        db.table("profile").insert({
            "user_id": user_id,
            "level": "A1",
            "xp": 0,
            "streak": 0,
            "last_active": None,
            "current_focus": "التحية والمفردات الأساسية",
        }).execute()
        res = db.table("profile").select("*").eq("user_id", user_id).execute()

    profile = res.data[0]
    _update_streak(user_id, profile)
    # Refresh after streak update
    return db.table("profile").select("*").eq("user_id", user_id).execute().data[0]


def _update_streak(user_id: int, profile: dict) -> None:
    today = date.today().isoformat()
    last = profile.get("last_active")
    if last == today:
        return
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    new_streak = (profile.get("streak") or 0) + 1 if last == yesterday else 1
    _db().table("profile").update({
        "streak": new_streak,
        "last_active": today,
    }).eq("user_id", user_id).execute()


def update_focus(user_id: int, focus: str) -> None:
    _db().table("profile").update({"current_focus": focus}).eq("user_id", user_id).execute()


def add_xp(user_id: int, amount: int = 5) -> None:
    profile = _db().table("profile").select("xp").eq("user_id", user_id).execute().data
    if profile:
        _db().table("profile").update({"xp": profile[0]["xp"] + amount}).eq("user_id", user_id).execute()


# ─── Messages ─────────────────────────────────────────────────────────────────

def save_message(user_id: int, role: str, content: str) -> None:
    _db().table("messages").insert({
        "user_id": user_id,
        "role": role,
        "content": content,
    }).execute()


def get_recent_messages(user_id: int, n: int = 20) -> list[dict]:
    res = (
        _db().table("messages")
        .select("role, content")
        .eq("user_id", user_id)
        .order("id", desc=True)
        .limit(n)
        .execute()
    )
    return list(reversed(res.data))


# ─── Weaknesses ───────────────────────────────────────────────────────────────

def upsert_weakness(user_id: int, topic: str, example: str = "") -> None:
    db = _db()
    today = date.today().isoformat()
    existing = db.table("weaknesses").select("id, count").eq("user_id", user_id).eq("topic", topic).execute()
    if existing.data:
        row = existing.data[0]
        db.table("weaknesses").update({
            "count": row["count"] + 1,
            "last_seen": today,
            "example": example or None,
        }).eq("id", row["id"]).execute()
    else:
        db.table("weaknesses").insert({
            "user_id": user_id,
            "topic": topic,
            "count": 1,
            "last_seen": today,
            "example": example or None,
        }).execute()


def get_top_weaknesses(user_id: int, n: int = 3) -> list[dict]:
    res = (
        _db().table("weaknesses")
        .select("topic, count, example")
        .eq("user_id", user_id)
        .order("count", desc=True)
        .limit(n)
        .execute()
    )
    return res.data


# ─── Strengths ────────────────────────────────────────────────────────────────

def upsert_strength(user_id: int, topic: str) -> None:
    db = _db()
    review_due = (date.today() + timedelta(days=7)).isoformat()
    today = date.today().isoformat()
    existing = db.table("strengths").select("id").eq("user_id", user_id).eq("topic", topic).execute()
    if existing.data:
        db.table("strengths").update({
            "confirmed_at": today,
            "review_due": review_due,
        }).eq("id", existing.data[0]["id"]).execute()
    else:
        db.table("strengths").insert({
            "user_id": user_id,
            "topic": topic,
            "confirmed_at": today,
            "review_due": review_due,
        }).execute()


def get_due_strengths(user_id: int) -> list[dict]:
    today = date.today().isoformat()
    res = (
        _db().table("strengths")
        .select("topic")
        .eq("user_id", user_id)
        .lte("review_due", today)
        .execute()
    )
    return res.data


# ─── Vocab SRS (SM-2) ─────────────────────────────────────────────────────────

def add_vocab(user_id: int, word: str, translation: str) -> None:
    db = _db()
    existing = db.table("vocab_srs").select("id").eq("user_id", user_id).eq("word", word).execute()
    if not existing.data:
        db.table("vocab_srs").insert({
            "user_id": user_id,
            "word": word,
            "translation": translation,
            "ease_factor": 2.5,
            "interval": 1,
            "due_date": date.today().isoformat(),
            "repetitions": 0,
        }).execute()


def get_due_vocab(user_id: int, n: int = 5) -> list[dict]:
    today = date.today().isoformat()
    res = (
        _db().table("vocab_srs")
        .select("*")
        .eq("user_id", user_id)
        .lte("due_date", today)
        .order("due_date")
        .limit(n)
        .execute()
    )
    return res.data


def update_vocab_srs(user_id: int, word: str, quality: int) -> None:
    """quality: 0-5 (SM-2). 0-2=fail, 3-5=pass."""
    res = (
        _db().table("vocab_srs")
        .select("ease_factor, interval, repetitions")
        .eq("user_id", user_id).eq("word", word)
        .execute()
    )
    if not res.data:
        return
    row = res.data[0]
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

    _db().table("vocab_srs").update({
        "ease_factor": ef,
        "interval": interval,
        "repetitions": reps,
        "due_date": due,
    }).eq("user_id", user_id).eq("word", word).execute()


# ─── Stats ────────────────────────────────────────────────────────────────────

def get_stats(user_id: int) -> dict:
    db = _db()
    profile_res = db.table("profile").select("*").eq("user_id", user_id).execute()
    if not profile_res.data:
        return {}
    profile = profile_res.data[0]

    vocab_count = len(db.table("vocab_srs").select("id").eq("user_id", user_id).execute().data)
    weaknesses = (
        db.table("weaknesses")
        .select("topic, count")
        .eq("user_id", user_id)
        .order("count", desc=True)
        .limit(3)
        .execute()
        .data
    )
    return {**profile, "vocab_count": vocab_count, "top_weaknesses": weaknesses}
