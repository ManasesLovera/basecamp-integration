from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import dotenv_values, set_key

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def read_env() -> dict[str, str]:
    return {k: v for k, v in dotenv_values(ENV_PATH).items() if v is not None}


def save_tokens(access_token: str, refresh_token: str, expires_in: int, account_id: str) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    for key, value in {
        "ACCESS_TOKEN": access_token,
        "REFRESH_TOKEN": refresh_token,
        "ACCOUNT_ID": str(account_id),
        "TOKEN_EXPIRES_AT": expires_at.isoformat(),
    }.items():
        set_key(str(ENV_PATH), key, value)
