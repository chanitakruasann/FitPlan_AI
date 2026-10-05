import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["DEV_LOGIN"] = "1"
os.environ["CRON_SECRET"] = "test-secret"

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import ai, main, video as yt
from app.db import Base, engine
from app.routes import food, progress_api, workout

WED = date(2026, 10, 7)   # วันพุธ สัปดาห์เริ่ม 5 ต.ค. 2026

PROFILE = {
    "fitness_level": "beginner", "equipment": "none",
    "height_cm": "160", "weight_kg": "60", "age": "25", "sex": "female",
    "activity": "light", "goal": "lose_weight", "kg_change": "3",
}

HIIT = [
    {"start": "00:00", "name": "วอร์มอัป", "category": "warmup_stretch", "minutes": 3, "muscles": []},
    {"start": "03:00", "name": "กระโดดตบ", "category": "hiit", "minutes": 14, "muscles": ["calves", "shoulders"]},
    {"start": "17:00", "name": "ยืดเหยียด", "category": "cooldown", "minutes": 3, "muscles": []},
]
LEGS = [
    {"start": "00:00", "name": "สควอท (Squat)", "category": "bodyweight_moderate", "minutes": 15, "muscles": ["quads", "glutes"]},
    {"start": "15:00", "name": "ลันจ์ (Lunge)", "category": "bodyweight_moderate", "minutes": 10, "muscles": ["quads", "glutes"]},
]
CLIPS = {"hiitHIIThii": HIIT, "legsLEGSleg": LEGS}


def set_today(monkeypatch, d):
    for mod in (workout, food, progress_api):
        monkeypatch.setattr(mod, "today", lambda d=d: d)


@pytest.fixture()
def client(monkeypatch):
    Base.metadata.drop_all(engine)
    calls = []

    def fake_analyze(url, categories):
        calls.append(url)
        vid = url.rsplit("=", 1)[1]
        if vid == "notworkout1":
            raise ai.NotWorkoutError(url)
        return {"segments": CLIPS.get(vid, HIIT), "total_minutes": 20}

    monkeypatch.setattr(ai, "analyze_video", fake_analyze)
    monkeypatch.setattr(yt, "fetch_title", lambda vid: None if vid == "privateVid1" else f"คลิป {vid}")
    monkeypatch.setattr(ai, "estimate_food", lambda name: {
        "portion": "1 จาน", "kcal": 600, "protein_g": 25, "carb_g": 70, "fat_g": 22, "confidence": "medium"})
    set_today(monkeypatch, WED)
    with TestClient(main.app) as c:
        c.calls = calls
        yield c
    engine.dispose()


def login(c, name="มิว", **overrides):
    from datetime import datetime
    from app.db import SessionLocal
    from app.models import User
    c.get(f"/auth/dev-login?name={name}")
    db = SessionLocal()   # ให้วันสมัครอยู่ก่อนวันที่ใช้ทดสอบเสมอ ไม่ขึ้นกับวันที่จริง
    db.query(User).filter(User.line_user_id == f"dev-{name}").update({"created_at": datetime(2026, 9, 1)})
    db.commit(); db.close()
    return c.post("/onboarding", data={**PROFILE, **overrides}, follow_redirects=False)


def add_clip(c, vid):
    return c.post("/api/video/analyze", json={"url": f"https://youtu.be/{vid}"}).json()["id"]
