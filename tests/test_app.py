from tests.conftest import PROFILE, login


def test_redirects_and_onboarding(client):
    r = client.get("/", follow_redirects=False)
    assert r.headers["location"] == "/login"
    client.get("/auth/dev-login?name=มิว", follow_redirects=False)
    assert client.get("/", follow_redirects=False).headers["location"] == "/onboarding"
    page = client.get("/onboarding").text
    assert "ระดับไหน" in page and "ผู้เริ่มต้น" in page and "อุปกรณ์" in page


def test_onboarding_requires_level(client):
    client.get("/auth/dev-login?name=มิว")
    r = client.post("/onboarding", data={**PROFILE, "fitness_level": ""})
    assert r.status_code == 422 and "ระดับการออกกำลังกาย" in r.text


def test_old_user_without_level_is_sent_back_to_onboarding(client):
    from app.db import SessionLocal
    from app.models import User
    login(client)
    db = SessionLocal()
    u = db.query(User).one(); u.fitness_level = None; db.commit(); db.close()
    assert client.get("/", follow_redirects=False).headers["location"] == "/onboarding"
    assert client.get("/api/today").status_code == 409


def test_goals_without_kg(client):
    for goal in ("strength", "fitness", "maintain", "build_muscle"):
        r = login(client, name=goal, goal=goal, kg_change="")
        assert r.status_code == 303, goal


def test_pages_render(client):
    login(client)
    for path, text in [("/", "เหลือกินได้อีก"), ("/schedule", "ตารางออกกำลังกาย"),
                       ("/progress", "ความก้าวหน้า"), ("/onboarding", "ข้อมูลของฉัน")]:
        r = client.get(path)
        assert r.status_code == 200 and text in r.text, path


def test_food_flow(client):
    login(client)
    food = client.post("/api/food/estimate", json={"name": "ข้าวมันไก่"}).json()
    client.post("/api/food/estimate", json={"name": "  ข้าวมันไก่ "})   # แคช
    client.post("/api/food/log", json={"food_id": food["id"], "servings": 1.5})
    client.post("/api/food/log", json={"name": "ชาไทย", "servings": 1, "kcal_per_serving": 250})
    t = client.get("/api/today").json()
    assert t["eaten"] == 1150 and t["remaining"] == t["target"] - 1150
    client.delete(f"/api/food/log/{t['logs'][1]['id']}")
    assert client.get("/api/today").json()["eaten"] == 900


def test_cannot_touch_other_users_data(client):
    login(client)
    log_id = client.post("/api/food/log", json={"name": "ส้มตำ", "servings": 1, "kcal_per_serving": 150}).json()["id"]
    item = client.post("/api/schedule/item", json={"weekday": 0, "program": "legs"}).json()["id"]
    client.get("/logout")
    login(client, name="บอส")
    assert client.delete(f"/api/food/log/{log_id}").status_code == 404
    assert client.delete(f"/api/schedule/item/{item}").status_code == 404
