import base64
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import HTTPException, status

from .config import settings
from .db import db


def verify_telegram_init_data(init_data: str) -> dict:
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Telegram hash")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", settings.telegram_bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram signature")

    user = json.loads(pairs.get("user", "{}"))
    if not user.get("id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Telegram user")
    return user


def _sign(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    body = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    signature = hmac.new(settings.session_secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def _unsign(token: str) -> dict:
    try:
        body, signature = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed session") from exc

    expected = hmac.new(settings.session_secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    padded = body + "=" * (-len(body) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
    if payload["exp"] < int(time.time()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    return payload


def create_session(user: dict) -> dict:
    telegram_id = user.get("id") or user.get("telegram_id")
    if not telegram_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Telegram user id")

    normalized_user = {**user, "id": telegram_id, "telegram_id": telegram_id}
    expires_at = int(time.time()) + settings.session_ttl_seconds
    token = _sign({"telegram_id": telegram_id, "exp": expires_at})
    with db() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO sessions (token, telegram_id, username, first_name, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (token, telegram_id, user.get("username"), user.get("first_name"), expires_at),
        )
    return {"token": token, "expires_at": expires_at, "user": normalized_user}


def get_session_user(token: str) -> dict:
    payload = _unsign(token)
    with db() as connection:
        row = connection.execute(
            "SELECT telegram_id, username, first_name, expires_at FROM sessions WHERE token = ?",
            (token,),
        ).fetchone()
    if not row or row["expires_at"] < int(time.time()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown session")
    return {**row, "telegram_id": payload["telegram_id"]}
