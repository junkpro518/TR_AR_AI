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
- `HERMES_BASE_URL` — default: `http://hermes:8642/v1`
- `HERMES_API_KEY` — local secret token for the Hermes API server
- `HERMES_MODEL` — default: `hermes-agent`
- `ALLOWED_USER_ID` — `5464178168`

## Architecture

```
User message (any free text)
  → main.py (Telegram handler)
  → Hermes API (http://hermes:8642/v1)
      → LLM via OpenRouter
```

### Key files

| File | Role |
|------|------|
| `bot/main.py` | Telegram bot + Hermes API client; handles all incoming messages |
| `bot/nodes/fetch_content.py` | Optional nlm CLI wrapper for NotebookLM queries |
| `hermes/SOUL.md` | Teacher personality / system prompt loaded by the Hermes agent |

## Deployment (VPS)

```bash
./deploy.sh root@vps-ip
```

Copies code + nlm credentials (`~/.notebooklm-mcp-cli/profiles/default/cookies.json`) + Hermes SOUL (`hermes/SOUL.md`) to VPS, builds Docker, starts container.
