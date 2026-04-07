"""LangGraph conversational tutor — conditional branching."""
from __future__ import annotations

import os
import re
import threading
from typing import Literal, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

import db
from analyzer import analyze_turn
from nodes.fetch_content import query_notebook
from prompts import (
    build_chat_prompt,
    build_drill_prompt,
    build_nlm_context,
    build_quiz_prompt,
    build_review_prompt,
)

_llm = ChatOpenAI(
    model=os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-120b"),
    openai_api_key=os.getenv("OPENROUTER_API_KEY", ""),
    openai_api_base="https://openrouter.ai/api/v1",
    max_tokens=1024,
)

NOTEBOOK_ID = os.getenv("NOTEBOOK_ID", "")

Route = Literal["chat", "quiz", "drill", "review"]


class TutorState(TypedDict):
    user_id: int
    user_message: str
    # loaded from DB
    profile: dict
    history: list[dict]
    weaknesses: list[dict]
    due_strengths: list[dict]
    message_count: int
    # computed
    route: Route
    system_prompt: str
    response: str
    quiz_data: dict


# ─── Node 1: Load context ────────────────────────────────────────────────────

def load_context(state: TutorState) -> TutorState:
    uid = state["user_id"]
    profile = db.get_or_create_profile(uid)
    history = db.get_recent_messages(uid, n=20)
    weaknesses = db.get_top_weaknesses(uid, n=3)
    due_strengths = db.get_due_strengths(uid)
    return {
        **state,
        "profile": profile,
        "history": history,
        "weaknesses": weaknesses,
        "due_strengths": due_strengths,
        "message_count": len(history),
        "route": "chat",       # default — overwritten by router
        "system_prompt": "",
        "response": "",
        "quiz_data": {},
    }


# ─── Router (deterministic — no LLM needed) ──────────────────────────────────

def router(state: TutorState) -> Route:
    count = state["message_count"]
    weaknesses = state["weaknesses"]
    due_strengths = state["due_strengths"]

    # 1. Focused drill when top weakness appears 3+ times
    if weaknesses and weaknesses[0]["count"] >= 3:
        return "drill"

    # 2. Quiz every 7 messages
    if count > 0 and count % 7 == 0:
        return "quiz"

    # 3. Strength review every 5 messages (if any due)
    if due_strengths and count > 0 and count % 5 == 0:
        return "review"

    return "chat"


# ─── Node helpers ─────────────────────────────────────────────────────────────

def _nlm_context(focus: str) -> str:
    if not NOTEBOOK_ID or not focus:
        return ""
    result = query_notebook(f"شرح مختصر: {focus}")
    answer = result.get("answer", "")
    return build_nlm_context(answer) if answer and "لا توجد مصادر" not in answer else ""


def _call_llm(system: str, history: list[dict], user_message: str) -> str:
    messages = [SystemMessage(content=system)]
    for msg in history:
        cls = HumanMessage if msg["role"] == "user" else AIMessage
        messages.append(cls(content=msg["content"]))
    messages.append(HumanMessage(content=user_message))
    return _llm.invoke(messages).content


# ─── Node 2a: Normal chat ────────────────────────────────────────────────────

def chat_node(state: TutorState) -> TutorState:
    system = build_chat_prompt(
        state["profile"], state["weaknesses"], state["due_strengths"]
    ) + _nlm_context(state["profile"].get("current_focus", ""))

    raw = _call_llm(system, state["history"], state["user_message"])
    quiz_data = _parse_quiz(raw)
    response = re.sub(r"\[QUIZ\].*?\[/QUIZ\]", "", raw, flags=re.DOTALL).strip()
    return {**state, "route": "chat", "system_prompt": system,
            "response": response, "quiz_data": quiz_data}


# ─── Node 2b: Quiz on weak topic ─────────────────────────────────────────────

def quiz_node(state: TutorState) -> TutorState:
    weak_topic = (
        state["weaknesses"][0]["topic"] if state["weaknesses"]
        else state["profile"].get("current_focus", "المفردات الأساسية")
    )
    system = build_quiz_prompt(state["profile"], weak_topic)
    raw = _call_llm(system, state["history"], state["user_message"])
    quiz_data = _parse_quiz(raw)
    response = re.sub(r"\[QUIZ\].*?\[/QUIZ\]", "", raw, flags=re.DOTALL).strip()
    return {**state, "route": "quiz", "system_prompt": system,
            "response": response, "quiz_data": quiz_data}


# ─── Node 2c: Drill on repeated weakness ─────────────────────────────────────

def drill_node(state: TutorState) -> TutorState:
    top = state["weaknesses"][0]
    system = build_drill_prompt(
        state["profile"], top["topic"], top.get("example", "")
    )
    raw = _call_llm(system, state["history"], state["user_message"])
    quiz_data = _parse_quiz(raw)
    response = re.sub(r"\[QUIZ\].*?\[/QUIZ\]", "", raw, flags=re.DOTALL).strip()
    return {**state, "route": "drill", "system_prompt": system,
            "response": response, "quiz_data": quiz_data}


# ─── Node 2d: Strength review ────────────────────────────────────────────────

def review_node(state: TutorState) -> TutorState:
    topic = state["due_strengths"][0]["topic"]
    system = build_review_prompt(state["profile"], topic)
    raw = _call_llm(system, state["history"], state["user_message"])
    quiz_data = _parse_quiz(raw)
    response = re.sub(r"\[QUIZ\].*?\[/QUIZ\]", "", raw, flags=re.DOTALL).strip()
    return {**state, "route": "review", "system_prompt": system,
            "response": response, "quiz_data": quiz_data}


# ─── Node 3: Save + background analyze ───────────────────────────────────────

def save_and_analyze(state: TutorState) -> TutorState:
    uid = state["user_id"]
    db.save_message(uid, "user", state["user_message"])
    db.save_message(uid, "assistant", state["response"])
    threading.Thread(
        target=analyze_turn,
        args=(uid, state["user_message"], state["response"]),
        daemon=True,
    ).start()
    return state


# ─── Quiz parser ──────────────────────────────────────────────────────────────

def _parse_quiz(text: str) -> dict:
    match = re.search(r"\[QUIZ\](.*?)\[/QUIZ\]", text, re.DOTALL)
    if not match:
        return {}
    block = match.group(1).strip()
    lines = [l.strip() for l in block.splitlines() if l.strip()]

    question, options, answer_letter = "", [], ""
    for line in lines:
        if line.startswith("السؤال:"):
            question = line.removeprefix("السؤال:").strip()
        elif re.match(r"^[أبجدabcd]\)", line, re.IGNORECASE):
            options.append(line[2:].strip())
        elif line.startswith("الجواب:"):
            answer_letter = line.removeprefix("الجواب:").strip()

    if not question or len(options) < 2:
        return {}

    letter_map = {"أ": 0, "ب": 1, "ج": 2, "د": 3, "a": 0, "b": 1, "c": 2, "d": 3}
    idx = letter_map.get(answer_letter.lower(), 0)
    answer = options[idx] if idx < len(options) else options[0]
    return {"question": question, "options": options, "answer": answer}


# ─── Graph ────────────────────────────────────────────────────────────────────

def create_graph():
    g = StateGraph(TutorState)

    # Nodes
    g.add_node("load_context", load_context)
    g.add_node("chat", chat_node)
    g.add_node("quiz", quiz_node)
    g.add_node("drill", drill_node)
    g.add_node("review", review_node)
    g.add_node("save_and_analyze", save_and_analyze)

    # Entry
    g.set_entry_point("load_context")

    # Conditional branching after load_context
    g.add_conditional_edges(
        "load_context",
        router,
        {
            "chat":   "chat",
            "quiz":   "quiz",
            "drill":  "drill",
            "review": "review",
        },
    )

    # All branches converge at save_and_analyze
    for node in ["chat", "quiz", "drill", "review"]:
        g.add_edge(node, "save_and_analyze")

    g.add_edge("save_and_analyze", END)

    return g.compile()
