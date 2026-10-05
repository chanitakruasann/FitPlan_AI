from datetime import datetime

from app.db import SessionLocal
from app.deps import TZ
from app.models import ScheduleItem, User
from app.routes import cron
from tests.conftest import login


def test_cron_requires_secret(client):
    assert client.post("/cron/remind").status_code == 401


def test_cron_sends_once_per_user_per_day(client, monkeypatch):
    sent = []
    monkeypatch.setattr(cron.line_msg, "send_line", lambda uid, text: sent.append((uid, text)))
    login(client)
    db = SessionLocal()
    user = db.query(User).one(); user.line_user_id = "U123"
    wd = datetime.now(TZ).weekday()
    db.add_all([ScheduleItem(user_id=user.id, weekday=wd, remind_time="00:00", program="legs"),
                ScheduleItem(user_id=user.id, weekday=wd, remind_time="00:00", program="core")])
    db.commit(); db.close()
    h = {"X-Cron-Secret": "test-secret"}
    assert client.post("/cron/remind", headers=h).json() == {"sent": 1, "failed": 0}
    assert "วันฝึกขาและก้น" in sent[0][1] and "เซต" in sent[0][1] and "วันฝึกหน้าท้อง" in sent[0][1]
    assert client.post("/cron/remind", headers=h).json() == {"sent": 0, "failed": 0}


def test_cron_skips_users_without_line(client, monkeypatch):
    sent = []
    monkeypatch.setattr(cron.line_msg, "send_line", lambda uid, text: sent.append(uid))
    client.post("/auth/register", data={"username": "noline", "password": "secret123", "password2": "secret123"})
    from tests.conftest import PROFILE
    client.post("/onboarding", data=PROFILE)
    wd = datetime.now(TZ).weekday()
    client.post("/api/schedule/item", json={"weekday": wd, "program": "legs"})
    client.put(f"/api/schedule/day/{wd}", json={"remind_time": "00:00"})
    r = client.post("/cron/remind", headers={"X-Cron-Secret": "test-secret"}).json()
    assert r == {"sent": 0, "failed": 0} and sent == []
    assert client.get("/api/schedule").json()["line_linked"] is False
