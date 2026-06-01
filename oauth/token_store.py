import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

TOKENS_PATH = Path(__file__).resolve().parent.parent / "tokens.json"


def save_tokens(access_token: str, refresh_token: str, expires_in: int, account_id: str) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    TOKENS_PATH.write_text(json.dumps({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "account_id": str(account_id),
        "token_expires_at": expires_at.isoformat(),
    }, indent=2))


def load_tokens() -> dict:
    if not TOKENS_PATH.exists():
        return {}
    return json.loads(TOKENS_PATH.read_text())
