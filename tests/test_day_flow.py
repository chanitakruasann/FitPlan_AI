from datetime import timedelta

from tests.conftest import WED, add_clip, login, set_today


def plan_week(c):
    hiit = add_clip(c, "hiitHIIThii")
    c.post("/api/schedule/item", json={"weekday": 0, "program": "legs"})
    c.post("/api/schedule/item", json={"weekday": 2, "program": "chest"})    # พุธ = วันนี้
    c.post("/api/schedule/item", json={"weekday": 4, "video_id": hiit})
    return hiit


def test_today_dashboard(client):
    login(client)
    plan_week(client)
    t = client.get("/api/today").json()
    p = t["plan"]
    assert t["day_name"] == "พุธ" and p["status"] is None
    assert p["sessions"][0]["title"] == "วันฝึกอก" and p["sessions"][0]["exercises"][0]["sets"] >= 2
    assert p["minutes"] > 0 and p["kcal"] > 0 and p["intensity"] in ("low", "moderate", "high")
    assert "Upper Body" in p["groups"]
    assert t["pending"] is None   # อังคารไม่มีแผน


def test_complete_logs_burn_and_undo(client):
    login(client)
    plan_week(client)
    r = client.post("/api/day/complete", json={"day": "today"}).json()
    t = client.get("/api/today").json()
    assert t["plan"]["status"] == "done" and t["burned"] == r["kcal"] > 0
    assert t["workouts"] == []   # log ของแผนไม่ซ้ำในรายการ
    client.post("/api/day/complete", json={"day": "today"})   # กดซ้ำไม่บวกซ้ำ
    assert client.get("/api/today").json()["burned"] == r["kcal"]
    client.post("/api/day/undo", json={"day": "today"})
    t = client.get("/api/today").json()
    assert t["plan"]["status"] is None and t["burned"] == 0


def test_skip_proposes_and_applies_reschedule(client):
    login(client)
    plan_week(client)
    p = client.post("/api/day/skip", json={"day": "today"}).json()
    assert p["skipped_name"] == "พุธ"
    assert all(o["day"] > 2 for o in p["options"])
    assert p["best"] is not None and "ระบบเสนอย้าย" in p["message"]
    to = p["best"]["day"]
    assert client.post("/api/reschedule/apply", json={"from_day": "today", "to_weekday": to}).status_code == 200

    # ตารางหลักไม่เปลี่ยน แต่สัปดาห์นี้ย้ายแล้ว
    assert client.get("/api/schedule").json()["days"][2]["items"]
    assert client.get("/api/today").json()["plan"] is None


def test_cannot_move_into_the_past(client):
    login(client)
    plan_week(client)
    client.post("/api/day/skip", json={"day": "today"})
    assert client.post("/api/reschedule/apply", json={"from_day": "today", "to_weekday": 1}).status_code == 422
    assert client.post("/api/reschedule/apply", json={"from_day": "today", "to_weekday": 2}).status_code == 422


def test_pending_yesterday_and_skip_into_today(client, monkeypatch):
    login(client)
    client.post("/api/schedule/item", json={"weekday": 1, "program": "legs"})   # อังคาร
    t = client.get("/api/today").json()
    assert t["pending"]["day_name"] == "อังคาร"
    p = client.post("/api/day/skip", json={"day": "yesterday"}).json()
    assert any(o["day"] == 2 for o in p["options"])   # วันนี้ (พุธ) เป็นทางเลือกได้
    assert client.get("/api/today").json()["pending"] is None


def test_streak(client, monkeypatch):
    login(client)
    plan_week(client)   # จันทร์ขา, พุธอก
    set_today(monkeypatch, WED - timedelta(days=2))   # จันทร์
    client.post("/api/day/complete", json={"day": "today"})
    set_today(monkeypatch, WED)
    assert client.get("/api/today").json()["streak"] == 2   # จันทร์ทำ + อังคารพัก
    client.post("/api/day/complete", json={"day": "today"})
    assert client.get("/api/today").json()["streak"] == 3


def test_generator_and_recovery_warning(client, monkeypatch):
    login(client)
    w = client.post("/api/workout/generate", json={"target": "legs"}).json()
    assert w["title"] == "วันฝึกขาและก้น" and w["exercises"] and w["warnings"] == []
    assert all(e["sets"] and (e["reps"] or e["seconds"]) and e["cue"] for e in w["exercises"])
    client.post("/api/workout/log-program", json={"target": "legs"})
    set_today(monkeypatch, WED + timedelta(days=1))
    w2 = client.post("/api/workout/generate", json={"target": "legs"}).json()
    assert w2["warnings"] and "เมื่อวาน" in w2["warnings"][0]
    assert client.post("/api/workout/generate", json={"target": "chest"}).json()["warnings"] == []
    assert client.post("/api/workout/generate", json={"target": "wings"}).status_code == 422
