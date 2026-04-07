# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Turkish language learning Telegram bot. The user talks naturally — the bot responds as a human teacher, detects weaknesses/strengths from conversation context, and adapts its teaching plan dynamically. No command-based interface.

## Development Commands

```bash
cd bot
source .venv/bin/activate
uv pip install -r requirements.txt
python main.py
```

## Environment Setup

Copy `bot/.env.example` to `bot/.env` and fill:
- `TELEGRAM_TOKEN` — from @BotFather
- `OPENROUTER_API_KEY` — from openrouter.ai
- `OPENROUTER_MODEL` — default: `openai/gpt-oss-120b`
- `NOTEBOOK_ID` — `bdf8dd30-292a-4cea-abb4-d88fc25beba8`
- `ALLOWED_USER_ID` — `5464178168`

## Architecture

```
User message (any free text)
  → main.py (single MessageHandler)
  → graph.py (LangGraph, 4 nodes)
      1. load_context   → SQLite: profile + last 20 msgs + weaknesses + due strengths
      2. build_prompt   → dynamic system prompt + optional nlm query
      3. respond        → LLM via OpenRouter → parse [QUIZ] blocks
      4. save_and_analyze → save to DB + background thread → analyzer.py
```

### Key files

| File | Role |
|------|------|
| `bot/main.py` | Two handlers only: `/start`, `/stats`, free text → graph |
| `bot/graph.py` | LangGraph 4-node pipeline, TutorState TypedDict |
| `bot/db.py` | SQLite schema + CRUD (profile, messages, weaknesses, strengths, vocab_srs) |
| `bot/prompts.py` | `build_system_prompt()` — rebuilds every message from DB state |
| `bot/analyzer.py` | Background LLM call → extracts weaknesses/strengths/vocab → updates DB |
| `bot/nodes/fetch_content.py` | Optional nlm CLI wrapper for NotebookLM queries |

### Database (`tutor.db`)

5 tables: `profile`, `messages`, `weaknesses`, `strengths`, `vocab_srs`

Weakness detection: analyzer runs after every response in a daemon thread.
Strength review: `get_due_strengths()` checks `review_due <= today`.
Quiz trigger: every 7 messages (`message_count % 7 == 0`) in `prompts.py`.

### Quiz flow

LLM embeds `[QUIZ]...[/QUIZ]` block in response → `graph.py:_parse_quiz()` extracts it → `main.py` sends inline keyboard with `callback_data="q:{option}:{answer}"` → `handle_quiz_callback` splits on `":"` with maxsplit=2.

## Deployment (VPS)

```bash
./deploy.sh root@vps-ip
```

Copies code + nlm credentials (`~/.notebooklm-mcp-cli/profiles/default/cookies.json`) to VPS, builds Docker, starts container. `tutor.db` persists via `db-data` Docker volume.
