"""Background analyzer — extracts weaknesses/strengths/vocab from a conversation turn."""
from __future__ import annotations

import json
import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

import db

_llm = ChatOpenAI(
    model=os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-120b"),
    openai_api_key=os.getenv("OPENROUTER_API_KEY", ""),
    openai_api_base="https://openrouter.ai/api/v1",
    max_tokens=512,
    temperature=0,
)

_PROMPT = """أنت محلل لغوي. بُعد هذه الرسالة من الطالب وهذا الرد من المعلم التركي، استخرج:

رسالة الطالب: {user_msg}
رد المعلم: {bot_msg}

أجب بـ JSON فقط (لا شرح):
{{
  "weaknesses": [{{"topic": "...", "example": "..."}}],
  "strengths": [{{"topic": "..."}}],
  "new_vocab": [{{"word": "...", "translation": "..."}}],
  "focus_update": null
}}

القواعد:
- weaknesses: مواضيع أخطأ فيها الطالب (نحو، مفردات، تصريف...)
- strengths: مواضيع أجاد فيها أو أكملها الطالب بشكل صحيح
- new_vocab: كلمات تركية جديدة ظهرت في الرد
- focus_update: null إلا إذا يجب تغيير التركيز تماماً
- إذا لا يوجد شيء مستخرج، أعطِ قوائم فارغة
"""


def analyze_turn(user_id: int, user_msg: str, bot_msg: str) -> None:
    """Run background analysis and update DB. Called after response is sent."""
    try:
        response = _llm.invoke([
            HumanMessage(content=_PROMPT.format(user_msg=user_msg, bot_msg=bot_msg))
        ])
        text = response.content.strip()
        start, end = text.find("{"), text.rfind("}") + 1
        if start == -1:
            return
        data = json.loads(text[start:end])
    except Exception:
        return

    for w in data.get("weaknesses", []):
        if w.get("topic"):
            db.upsert_weakness(user_id, w["topic"], w.get("example", ""))

    for s in data.get("strengths", []):
        if s.get("topic"):
            db.upsert_strength(user_id, s["topic"])

    for v in data.get("new_vocab", []):
        if v.get("word") and v.get("translation"):
            db.add_vocab(user_id, v["word"], v["translation"])

    focus = data.get("focus_update")
    if focus:
        db.update_focus(user_id, focus)

    db.add_xp(user_id, 5)
