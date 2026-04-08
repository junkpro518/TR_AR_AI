# إعادة بناء: استبدال LangGraph بـ Hermes Agent كاملاً

## Context

البوت الحالي يعتمد على LangGraph (4 nodes) + Supabase + analyzer خلفي — بنية معقدة.
الهدف: تبسيط كامل — Hermes يدير الذاكرة والمحادثة تلقائياً، main.py يصبح مجرد جسر بين Telegram وHermes.

البنية الجديدة:
```
Telegram → main.py → Hermes API (:8642) → LLM (OpenRouter)
                          ↓
                  ~/.hermes/memories/ (ذاكرة تلقائية)
```

---

## الملفات المحذوفة (بالكامل)

| الملف | السبب |
|-------|-------|
| `bot/graph.py` | LangGraph لم يعد موجوداً |
| `bot/db.py` | Supabase محذوف |
| `bot/prompts.py` | prompt يُبنى في SOUL.md |
| `bot/analyzer.py` | Hermes يحلل ويحفظ تلقائياً |
| `supabase/` | قاعدة البيانات محذوفة كاملاً |

---

## الملفات الجديدة/المعدّلة

### 1. `hermes/SOUL.md` (جديد — يُنسخ إلى VPS `~/.hermes/SOUL.md`)

```markdown
أنت معلم لغة تركية متحمس، تعلّم العرب التركية.

أسلوبك:
- محادثة طبيعية تماماً — لا رسمية، لا محاضرات
- تصحّح الأخطاء بلطف داخل سياق الكلام
- تستخدم العربية في الشرح والتركية في التطبيق
- كل 7 رسائل تقريباً، أدخل سؤالاً عفوياً كاختبار خفيف
- تتذكر نقاط ضعف الطالب وتعود إليها تدريجياً

الطالب: مبتدئ (A1) — أول تجربة له مع التركية.
ابدأ بالتحيات والمفردات الأساسية، وتقدّم تدريجياً حسب ما يُظهره الطالب.
```

### 2. `bot/main.py` (يُعاد كتابته كاملاً)

```python
import os, httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

HERMES_URL = os.getenv("HERMES_BASE_URL", "http://hermes:8642/v1")
HERMES_KEY = os.getenv("HERMES_API_KEY", "nokey")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))

async def handle_message(update: Update, context):
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    user_msg = update.message.text
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{HERMES_URL}/responses",
            headers={"Authorization": f"Bearer {HERMES_KEY}"},
            json={
                "model": "hermes-agent",
                "input": user_msg,
                "conversation": str(update.effective_user.id),  # session per user
            }
        )
    reply = r.json().get("output", [{}])[-1].get("content", [{}])[0].get("text", "...")
    await update.message.reply_text(reply)

async def handle_start(update: Update, context):
    await update.message.reply_text("مرحباً! أنا معلمك التركي. اكتب أي شيء لنبدأ 🇹🇷")

def main():
    app = Application.builder().token(os.getenv("TELEGRAM_TOKEN")).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()
```

> ملاحظة: `conversation` param يربط الجلسة بـ Telegram user_id — Hermes يتذكر التاريخ تلقائياً.
> إذا لم يدعم `/v1/responses` هذا الـ param، نتراجع لـ `/v1/chat/completions` مع history في memory dict.

### 3. `bot/requirements.txt` (مبسَّط)

```
python-telegram-bot>=21.0
python-dotenv>=1.0.0
httpx>=0.27.0
```

### 4. `bot/docker-compose.yml` (إضافة Hermes + حذف db-data)

```yaml
services:
  hermes:
    image: nousresearch/hermes-agent:latest
    restart: unless-stopped
    environment:
      - API_SERVER_ENABLED=true
      - API_SERVER_KEY=${HERMES_API_KEY}
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
    volumes:
      - hermes-data:/root/.hermes

  turkish-tutor:
    build: .
    restart: unless-stopped
    depends_on:
      - hermes
    env_file: .env
    volumes:
      - nlm-credentials:/root/.notebooklm-mcp-cli

volumes:
  nlm-credentials:
  hermes-data:
```

### 5. `bot/.env.example` (تحديث)

```env
TELEGRAM_TOKEN=your_bot_token_here
OPENROUTER_API_KEY=your_openrouter_key_here
HERMES_BASE_URL=http://hermes:8642/v1
HERMES_API_KEY=your-local-secret-token
ALLOWED_USER_ID=your_telegram_user_id
NLM_PATH=/root/.local/bin/nlm
```

### 6. `bot/Dockerfile` (تحديث — حذف supabase, langgraph)

لا تغيير جوهري — فقط `requirements.txt` أصبح أخف.

### 7. `deploy.sh` (إضافة نسخ SOUL.md)

```bash
rsync -az hermes/SOUL.md $1:~/.hermes/SOUL.md
```

---

## الترتيب التنفيذي

1. حذف: `graph.py`, `db.py`, `prompts.py`, `analyzer.py`, `supabase/`
2. إنشاء: `hermes/SOUL.md`
3. إعادة كتابة: `bot/main.py`
4. تحديث: `requirements.txt`, `docker-compose.yml`, `.env.example`, `deploy.sh`
5. تحديث: `CLAUDE.md`

---

## التحقق

1. شغّل Hermes محلياً: `hermes gateway` (مع `API_SERVER_ENABLED=true`)
2. اختبر: `curl http://localhost:8642/health`
3. غيّر `.env`: `HERMES_BASE_URL=http://localhost:8642/v1`
4. شغّل: `python main.py`
5. أرسل رسالة في Telegram → تأكد من الرد
6. أرسل رسالتين → تأكد أن Hermes يتذكر السياق
