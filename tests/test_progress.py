from datetime import timedelta

from app import ai
from tests.conftest import WED, login, set_today


def test_checkin_updates_weight_and_target(client):
    login(client)
    before = client.get("/api/today").json()["target"]
    r = client.post("/api/checkin", json={"weight_kg": 58.5, "waist_cm": 70}).json()
    assert r["daily_kcal_target"] < before
    p = client.get("/api/progress").json()
    assert p["this_week"]["weight_kg"] == 58.5 and p["this_week"]["waist_cm"] == 70
    assert len(p["weeks"]) == 8 and p["current_weight"] == 58.5
    client.post("/api/checkin", json={"weight_kg": 58.0})   # สัปดาห์เดียวกัน = แก้ค่าเดิม
    assert client.get("/api/progress").json()["this_week"]["weight_kg"] == 58.0


def test_weekly_metrics(client, monkeypatch):
    login(client)
    client.post("/api/schedule/item", json={"weekday": 0, "program": "legs"})
    client.post("/api/schedule/item", json={"weekday": 2, "program": "chest"})
    client.post("/api/schedule/item", json={"weekday": 4, "program": "back"})
    set_today(monkeypatch, WED - timedelta(days=2))
    client.post("/api/day/complete", json={"day": "today"})
    set_today(monkeypatch, WED)
    client.post("/api/day/skip", json={"day": "today"})
    w = client.get("/api/progress").json()["this_week"]
    assert w["planned_days"] == 3 and w["done_planned_days"] == 1
    assert w["adherence"] == 50   # ถึงกำหนดแล้ว 2 วัน ทำ 1
    assert w["kcal"] > 0 and w["minutes"] > 0 and w["exercise_days"] == 1


def test_insight_needs_two_weeks(client, monkeypatch):
    login(client)
    client.post("/api/checkin", json={"weight_kg": 60})
    assert client.post("/api/progress/insight").status_code == 422
    set_today(monkeypatch, WED + timedelta(days=7))
    client.post("/api/checkin", json={"weight_kg": 59.4})
    seen = {}
    monkeypatch.setattr(ai, "progress_insight",
                        lambda level, goal, summary: seen.update(s=summary) or {"overview": "ดีขึ้น", "suggestions": ["ยังไม่ต้องปรับ"]})
    r = client.post("/api/progress/insight").json()
    assert r["suggestions"] == ["ยังไม่ต้องปรับ"]
    assert "60.0" in seen["s"] and "59.4" in seen["s"]


def test_weeks_before_signup_are_not_counted(client):
    from datetime import datetime
    from app.db import SessionLocal
    from app.models import User
    login(client)
    client.post("/api/schedule/item", json={"weekday": 0, "program": "legs"})
    db = SessionLocal(); db.query(User).update({"created_at": datetime(2026, 10, 6, 3)}); db.commit(); db.close()
    weeks = client.get("/api/progress").json()["weeks"]
    assert all(w["planned_days"] == 0 for w in weeks)   # จันทร์ 5 ต.ค. อยู่ก่อนวันสมัคร
