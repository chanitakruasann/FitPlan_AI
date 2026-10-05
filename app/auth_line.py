"""LINE Login (OAuth 2.0 + OpenID Connect)"""
from urllib.parse import urlencode

import requests

from . import config

AUTH_URL = "https://access.line.me/oauth2/v2.1/authorize"
TOKEN_URL = "https://api.line.me/oauth2/v2.1/token"
VERIFY_URL = "https://api.line.me/oauth2/v2.1/verify"


def redirect_uri() -> str:
    return f"{config.BASE_URL}/auth/line/callback"


def build_login_url(state: str, nonce: str) -> str:
    params = {
        "response_type": "code",
        "client_id": config.LINE_LOGIN_CHANNEL_ID,
        "redirect_uri": redirect_uri(),
        "state": state,
        "scope": "profile openid",
        "nonce": nonce,
        # ชวนผู้ใช้แอด Official Account เป็นเพื่อนตอน login (ต้อง link OA ไว้ใน LINE Login channel)
        "bot_prompt": "aggressive",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def exchange_code(code: str) -> dict:
    r = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri(),
        "client_id": config.LINE_LOGIN_CHANNEL_ID,
        "client_secret": config.LINE_LOGIN_CHANNEL_SECRET,
    }, timeout=15)
    r.raise_for_status()
    return r.json()


def verify_id_token(id_token: str, nonce: str | None) -> dict:
    """คืนค่า sub (= LINE userId), name, picture"""
    payload = {"id_token": id_token, "client_id": config.LINE_LOGIN_CHANNEL_ID}
    if nonce:
        payload["nonce"] = nonce
    r = requests.post(VERIFY_URL, data=payload, timeout=15)
    r.raise_for_status()
    return r.json()
