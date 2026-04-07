"""Build dynamic system prompts — one per branch."""
from __future__ import annotations

_BASE = """أنت معلم لغة تركية شخصي. تتحدث مع الطالب بشكل طبيعي — كصديق يعلّم.
المستوى: {level} | التركيز: {focus} | Streak: {streak} يوم

══ صيغة [QUIZ] (استخدمها عند الحاجة) ══
[QUIZ]
السؤال: ...
أ) ...  ب) ...  ج) ...  د) ...
الجواب: أ
[/QUIZ]
"""

_WEAK_LINES = lambda w: "\n".join(
    f"  - {x['topic']} ({x['count']} مرة)" + (f" — مثال: {x['example']}" if x.get("example") else "")
    for x in w
) or "  لا توجد بعد"


def build_chat_prompt(profile: dict, weaknesses: list, due_strengths: list) -> str:
    base = _BASE.format(
        level=profile.get("level", "A1"),
        focus=profile.get("current_focus", "التحية"),
        streak=profile.get("streak", 0),
    )
    strength_lines = "\n".join(f"  - {s['topic']}" for s in due_strengths) or "  لا شيء اليوم"
    return base + f"""
══ نقاط الضعف (راقبها) ══
{_WEAK_LINES(weaknesses)}

══ قوة مستحقة للمراجعة ══
{strength_lines}

تعليمات:
- تكلم بشكل طبيعي، لا محاضرات
- صحّح الأخطاء بلطف داخل السياق
- اشرح بالعربية، أمثلة بالتركية
"""


def build_quiz_prompt(profile: dict, weak_topic: str) -> str:
    base = _BASE.format(
        level=profile.get("level", "A1"),
        focus=profile.get("current_focus", "التحية"),
        streak=profile.get("streak", 0),
    )
    return base + f"""
المهمة الآن: أدخل اختباراً [QUIZ] عن موضوع "{weak_topic}" بشكل عفوي في المحادثة.
ابدأ بجملة طبيعية ثم أدرج الكويز مباشرة.
الكويز يجب أن يختبر تحديداً هذا الموضوع بمستوى A1.
"""


def build_drill_prompt(profile: dict, weak_topic: str, example: str) -> str:
    base = _BASE.format(
        level=profile.get("level", "A1"),
        focus=profile.get("current_focus", "التحية"),
        streak=profile.get("streak", 0),
    )
    return base + f"""
لاحظت أن الطالب يكرر خطأ في: "{weak_topic}"
مثال من محادثاته: "{example}"

المهمة الآن: صمّم تمريناً مركّزاً قصيراً (2-3 أسئلة) يعالج هذا الخطأ تحديداً.
ابدأ بتصحيح لطيف ثم انتقل للتمرين بشكل طبيعي.
"""


def build_review_prompt(profile: dict, review_topic: str) -> str:
    base = _BASE.format(
        level=profile.get("level", "A1"),
        focus=profile.get("current_focus", "التحية"),
        streak=profile.get("streak", 0),
    )
    return base + f"""
الطالب أتقن سابقاً موضوع: "{review_topic}" — وحان وقت مراجعته.
المهمة: ادمج مراجعة هذا الموضوع في المحادثة بشكل طبيعي وعفوي.
لا تقل "سنراجع" — فقط ابدأ باستخدام الموضوع في الحوار.
"""


def build_nlm_context(nlm_answer: str) -> str:
    if not nlm_answer:
        return ""
    return f"\n══ معلومات من المصادر (استخدمها إذا أفادت) ══\n{nlm_answer}\n"
