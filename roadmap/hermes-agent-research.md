# Hermes Agent — بحث تقني كامل

## ما هو hermes-agent؟

**ليس** LLM API ولا نموذج مستضاف. هو **agent runtime محلي** مفتوح المصدر (MIT) من Nous Research يعمل على جهازك أو VPS ويضيف طبقة ذكاء فوق أي LLM provider.

يُشغَّل كعملية محلية دائمة، ويتواصل مع 14+ منصة (Telegram, Discord, Slack, WhatsApp...).

---

## API Server (OpenAI-compatible)

Hermes يعرض API كاملاً متوافقاً مع OpenAI:

| المعامل | القيمة |
|---------|--------|
| Base URL | `http://localhost:8642/v1` |
| Model name | `hermes-agent` |
| Auth | `Authorization: Bearer <API_SERVER_KEY>` |

### تفعيله في `~/.hermes/.env`:
```env
API_SERVER_ENABLED=true
API_SERVER_KEY=your-secret-token
```

### تشغيله:
```bash
hermes gateway
```

### Endpoints المتاحة:
| Endpoint | الوظيفة |
|----------|---------|
| `POST /v1/chat/completions` | OpenAI chat completions |
| `POST /v1/responses` | OpenAI Responses API |
| `GET /v1/models` | يعيد `hermes-agent` |
| `GET /health` | فحص الحالة |
| `GET/POST /api/jobs` | Cron jobs REST API |

---

## الاستخدام مع langchain_openai

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://localhost:8642/v1",
    api_key=os.getenv("HERMES_API_KEY", "nokey"),
    model="hermes-agent"
)
```

### Session continuity:
إرسال التاريخ كاملاً مع كل طلب (نفس الطريقة الحالية مع OpenRouter).

---

## LLM Providers المدعومة (30+)

Hermes يعمل كـ proxy فوق أي provider:

| Provider | Env Variable |
|----------|-------------|
| OpenRouter | `OPENROUTER_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| DeepSeek | `DEEPSEEK_API_KEY` |
| Ollama (محلي) | `http://localhost:11434/v1` |
| vLLM (محلي) | `http://localhost:8000/v1` |
| Groq | `https://api.groq.com/openai/v1` |
| Mistral | `https://api.mistral.ai/v1` |

---

## التثبيت على VPS

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
source ~/.bashrc
hermes setup
hermes gateway  # يبدأ API server على :8642
```

### Config (`~/.hermes/config.yaml`):
```yaml
model:
  default: "nousresearch/hermes-3-llama-3.1-405b"
  provider: "openrouter"

agent:
  reasoning_effort: medium
  max_turns: 90
```

---

## التغييرات المطلوبة في المشروع

### `.env`:
```env
HERMES_API_KEY=your-local-token
HERMES_BASE_URL=http://localhost:8642/v1
HERMES_MODEL=hermes-agent
```

### `graph.py` و `analyzer.py`:
```python
# قبل:
openai_api_base="https://openrouter.ai/api/v1"
model=os.getenv("OPENROUTER_MODEL")
api_key=os.getenv("OPENROUTER_API_KEY")

# بعد:
openai_api_base=os.getenv("HERMES_BASE_URL", "http://localhost:8642/v1")
model=os.getenv("HERMES_MODEL", "hermes-agent")
api_key=os.getenv("HERMES_API_KEY", "nokey")
```

### `docker-compose.yml`:
إضافة Hermes كـ service يعمل مع البوت.

---

## مقارنة البنيتين

| | OpenRouter (الحالي) | Hermes Agent |
|--|--------------------|-|
| API call | مباشر للـ cloud | محلي → Hermes → cloud |
| Memory | Supabase (يدوي) | Hermes يتولاها + Supabase |
| Model flexibility | تغيير في `.env` | تغيير في Hermes config |
| Latency | أقل | أعلى قليلاً (local hop) |
| Capabilities | LLM فقط | LLM + tools + memory + skills |
| Setup complexity | بسيط | يحتاج تثبيت Hermes على VPS |

---

## ملاحظات مهمة

1. **Hermes يجب أن يكون شغّالاً** على VPS قبل أن يستطيع البوت الاتصال به
2. **النموذج الفعلي** يُحدَّد في `~/.hermes/config.yaml` — يمكن استخدام OpenRouter كـ backend داخل Hermes
3. **Session continuity** عبر `X-Hermes-Session-Id` header — أفضل من إرسال التاريخ كاملاً
4. **Hermes يضيف ذاكرة ومهارات تلقائية** فوق أي LLM

---

*تاريخ البحث: 2026-04-07*
*المصادر: hermes-agent.nousresearch.com/docs*
