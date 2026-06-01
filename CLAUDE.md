# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                  # install dependencies
make oauth               # start OAuth server on :8080 (uvicorn oauth.main:app --port 8080 --reload)
make app                 # start main web app on :8001 (uvicorn app.main:app --port 8001 --reload)
basecamp-cli --help      # list all CLI commands (requires uv sync first)
```

There are no tests in this project.

## Architecture

The project has two separate FastAPI applications and a CLI tool, all sharing a single `BasecampClient`.

**OAuth flow** (`oauth/`) — a one-time setup server. Visit `http://localhost:8080/oauth/start` to authorize via 37signals Launchpad. On callback it exchanges the code for tokens, fetches the user's Basecamp account ID, and writes `ACCESS_TOKEN`, `REFRESH_TOKEN`, `ACCOUNT_ID`, and `TOKEN_EXPIRES_AT` directly into `.env` via `oauth/token_store.py`. The main app reads from `.env` at startup, so OAuth must be completed before the main app will work.

**Main web app** (`app/`) — server-side rendered UI using Jinja2 + HTMX + Tailwind (CDN). Routes in `app/routes/` return full HTML pages or HTML partials; HTMX swaps in partials for inline actions (creating todolists, creating and completing todos) without full page reloads.

**CLI** (`app/cli.py`) — Click commands that wrap `BasecampClient` for scripting. The `create-from-template` command reads a YAML/JSON file (see `template.example.yaml`) and bulk-creates a todolist with todos in one call.

**`BasecampClient`** (`app/client.py`) — async context manager wrapping `httpx.AsyncClient`. On entry it checks `TOKEN_EXPIRES_AT` and auto-refreshes the token if within 5 minutes of expiry, writing new tokens back to `.env`. All HTTP methods retry up to 3 times, handling 401 (re-auth) and 429 (rate limit via `Retry-After` header).

**Token persistence** — both `oauth/token_store.py` and `app/client.py` write token data directly to `.env` using `python-dotenv`'s `set_key`. The `.env` file is the single source of truth for all credentials and token state.

## Environment Setup

Copy `.env.example` to `.env` and fill in `CLIENT_ID`, `CLIENT_SECRET`, and `REDIRECT_URI` from your [37signals integration](https://launchpad.37signals.com/integrations). The remaining four vars (`ACCESS_TOKEN`, `REFRESH_TOKEN`, `ACCOUNT_ID`, `TOKEN_EXPIRES_AT`) are written automatically by the OAuth flow.
