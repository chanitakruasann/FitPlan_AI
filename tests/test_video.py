import pytest

from app import ai, video as yt
from tests.conftest import add_clip, login

VID = "dQw4w9WgXcQ"


@pytest.mark.parametrize("url", [
    f"https://www.youtube.com/watch?v={VID}", f"https://youtu.be/{VID}?si=x", f"youtu.be/{VID}",
    f"https://m.youtube.com/watch?v={VID}&t=3", f"https://www.youtube.com/shorts/{VID}",
])
def test_extract_video_id(url):
    assert yt.extract_video_id(url) == VID


def test_intensity_levels():
    assert yt.intensity_of([{"category": "yoga", "minutes": 20}]) == "low"
    assert yt.intensity_of([{"category": "warmup_stretch", "minutes": 5},
                            {"category": "bodyweight_moderate", "minutes": 20}]) == "moderate"
    assert yt.intensity_of([{"category": "warmup_stretch", "minutes": 5},
                            {"category": "hiit", "minutes": 12}]) == "high"


def test_analyze_returns_intensity_and_muscles(client):
    login(client)
    v = client.post("/api/video/analyze", json={"url": "https://youtu.be/legsLEGSleg"}).json()
    assert v["intensity"] == "moderate"
    assert v["muscle_text"] == "ส่วนล่าง (ต้นขาหน้า, ก้น)"
    assert v["segments"][0]["muscle_text"] == "ต้นขาหน้า, ก้น"
    client.post("/api/video/analyze", json={"url": f"https://www.youtube.com/watch?v=legsLEGSleg"})
    assert len(client.calls) == 1   # ใช้แคช


def test_old_analysis_is_refreshed(client):
    from app.db import SessionLocal
    from app.models import Video
    login(client)
    vid = add_clip(client, "hiitHIIThii")
    db = SessionLocal(); v = db.get(Video, vid); v.version = 1; db.commit(); db.close()
    client.post("/api/video/analyze", json={"url": "https://youtu.be/hiitHIIThii"})
    assert len(client.calls) == 2


def test_error_messages(client):
    login(client)
    assert client.post("/api/video/analyze", json={"url": "https://vimeo.com/123"}).status_code == 422
    assert client.post("/api/video/analyze", json={"url": "https://youtu.be/privateVid1"}).status_code == 422
    assert client.post("/api/video/analyze", json={"url": "https://youtu.be/notworkout1"}).status_code == 422


def test_ai_sanitizes_muscles(monkeypatch):
    monkeypatch.setattr(ai, "_gemini_json", lambda *a, **k: {"is_workout": True, "total_minutes": 10, "segments": [
        {"start": "0:00", "name": "Squat", "category": "made_up", "minutes": 5, "muscles": ["quads", "wings", "quads"]},
        {"start": "5:00", "name": "พัก", "category": "rest", "minutes": 5, "muscles": ["abs"]}]})
    r = ai.analyze_video("u", yt.CATEGORIES)
    assert r["segments"][0]["category"] == "bodyweight_moderate" and r["segments"][0]["muscles"] == ["quads"]
    assert r["segments"][1]["muscles"] == []
