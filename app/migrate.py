"""อัปเดตโครงฐานข้อมูลเดิมให้ตรงกับโมเดลใหม่ (เพิ่มคอลัมน์ที่ขาด + แปลงค่าเก่า)

create_all สร้างได้แค่ตารางใหม่ ไม่แก้ตารางที่มีอยู่แล้ว ไฟล์นี้จึงเติมให้
ถ้าโปรเจกต์โตขึ้นควรเปลี่ยนไปใช้ Alembic
"""
from sqlalchemy import inspect, text

NEW_COLUMNS = {
    "users": {
        "fitness_level": "VARCHAR(20)", "equipment": "VARCHAR(20)",
        "username": "VARCHAR(30)", "username_key": "VARCHAR(30)", "password_hash": "VARCHAR(200)",
        "failed_logins": "INTEGER DEFAULT 0", "locked_until": "TIMESTAMP",
    },
    "videos": {"version": "INTEGER DEFAULT 1"},
    "schedule_items": {"program": "VARCHAR(20)", "program_minutes": "INTEGER"},
    "workout_logs": {"title": "VARCHAR(300)", "minutes": "FLOAT", "muscles": "JSON", "source": "VARCHAR(10)"},
}


def _line_id_required(insp) -> bool:
    col = next((c for c in insp.get_columns("users") if c["name"] == "line_user_id"), None)
    return bool(col and not col["nullable"])


def _rebuild_sqlite_users(engine) -> None:
    """SQLite แก้ NOT NULL ของคอลัมน์ไม่ได้ จึงสร้างตาราง users ใหม่แล้วคัดลอกข้อมูล
    (legacy_alter_table ทำให้ foreign key ของตารางอื่นยังชี้ไปที่ชื่อ users เหมือนเดิม)"""
    from .models import User

    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        conn.exec_driver_sql("PRAGMA legacy_alter_table=ON")
        conn.commit()   # PRAGMA ต้องตั้งนอก transaction
        with conn.begin():
            old_cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(users)")]
            conn.exec_driver_sql("ALTER TABLE users RENAME TO users_old")
            for (name,) in conn.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='users_old' AND sql IS NOT NULL"):
                conn.exec_driver_sql(f'DROP INDEX "{name}"')
            User.__table__.create(conn)
            keep = [c for c in old_cols if c in User.__table__.c]
            cols = ", ".join(keep)
            conn.exec_driver_sql(f"INSERT INTO users ({cols}) SELECT {cols} FROM users_old")
            conn.exec_driver_sql("DROP TABLE users_old")
        conn.exec_driver_sql("PRAGMA legacy_alter_table=OFF")
        conn.commit()


def run(engine) -> None:
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    sqlite = engine.dialect.name == "sqlite"

    if "users" in tables and _line_id_required(insp):
        if sqlite:
            _rebuild_sqlite_users(engine)
        else:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ALTER COLUMN line_user_id DROP NOT NULL"))
        insp = inspect(engine)

    with engine.begin() as conn:
        for table, cols in NEW_COLUMNS.items():
            if table not in tables:
                continue
            have = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols.items():
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        if "users" in tables:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username_key ON users (username_key)"))
            if not sqlite:
                conn.execute(text("ALTER TABLE users ALTER COLUMN goal TYPE VARCHAR(20)"))
            conn.execute(text("UPDATE users SET goal = 'lose_weight' WHERE goal = 'lose'"))
            conn.execute(text("UPDATE users SET goal = 'build_muscle' WHERE goal = 'gain'"))
            conn.execute(text("UPDATE users SET failed_logins = 0 WHERE failed_logins IS NULL"))
