"""Query NotebookLM via nlm CLI and return cited content."""
import json
import os
import subprocess


NOTEBOOK_ID = os.getenv("NOTEBOOK_ID", "")
NLM_PATH = os.getenv("NLM_PATH", "nlm")


def query_notebook(question: str, conversation_id: str | None = None) -> dict:
    cmd = [NLM_PATH, "notebook", "query", NOTEBOOK_ID, question, "--json"]
    if conversation_id:
        cmd += ["--conversation-id", conversation_id]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        pass
    return {"answer": "", "sources": []}


def create_quiz_from_notebook(topic: str, count: int = 4, difficulty: int = 1) -> str:
    cmd = [
        NLM_PATH, "quiz", "create", NOTEBOOK_ID,
        "--focus", topic,
        "--count", str(count),
        "--difficulty", str(difficulty),
        "--confirm",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""
