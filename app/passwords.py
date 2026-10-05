"""เก็บรหัสผ่านแบบ hash (PBKDF2-SHA256 จากไลบรารีมาตรฐาน ไม่ต้องติดตั้งเพิ่ม)"""
import hashlib
import hmac
import re
import secrets

ITERATIONS = 310_000
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\u0E00-\u0E7F]{3,30}$")   # อังกฤษ ไทย ตัวเลข _ .
MIN_PASSWORD = 6
MAX_FAILED = 5
LOCK_MINUTES = 10


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _, iterations, salt, digest = stored.split("$")
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations)).hex()
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(check, digest)


def username_key(username: str) -> str:
    return username.strip().lower()


def validate_new_account(username: str, password: str, password2: str) -> list[str]:
    errors = []
    if not USERNAME_RE.match(username.strip()):
        errors.append("ชื่อผู้ใช้ต้องยาว 3–30 ตัว ใช้ได้เฉพาะตัวอักษรไทย อังกฤษ ตัวเลข _ และ . (ห้ามเว้นวรรค)")
    if len(password) < MIN_PASSWORD:
        errors.append(f"รหัสผ่านต้องยาวอย่างน้อย {MIN_PASSWORD} ตัว")
    elif password != password2:
        errors.append("รหัสผ่านสองช่องไม่ตรงกัน")
    return errors
