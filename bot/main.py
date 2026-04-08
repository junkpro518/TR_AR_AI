"""Turkish tutor bot — Telegram gateway to Hermes Agent."""
from __future__ import annotations

import os
from dotenv import load_dotenv
load_dotenv()

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

HERMES_URL  = os.getenv("HERMES_BASE_URL", "http://hermes:8642/v1")
HERMES_KEY  = os.getenv("HERMES_API_KEY", "nokey")
HERMES_MODEL = os.getenv("HERMES_MODEL", "hermes-agent")
ALLOWED_UID = int(os.getenv("ALLOWED_USER_ID", "0"))

# Per-user conversation history (in-memory)
_sessions: dict[int, list[dict]] = {}
MAX_HISTORY = 20


def _get_history(uid: int) -> list[dict]:
    return _sessions.setdefault(uid, [])


def _append(uid: int, role: str, content: str) -> None:
    hist = _get_history(uid)
    hist.append({"role": role, "content": content})
    if len(hist) > MAX_HISTORY:
        _sessions[uid] = hist[-MAX_HISTORY:]


async def _ask_hermes(uid: int, user_msg: str) -> str:
    _append(uid, "user", user_msg)
    payload = {
        "model": HERMES_MODEL,
        "messages": _get_history(uid),
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{HERMES_URL}/chat/completions",
            headers={"Authorization": f"Bearer {HERMES_KEY}"},
            json=payload,
        )
        r.raise_for_status()
    reply = r.json()["choices"][0]["message"]["content"]
    _append(uid, "assistant", reply)
    return reply


async def handle_start(update: Update, context) -> None:
    if update.effective_user.id != ALLOWED_UID:
        return
    _sessions.pop(update.effective_user.id, None)  # fresh session
    await update.message.reply_text(
        "مرحباً! أنا معلمك التركي 🇹🇷\nاكتب أي شيء لنبدأ المحادثة."
    )


async def handle_message(update: Update, context) -> None:
    if update.effective_user.id != ALLOWED_UID:
        return
    await update.message.chat.send_action("typing")
    try:
        reply = await _ask_hermes(update.effective_user.id, update.message.text)
    except Exception as e:
        reply = f"حدث خطأ: {e}"
    await update.message.reply_text(reply)


def main() -> None:
    app = Application.builder().token(os.getenv("TELEGRAM_TOKEN", "")).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()


if __name__ == "__main__":
    main()
