from app import ai
from tests.conftest import add_clip, login


def test_programs_and_clips_in_schedule(client):
    login(client)
    hiit = add_clip(client, "hiitHIIThii")
    for wd, body in [(0, {"program": "legs"}), (1, {"program": "chest"}), (2, {"program": "legs"}),
                     (3, {"program": "back"}), (4, {"program": "core"}), (5, {"video_id": hiit})]:
        assert client.post("/api/schedule/item", json={"weekday": wd, **body}).status_code == 200
    data = client.get("/api/schedule").json()
    assert data["score"]["total"] > 0 and len(data["score"]["parts"]) == 5
    assert data["days"][0]["items"][0]["title"] == "วันฝึกขาและก้น"
    assert data["days"][0]["items"][0]["exercises"]
    assert data["days"][5]["items"][0]["intensity"] == "high"
    assert any("วันจันทร์และวันพุธ" in f["text"] for f in data["findings"])
    assert data["program_minutes"] == 30 and data["level"] == "ผู้เริ่มต้น"


def test_add_validation(client):
    login(client)
    assert client.post("/api/schedule/item", json={"weekday": 0}).status_code == 422
    assert client.post("/api/schedule/item", json={"weekday": 0, "program": "wings"}).status_code == 422
    assert client.post("/api/schedule/item", json={"weekday": 0, "program": "legs", "video_id": 1}).status_code == 422
    for _ in range(5):
        client.post("/api/schedule/item", json={"weekday": 1, "program": "core"})
    assert client.post("/api/schedule/item", json={"weekday": 1, "program": "core"}).status_code == 422


def test_remind_time(client):
    login(client)
    assert client.put("/api/schedule/day/2", json={"remind_time": "08:00"}).status_code == 422
    client.post("/api/schedule/item", json={"weekday": 2, "program": "legs"})
    assert client.put("/api/schedule/day/2", json={"remind_time": "18:30"}).status_code == 200
    assert client.put("/api/schedule/day/2", json={"remind_time": "25:00"}).status_code == 422
    assert client.get("/api/schedule").json()["days"][2]["remind_time"] == "18:30"


def test_advice(client, monkeypatch):
    login(client)
    assert client.post("/api/schedule/advice").status_code == 422
    seen = {}

    def fake(level, goal, summary):
        seen.update(level=level, goal=goal, summary=summary)
        return {"overview": "ภาพรวมดี", "suggestions": ["ข้อ 1"]}

    monkeypatch.setattr(ai, "schedule_advice", fake)
    client.post("/api/schedule/item", json={"weekday": 0, "program": "legs"})
    r = client.post("/api/schedule/advice").json()
    assert r["overview"] == "ภาพรวมดี"
    assert seen["level"] == "ผู้เริ่มต้น" and seen["goal"] == "ลดน้ำหนัก 3 กก."
    assert "คะแนนรวม" in seen["summary"] and "จันทร์: วันฝึกขาและก้น" in seen["summary"]
