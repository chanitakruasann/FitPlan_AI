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
