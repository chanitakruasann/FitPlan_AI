"""อัปเดตโครงฐานข้อมูลเดิมให้ตรงกับโมเดลใหม่ (เพิ่มคอลัมน์ที่ขาด + แปลงค่าเก่า)

create_all สร้างได้แค่ตารางใหม่ ไม่เพิ่มคอลัมน์ในตารางที่มีอยู่แล้ว ไฟล์นี้จึงเติมให้
ถ้าโปรเจกต์โตขึ้นควรเปลี่ยนไปใช้ Alembic
"""
from sqlalchemy import inspect, text

NEW_COLUMNS = {
    "users": {"fitness_level": "VARCHAR(20)", "equipment": "VARCHAR(20)"},
    "videos": {"version": "INTEGER DEFAULT 1"},
    "schedule_items": {"program": "VARCHAR(20)", "program_minutes": "INTEGER"},
    "workout_logs": {"title": "VARCHAR(300)", "minutes": "FLOAT", "muscles": "JSON", "source": "VARCHAR(10)"},
}


def run(engine) -> None:
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table, cols in NEW_COLUMNS.items():
            if table not in tables:
                continue
            have = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols.items():
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        if "users" in tables and engine.dialect.name == "postgresql":
            conn.execute(text("ALTER TABLE users ALTER COLUMN goal TYPE VARCHAR(20)"))
        if "users" in tables:
            conn.execute(text("UPDATE users SET goal = 'lose_weight' WHERE goal = 'lose'"))
            conn.execute(text("UPDATE users SET goal = 'build_muscle' WHERE goal = 'gain'"))
