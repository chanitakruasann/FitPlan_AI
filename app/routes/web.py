"""หน้าเว็บ + เข้าสู่ระบบ + ข้อมูลร่างกาย"""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import auth_line, calc, config, passwords
from ..db import get_db
from ..deps import current_user, profile_complete, templates
from ..models import User

router = APIRouter()


def upsert_user(db: Session, line_user_id: str, name: str, picture: str | None) -> User:
    user = db.scalar(select(User).where(User.line_user_id == line_user_id))
    if user:
        user.display_name, user.picture_url = name, picture
    else:
        user = User(line_user_id=line_user_id, display_name=name, picture_url=picture)
        db.add(user)
    db.commit()
    return user


def _to_float(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def _page(request: Request, db: Session, name: str, active: str):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", 303)
    if not profile_complete(user):
        return RedirectResponse("/onboarding", 303)
    ctx = {"user": user, "active": active}
    if name == "home.html":
        ctx["plan"] = calc.daily_target(user.weight_kg, user.height_cm, user.age, user.sex,
                                        user.activity, user.goal, user.kg_change)
        ctx["goal_label"] = calc.goal_label(user.goal, user.kg_change)
        from ..exercises import DEFAULT_MINUTES, TARGETS
        ctx["targets"] = TARGETS
        ctx["default_minutes"] = DEFAULT_MINUTES[user.fitness_level]
    return templates.TemplateResponse(request, name, ctx)


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    return _page(request, db, "home.html", "home")


@router.get("/schedule")
def schedule_page(request: Request, db: Session = Depends(get_db)):
    return _page(request, db, "schedule.html", "schedule")


@router.get("/progress")
def progress_page(request: Request, db: Session = Depends(get_db)):
    return _page(request, db, "progress.html", "progress")


def _login_page(request: Request, mode: str = "login", errors: list[str] | None = None,
                username: str = "", status: int = 200):
    line_error = request.query_params.get("error")
    return templates.TemplateResponse(request, "login.html", {
        "mode": mode, "errors": errors or [], "username": username,
        "line_error": line_error, "dev_login": config.DEV_LOGIN,
    }, status_code=status)


@router.get("/login")
def login_page(request: Request, db: Session = Depends(get_db)):
    if current_user(request, db):
        return RedirectResponse("/", 303)
    mode = "register" if request.query_params.get("mode") == "register" else "login"
    return _login_page(request, mode)


def _sign_in(request: Request, user: User) -> RedirectResponse:
    request.session.clear()   # กัน session fixation
    request.session["user_id"] = user.id
    return RedirectResponse("/", 303)


@router.post("/auth/register")
def register(request: Request, username: str = Form(""), password: str = Form(""), password2: str = Form(""),
             db: Session = Depends(get_db)):
    username = username.strip()
    errors = passwords.validate_new_account(username, password, password2)
    key = passwords.username_key(username)
    if not errors and db.scalar(select(User).where(User.username_key == key)):
        errors.append("ชื่อผู้ใช้นี้มีคนใช้แล้ว ลองชื่ออื่น")
    if errors:
        return _login_page(request, "register", errors, username, 422)
    user = User(username=username, username_key=key, password_hash=passwords.hash_password(password),
                display_name=username, failed_logins=0)
    db.add(user)
    db.commit()
    return _sign_in(request, user)


@router.post("/auth/login")
def password_login(request: Request, username: str = Form(""), password: str = Form(""),
                   db: Session = Depends(get_db)):
    wrong = ["ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"]
    user = db.scalar(select(User).where(User.username_key == passwords.username_key(username)))
    if not user or not user.password_hash:
        passwords.verify_password(password, passwords.hash_password("x"))   # ใช้เวลาเท่ากัน ไม่บอกใบ้ว่ามีชื่อนี้ไหม
        return _login_page(request, "login", wrong, username.strip(), 401)

    now = datetime.now(timezone.utc)
    locked = user.locked_until
    if locked and locked.tzinfo is None:
        locked = locked.replace(tzinfo=timezone.utc)
    if locked and locked > now:
        mins = max(1, int((locked - now).total_seconds() // 60) + 1)
        return _login_page(request, "login", [f"ใส่รหัสผิดหลายครั้ง ลองใหม่ในอีก {mins} นาที"], username.strip(), 429)

    if not passwords.verify_password(password, user.password_hash):
        user.failed_logins = (user.failed_logins or 0) + 1
        if user.failed_logins >= passwords.MAX_FAILED:
            user.failed_logins = 0
            user.locked_until = now + timedelta(minutes=passwords.LOCK_MINUTES)
        db.commit()
        return _login_page(request, "login", wrong, username.strip(), 401)

    user.failed_logins, user.locked_until = 0, None
    db.commit()
    return _sign_in(request, user)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", 303)


def _onboarding(request, user, form, errors, status=200):
    editing = profile_complete(user)
    return templates.TemplateResponse(request, "onboarding.html", {
        "user": user, "form": form, "errors": errors,
        "activities": calc.ACTIVITY_LABELS, "goals": calc.GOALS, "levels": calc.LEVELS, "equipment": calc.EQUIPMENT,
        "editing": editing, "active": "profile" if editing else "",
        "linked": request.query_params.get("linked"), "link_error": request.query_params.get("link_error"),
    }, status_code=status)


@router.get("/onboarding")
def onboarding_page(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", 303)
    form = {
        "fitness_level": user.fitness_level or "", "equipment": user.equipment or "",
        "height_cm": user.height_cm or "", "weight_kg": user.weight_kg or "",
        "age": user.age or "", "sex": user.sex or "", "activity": user.activity or "",
        "goal": calc.LEGACY_GOALS.get(user.goal, user.goal) or "lose_weight", "kg_change": user.kg_change or "",
    }
    return _onboarding(request, user, form, [])


@router.post("/onboarding")
def onboarding_submit(
    request: Request,
    fitness_level: str = Form(""), equipment: str = Form(""),
    height_cm: str = Form(""), weight_kg: str = Form(""), age: str = Form(""),
    sex: str = Form(""), activity: str = Form(""), goal: str = Form(""), kg_change: str = Form(""),
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", 303)
    age_f = _to_float(age)
    kg_mode = calc.GOALS.get(goal, {}).get("kg")
    values = {
        "height_cm": _to_float(height_cm), "weight_kg": _to_float(weight_kg),
        "age": int(age_f) if age_f is not None else None,
        "sex": sex, "activity": activity, "goal": goal,
        "kg_change": _to_float(kg_change) if kg_mode else None,
        "fitness_level": fitness_level, "equipment": equipment,
    }
    errors = calc.validate_profile(**values)
    if errors:
        form = {k: ("" if v is None else v) for k, v in values.items()}
        return _onboarding(request, user, form, errors, 422)

    plan = calc.daily_target(values["weight_kg"], values["height_cm"], values["age"], values["sex"],
                             values["activity"], values["goal"], values["kg_change"])
    for k, v in values.items():
        setattr(user, k, v)
    user.daily_kcal_target = plan["target"]
    db.commit()
    return RedirectResponse("/", 303)


@router.get("/auth/line/login")
def line_login(request: Request, link: int = 0, db: Session = Depends(get_db)):
    """link=1: ผู้ใช้ที่สมัครด้วยรหัสผ่าน ขอเชื่อมบัญชี LINE เพื่อรับแจ้งเตือน"""
    state, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    request.session["oauth_state"] = state
    request.session["oauth_nonce"] = nonce
    request.session["oauth_link"] = bool(link and current_user(request, db))
    return RedirectResponse(auth_line.build_login_url(state, nonce), 302)


@router.get("/auth/line/callback")
def line_callback(request: Request, code: str | None = None, state: str | None = None,
                  error: str | None = None, db: Session = Depends(get_db)):
    expected_state = request.session.pop("oauth_state", None)
    nonce = request.session.pop("oauth_nonce", None)
    linking = request.session.pop("oauth_link", False)
    fail = "/onboarding?link_error=1" if linking else "/login?error=1"
    if error or not code or not state or state != expected_state:
        return RedirectResponse(fail, 303)
    try:
        tokens = auth_line.exchange_code(code)
        profile = auth_line.verify_id_token(tokens["id_token"], nonce)
    except Exception:
        return RedirectResponse(fail, 303)

    if linking:
        user = current_user(request, db)
        if not user:
            return RedirectResponse("/login", 303)
        owner = db.scalar(select(User).where(User.line_user_id == profile["sub"]))
        if owner and owner.id != user.id:
            return RedirectResponse("/onboarding?link_error=taken", 303)
        user.line_user_id = profile["sub"]
        user.picture_url = profile.get("picture") or user.picture_url
        db.commit()
        return RedirectResponse("/onboarding?linked=1", 303)

    user = upsert_user(db, profile["sub"], profile.get("name") or "เพื่อน", profile.get("picture"))
    return _sign_in(request, user)


@router.get("/auth/dev-login")
def dev_login(request: Request, name: str = "ทดสอบ", db: Session = Depends(get_db)):
    """เข้าระบบโดยไม่ผ่าน LINE — เปิดได้เฉพาะตอน DEV_LOGIN=1"""
    if not config.DEV_LOGIN:
        raise HTTPException(404)
    user = upsert_user(db, f"dev-{name}", name, None)
    return _sign_in(request, user)
