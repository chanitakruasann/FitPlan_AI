import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["DEV_LOGIN"] = "1"

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import ai, main, schedule as sched, video as yt
from app.db import Base, SessionLocal, engine
from app.models import ScheduleItem

HIIT = [  # 30 นาที: วอร์ม 5, HIIT 20, คูลดาวน์ 5
    {"start": "00:00", "name": "วอร์มอัป", "category": "warmup_stretch", "minutes": 5},
    {"start": "05:00", "name": "HIIT", "category": "hiit", "minutes": 20},
    {"start": "25:00", "name": "ยืด", "category": "cooldown", "minutes": 5},
]
STRENGTH = [  # 30 นาที บอดี้เวท ไม่มียืดเหยียด
    {"start": "00:00", "name": "Squat", "category": "bodyweight_moderate", "minutes": 30},
]
WALK = [{"start": "00:00", "name": "เดินเร็ว", "category": "low_impact_cardio", "minutes": 30}]


# ---------- ตัววิเคราะห์ ----------

def test_empty_week():
    r = sched.analyze_week([[] for _ in range(7)], 60)
    assert r["findings"][0]["level"] == "info" and r["totals"]["rest_days"] == 7


def test_who_minutes_count_vigorous_double():
    week = [[HIIT], [], [HIIT], [], [HIIT], [], []]
    r = sched.analyze_week(week, 60)
    assert r["totals"]["vigorous_min"] == 60
    assert r["totals"]["cardio_equivalent_min"] == 120
    assert any(f["level"] == "warn" and "ขาดอีกประมาณ 30" in f["text"] for f in r["findings"])


def test_good_week():
    week = [[HIIT], [STRENGTH, WALK], [], [HIIT], [STRENGTH, WALK], [WALK], []]
    r = sched.analyze_week(week, 60)
    texts = " ".join(f["text"] for f in r["findings"])
    assert r["totals"]["cardio_equivalent_min"] == 2 * 40 + 90   # 170
    assert "อยู่ในช่วง 150–300" in texts
    assert r["totals"]["strength_days"] == 2
    assert not any("ติดกัน" in f["text"] for f in r["findings"])


def test_consecutive_hard_days_wraps_sunday_to_monday():
    week = [[HIIT], [], [], [], [], [], [HIIT]]
    r = sched.analyze_week(week, 60)
    assert any("วันอาทิตย์กับวันจันทร์" in f["text"] for f in r["findings"])


def test_no_rest_and_no_stretch_warnings():
    r = sched.analyze_week([[STRENGTH]] * 7, 60)
    texts = " ".join(f["text"] for f in r["findings"])
    assert "ไม่มีวันพัก" in texts and "ไม่มีช่วงวอร์มอัป" in texts


# ---------- API ----------

@pytest.fixture()
def client(monkeypatch):
    Base.metadata.drop_all(engine)
    clips = {"hiitHIIThii": HIIT, "strengthSTR": STRENGTH}
    monkeypatch.setattr(yt, "fetch_title", lambda vid: f"คลิป {vid}")
    monkeypatch.setattr(ai, "analyze_video",
                        lambda url, c: {"segments": clips[url.rsplit("=", 1)[1]], "total_minutes": 30})
    with TestClient(main.app) as c:
        c.get("/auth/dev-login?name=มิว")
        c.post("/onboarding", data={
            "height_cm": "160", "weight_kg": "60", "age": "25", "sex": "female",
            "activity": "light", "goal": "lose", "kg_change": "3",
        })
        yield c


def add_clip(c, vid):
    return c.post("/api/video/analyze", json={"url": f"https://youtu.be/{vid}"}).json()["id"]


def test_library_and_schedule(client):
    hiit, strength = add_clip(client, "hiitHIIThii"), add_clip(client, "strengthSTR")
    data = client.get("/api/schedule").json()
    assert {v["id"] for v in data["library"]} == {hiit, strength}
    assert data["findings"][0]["level"] == "info"

    for wd, vid in [(0, hiit), (1, strength), (3, strength)]:
        assert client.post("/api/schedule/item", json={"weekday": wd, "video_id": vid}).status_code == 200
    data = client.get("/api/schedule").json()
    assert data["days"][0]["items"][0]["title"] == "คลิป hiitHIIThii"
    assert data["days"][0]["remind_time"] == "07:00"
    assert data["totals"]["strength_days"] == 2
    assert data["days"][0]["stats"]["is_hard"] is True

    # ตั้งเวลาเตือนรายวัน
    assert client.put("/api/schedule/day/1", json={"remind_time": "18:30"}).status_code == 200
    assert client.get("/api/schedule").json()["days"][1]["remind_time"] == "18:30"
    assert client.put("/api/schedule/day/1", json={"remind_time": "25:00"}).status_code == 422
    assert client.put("/api/schedule/day/2", json={"remind_time": "08:00"}).status_code == 422  # วันว่าง

    # เอาออก
    item_id = data["days"][3]["items"][0]["id"]
    client.delete(f"/api/schedule/item/{item_id}")
    assert client.get("/api/schedule").json()["totals"]["strength_days"] == 1


def test_max_items_per_day(client):
    vid = add_clip(client, "hiitHIIThii")
    for _ in range(main.MAX_ITEMS_PER_DAY):
        client.post("/api/schedule/item", json={"weekday": 2, "video_id": vid})
    assert client.post("/api/schedule/item", json={"weekday": 2, "video_id": vid}).status_code == 422


def test_today_planned_and_done(client):
    vid = add_clip(client, "hiitHIIThii")
    today = datetime.now(main.TZ).weekday()
    client.post("/api/schedule/item", json={"weekday": today, "video_id": vid})
    planned = client.get("/api/today").json()["planned"]
    assert len(planned) == 1 and planned[0]["done"] is False
    client.post("/api/workout/log", json={"video_id": vid, "portion": 1})
    assert client.get("/api/today").json()["planned"][0]["done"] is True


def test_added_today_with_passed_time_is_not_sent_backwards(client):
    vid = add_clip(client, "hiitHIIThii")
    now = datetime.now(main.TZ)
    client.post("/api/schedule/item", json={"weekday": now.weekday(), "video_id": vid})
    client.put(f"/api/schedule/day/{now.weekday()}", json={"remind_time": "00:00"})
    db = SessionLocal()
    it = db.query(ScheduleItem).one()
    assert it.last_sent_date == now.date()
    db.close()


def test_advice(client, monkeypatch):
    assert client.post("/api/schedule/advice").status_code == 422   # ตารางว่าง
    captured = {}

    def fake(goal, summary):
        captured.update(goal=goal, summary=summary)
        return ["ลองเพิ่มวันเวทอีก 1 วัน"]

    monkeypatch.setattr(ai, "schedule_advice", fake)
    vid = add_clip(client, "hiitHIIThii")
    client.post("/api/schedule/item", json={"weekday": 0, "video_id": vid})
    r = client.post("/api/schedule/advice").json()
    assert r["suggestions"] == ["ลองเพิ่มวันเวทอีก 1 วัน"]
    assert captured["goal"] == "ลดน้ำหนัก 3 กก."
    assert "จันทร์: คลิป hiitHIIThii" in captured["summary"] and "อังคาร: วันพัก" in captured["summary"]


def test_cannot_edit_other_users_schedule(client):
    vid = add_clip(client, "hiitHIIThii")
    item_id = client.post("/api/schedule/item", json={"weekday": 0, "video_id": vid}).json()["id"]
    client.get("/logout")
    client.get("/auth/dev-login?name=บอส")
    client.post("/onboarding", data={"height_cm": "175", "weight_kg": "70", "age": "30", "sex": "male",
                                     "activity": "moderate", "goal": "maintain"})
    assert client.delete(f"/api/schedule/item/{item_id}").status_code == 404
    assert client.get("/api/schedule").json()["library"] == []
