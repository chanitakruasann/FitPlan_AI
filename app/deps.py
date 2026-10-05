from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .db import get_db
from .models import User

TZ = ZoneInfo("Asia/Bangkok")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def today() -> date:
    return datetime.now(TZ).date()


def current_user(request: Request, db: Session) -> User | None:
    uid = request.session.get("user_id")
    return db.get(User, uid) if uid else None


def profile_complete(user: User) -> bool:
    return user.daily_kcal_target is not None and user.fitness_level is not None and user.equipment is not None


def require_user_api(request: Request, db: Session = Depends(get_db)) -> User:
    user = current_user(request, db)
    if not user:
        raise HTTPException(401, "กรุณาเข้าสู่ระบบ")
    if not profile_complete(user):
        raise HTTPException(409, "กรอกข้อมูลร่างกายก่อน")
    return user
