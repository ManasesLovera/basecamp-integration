import os
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from oauth.token_store import save_tokens

load_dotenv()

app = FastAPI(title="Basecamp OAuth Server")

LAUNCHPAD_AUTH_URL = "https://launchpad.37signals.com/authorization/new"
LAUNCHPAD_TOKEN_URL = "https://launchpad.37signals.com/authorization/token"
LAUNCHPAD_INFO_URL = "https://launchpad.37signals.com/authorization.json"


@app.get("/oauth/start")
def oauth_start():
    client_id = os.getenv("CLIENT_ID")
    redirect_uri = os.getenv("REDIRECT_URI")
    if not client_id or not redirect_uri:
        raise HTTPException(500, "CLIENT_ID and REDIRECT_URI must be set in .env")

    params = urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
    })
    return RedirectResponse(f"{LAUNCHPAD_AUTH_URL}?{params}")


@app.get("/oauth/callback")
async def oauth_callback(request: Request, code: str | None = None, error: str | None = None):
    if error or not code:
        raise HTTPException(400, f"Authorization failed: {error or 'no code received'}")

    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    redirect_uri = os.getenv("REDIRECT_URI")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            LAUNCHPAD_TOKEN_URL,
            params={
                "type": "web_server",
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        token_resp.raise_for_status()
        tokens = token_resp.json()

        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        expires_in = tokens.get("expires_in", 1209600)

        info_resp = await client.get(
            LAUNCHPAD_INFO_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "Basecamp Integration (contact@example.com)",
            },
        )
        info_resp.raise_for_status()
        info = info_resp.json()

    bc3_accounts = [a for a in info.get("accounts", []) if a.get("product") == "bc3"]
    if not bc3_accounts:
        raise HTTPException(400, "No Basecamp 4 account found on this user's profile.")

    account_id = bc3_accounts[0]["id"]
    account_name = bc3_accounts[0]["name"]

    save_tokens(access_token, refresh_token, expires_in, account_id)

    return HTMLResponse(f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Authorized — Basecamp</title>
  <style>
    body {{ font-family: system-ui, sans-serif; display: flex; align-items: center;
           justify-content: center; height: 100vh; margin: 0; background: #f5f5f5; }}
    .card {{ background: white; border-radius: 12px; padding: 2.5rem 3rem;
             box-shadow: 0 2px 16px rgba(0,0,0,.1); text-align: center; max-width: 400px; }}
    h1 {{ color: #1db954; margin-top: 0; }}
    p {{ color: #555; line-height: 1.6; }}
    code {{ background: #f0f0f0; padding: 2px 6px; border-radius: 4px; font-size: .9em; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>&#10003; Authorized!</h1>
    <p>Connected to <strong>{account_name}</strong> (account&nbsp;ID:&nbsp;<code>{account_id}</code>).</p>
    <p>Tokens saved to <code>.env</code>. You can close this window and start the main app:</p>
    <pre style="background:#f0f0f0;padding:1rem;border-radius:8px;text-align:left">uvicorn app.main:app --port 8001</pre>
  </div>
</body>
</html>
""")
