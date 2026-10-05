import os

from dotenv import load_dotenv

load_dotenv()


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return "sqlite:///./local.db"
    # Neon/Supabase ให้มาเป็น postgres:// หรือ postgresql:// → บอก SQLAlchemy ให้ใช้ไดรเวอร์ psycopg 3
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-only-secret")
CRON_SECRET = os.getenv("CRON_SECRET", "")
DATABASE_URL = _database_url()

LINE_LOGIN_CHANNEL_ID = os.getenv("LINE_LOGIN_CHANNEL_ID", "")
LINE_LOGIN_CHANNEL_SECRET = os.getenv("LINE_LOGIN_CHANNEL_SECRET", "")
LINE_MESSAGING_TOKEN = os.getenv("LINE_MESSAGING_TOKEN", "")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

DEV_LOGIN = os.getenv("DEV_LOGIN", "0") == "1"
