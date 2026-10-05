import requests

from . import config

PUSH_URL = "https://api.line.me/v2/bot/message/push"


def send_line(user_id: str, text: str) -> None:
    r = requests.post(
        PUSH_URL,
        headers={"Authorization": f"Bearer {config.LINE_MESSAGING_TOKEN}"},
        json={"to": user_id, "messages": [{"type": "text", "text": text[:5000]}]},
        timeout=15,
    )
    r.raise_for_status()
