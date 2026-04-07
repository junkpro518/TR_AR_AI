"""Telegram bot — conversational Turkish tutor."""
import asyncio
import logging
import os
import random

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import db
from graph import TutorState, create_graph

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

TOKEN = os.getenv("TELEGRAM_TOKEN", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8443"))
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))

db.init_db()
graph = create_graph()


def _allowed(update: Update) -> bool:
    return ALLOWED_USER_ID == 0 or update.effective_user.id == ALLOWED_USER_ID


def _base_state(user_id: int, message: str) -> TutorState:
    return TutorState(
        user_id=user_id,
        user_message=message,
        profile={},
        history=[],
        weaknesses=[],
        due_strengths=[],
        message_count=0,
        route="chat",
        system_prompt="",
        response="",
        quiz_data={},
    )


async def _run(user_id: int, message: str) -> TutorState:
    return await asyncio.to_thread(graph.invoke, _base_state(user_id, message))


# ─── Handlers ─────────────────────────────────────────────────────────────────

async def handle_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    uid = update.effective_user.id
    db.get_or_create_profile(uid)
    await update.message.reply_text(
        "أهلاً! أنا معلمك للغة التركية 🇹🇷\n"
        "فقط تكلم معي بشكل طبيعي — بالعربية أو بأي تركية تعرفها.\n"
        "سأتعرف على ما تحتاجه وأعلمك بالطريقة المناسبة.\n\n"
        "ابدأ بأي شيء — حتى لو 'مرحبا' 😊"
    )


async def handle_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    stats = db.get_stats(update.effective_user.id)
    if not stats:
        await update.message.reply_text("لا يوجد تاريخ بعد. ابدأ بالتحدث!")
        return

    weak_text = "\n".join(
        f"  • {w['topic']} ({w['count']} مرة)"
        for w in stats.get("top_weaknesses", [])
    ) or "  لا شيء بعد"

    await update.message.reply_text(
        f"📊 إحصائياتك:\n"
        f"المستوى: {stats.get('level', 'A1')}\n"
        f"XP: {stats.get('xp', 0)}\n"
        f"Streak: {stats.get('streak', 0)} يوم\n"
        f"المفردات المحفوظة: {stats.get('vocab_count', 0)}\n"
        f"التركيز الحالي: {stats.get('current_focus', '-')}\n\n"
        f"نقاط الضعف الأبرز:\n{weak_text}"
    )


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    uid = update.effective_user.id
    user_text = update.message.text.strip()
    if not user_text:
        return

    await update.message.chat.send_action("typing")
    state = await _run(uid, user_text)

    # Send text response
    if state["response"]:
        await update.message.reply_text(state["response"])

    # Send quiz if present
    qd = state.get("quiz_data", {})
    if qd and qd.get("question") and qd.get("options"):
        options = qd["options"][:]
        random.shuffle(options)
        keyboard = [
            [InlineKeyboardButton(opt, callback_data=f"q:{opt}:{qd['answer']}")]
            for opt in options
        ]
        await update.message.reply_text(
            f"سؤال سريع 😄\n\n{qd['question']}",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def handle_quiz_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    _, chosen, correct = query.data.split(":", 2)
    if chosen == correct:
        await query.edit_message_text(f"✅ ممتاز! الجواب: {correct}")
        db.upsert_strength(query.from_user.id, f"quiz:{correct[:20]}")
    else:
        await query.edit_message_text(
            f"❌ الجواب الصحيح: {correct}\nاخترت: {chosen}\n\nسنراجعها لاحقاً 📝"
        )
        db.upsert_weakness(query.from_user.id, f"quiz:{correct[:20]}", chosen)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("stats", handle_stats))
    app.add_handler(CallbackQueryHandler(handle_quiz_callback, pattern=r"^q:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    if WEBHOOK_URL:
        logging.info("Webhook: %s", WEBHOOK_URL)
        app.run_webhook(listen="0.0.0.0", port=WEBHOOK_PORT, webhook_url=WEBHOOK_URL)
    else:
        logging.info("Polling...")
        app.run_polling()


if __name__ == "__main__":
    main()
