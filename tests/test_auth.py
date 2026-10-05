from datetime import datetime

import sqlalchemy as sa

from app import auth_line, migrate, passwords
from app.db import SessionLocal
from app.models import User
from tests.conftest import PROFILE


def register(c, username="mew_fit", password="secret123", password2=None):
    return c.post("/auth/register", data={"username": username, "password": password,
                                          "password2": password2 or password}, follow_redirects=False)


def test_password_hashing():
    h = passwords.hash_password("secret123")
    assert h.startswith("pbkdf2_sha256$") and "secret123" not in h
    assert passwords.verify_password("secret123", h)
    assert not passwords.verify_password("wrong", h)
    assert not passwords.verify_password("x", None)


def test_login_page_offers_both(client):
    page = client.get("/login").text
    assert "เข้าสู่ระบบด้วย LINE" in page and 'action="/auth/login"' in page
    assert 'action="/auth/register"' in client.get("/login?mode=register").text


def test_register_then_onboarding(client):
    r = register(client)
    assert r.status_code == 303
    assert client.get("/", follow_redirects=False).headers["location"] == "/onboarding"
    assert client.post("/onboarding", data=PROFILE, follow_redirects=False).status_code == 303
    assert client.get("/api/today").status_code == 200


def test_register_validation(client):
    assert register(client, username="ab").status_code == 422
    assert register(client, username="มี เว้นวรรค").status_code == 422
    assert register(client, password="123").status_code == 422
    r = register(client, password="secret123", password2="other123")
    assert r.status_code == 422 and "ไม่ตรงกัน" in r.text
    assert register(client, username="มิวฟิต").status_code == 303          # ภาษาไทยได้
    client.get("/logout")
    r = register(client, username="มิวฟิต")
    assert r.status_code == 422 and "มีคนใช้แล้ว" in r.text


def test_username_is_case_insensitive(client):
    register(client, username="MewFit")
    client.get("/logout")
    assert register(client, username="mewfit").status_code == 422
    r = client.post("/auth/login", data={"username": "MEWFIT", "password": "secret123"}, follow_redirects=False)
    assert r.status_code == 303


def test_wrong_password_and_lockout(client):
    register(client)
    client.get("/logout")
    for _ in range(passwords.MAX_FAILED):
        r = client.post("/auth/login", data={"username": "mew_fit", "password": "nope"})
        assert r.status_code == 401
    r = client.post("/auth/login", data={"username": "mew_fit", "password": "secret123"})
    assert r.status_code == 429 and "ลองใหม่ในอีก" in r.text   # ล็อกแม้รหัสถูก
    db = SessionLocal(); db.query(User).update({"locked_until": None}); db.commit(); db.close()
    assert client.post("/auth/login", data={"username": "mew_fit", "password": "secret123"},
                       follow_redirects=False).status_code == 303


def test_unknown_user_same_message(client):
    r = client.post("/auth/login", data={"username": "ghost", "password": "whatever"})
    assert r.status_code == 401 and "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง" in r.text


def _fake_line(monkeypatch, sub):
    monkeypatch.setattr(auth_line, "exchange_code", lambda code: {"id_token": "t"})
    monkeypatch.setattr(auth_line, "verify_id_token", lambda tok, nonce: {"sub": sub, "name": "LINE User"})


def _run_line(c, link=False):
    r = c.get(f"/auth/line/login{'?link=1' if link else ''}", follow_redirects=False)
    from urllib.parse import parse_qs, urlparse
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    return c.get(f"/auth/line/callback?code=abc&state={state}", follow_redirects=False)


def test_link_line_to_password_account(client, monkeypatch):
    register(client)
    client.post("/onboarding", data=PROFILE)
    page = client.get("/onboarding").text
    assert "ยังไม่ได้เชื่อม" in page and "/auth/line/login?link=1" in page
    _fake_line(monkeypatch, "U999")
    r = _run_line(client, link=True)
    assert r.headers["location"] == "/onboarding?linked=1"
    assert "เชื่อมแล้ว" in client.get("/onboarding").text
    # ออกจากระบบแล้วเข้าด้วย LINE ได้บัญชีเดิม
    client.get("/logout")
    r = _run_line(client)
    assert r.status_code == 303 and client.get("/api/today").status_code == 200
    db = SessionLocal(); assert db.query(User).count() == 1; db.close()


def test_cannot_link_line_used_by_someone_else(client, monkeypatch):
    _fake_line(monkeypatch, "U111")
    _run_line(client)                       # มีคนเข้าด้วย LINE นี้แล้ว
    client.get("/logout")
    register(client)
    r = _run_line(client, link=True)
    assert r.headers["location"] == "/onboarding?link_error=taken"


def test_migration_from_old_schema(tmp_path):
    """ฐานข้อมูลรุ่นแรก: line_user_id เป็น NOT NULL และยังไม่มีคอลัมน์ใหม่"""
    eng = sa.create_engine(f"sqlite:///{tmp_path}/old.db")
    with eng.begin() as c:
        c.exec_driver_sql("""CREATE TABLE users (id INTEGER PRIMARY KEY, line_user_id VARCHAR(64) NOT NULL,
            display_name VARCHAR(100) NOT NULL, picture_url VARCHAR(500), height_cm FLOAT, weight_kg FLOAT, age INTEGER,
            sex VARCHAR(10), activity VARCHAR(20), goal VARCHAR(10), kg_change FLOAT, daily_kcal_target INTEGER,
            created_at DATETIME)""")
        c.exec_driver_sql("CREATE UNIQUE INDEX ix_users_line_user_id ON users (line_user_id)")
        c.exec_driver_sql("""CREATE TABLE food_logs (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id),
            food_id INTEGER, name VARCHAR(100), servings FLOAT, kcal INTEGER, eaten_on DATE, created_at DATETIME)""")
        c.exec_driver_sql("INSERT INTO users (id, line_user_id, display_name, goal, created_at) "
                          "VALUES (1, 'Uold', 'เก่า', 'lose', '2026-09-01')")
        c.exec_driver_sql("INSERT INTO food_logs (id, user_id, name, servings, kcal, eaten_on) "
                          "VALUES (1, 1, 'ข้าว', 1, 300, '2026-09-02')")
    migrate.run(eng)
    insp = sa.inspect(eng)
    cols = {c["name"]: c for c in insp.get_columns("users")}
    assert cols["line_user_id"]["nullable"] and "password_hash" in cols and "fitness_level" in cols
    with eng.begin() as c:
        assert c.exec_driver_sql("SELECT goal FROM users WHERE id=1").scalar() == "lose_weight"
        c.exec_driver_sql("INSERT INTO users (display_name, username, username_key, failed_logins) "
                          "VALUES ('ใหม่', 'new', 'new', 0)")   # ไม่มี LINE ได้แล้ว
        fk = c.exec_driver_sql("PRAGMA foreign_key_list(food_logs)").fetchall()
        assert fk[0][2] == "users"   # foreign key ยังชี้ตาราง users
        assert c.exec_driver_sql("SELECT kcal FROM food_logs").scalar() == 300
    migrate.run(eng)   # รันซ้ำได้ไม่พัง
    eng.dispose()
