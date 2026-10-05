"""แปลงตารางเป็นแผนของแต่ละวัน (รวมการย้ายเฉพาะสัปดาห์) และแปลงรายการในตารางเป็น session"""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import analysis as an, exercises as ex, video as yt
from .models import ScheduleItem, ScheduleMove, User

FLEX_CATS = {"warmup_stretch", "cooldown", "rest"}


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def user_ctx(user: User) -> dict:
    return {
        "level": user.fitness_level or "beginner",
        "goal": user.goal or "maintain",
        "equipment": user.equipment or "none",
        "weight": user.weight_kg,
    }


def template_week(db: Session, user: User) -> list[list[ScheduleItem]]:
    items = db.scalars(select(ScheduleItem).where(ScheduleItem.user_id == user.id).order_by(ScheduleItem.id)).all()
    week: list[list[ScheduleItem]] = [[] for _ in range(7)]
    for it in items:
        if it.video or it.program:
            week[it.weekday].append(it)
    return week


def week_plan(db: Session, user: User, ws: date) -> list[list[ScheduleItem]]:
    """ตารางของสัปดาห์ที่เริ่มวันจันทร์ ws หลังจากใช้การย้ายของสัปดาห์นั้นแล้ว"""
    week = template_week(db, user)
    moves = {m.item_id: m.to_weekday for m in db.scalars(
        select(ScheduleMove).where(ScheduleMove.user_id == user.id, ScheduleMove.week_start == ws))}
    if not moves:
        return week
    out: list[list[ScheduleItem]] = [[] for _ in range(7)]
    for day in week:
        for it in day:
            out[moves.get(it.id, it.weekday)].append(it)
    return out


def planned_items(db: Session, user: User, d: date) -> list[ScheduleItem]:
    return week_plan(db, user, week_start(d))[d.weekday()]


def session_of(item: ScheduleItem, ctx: dict) -> dict:
    if item.program:
        w = ex.generate_workout(item.program, ctx["level"], ctx["goal"], ctx["equipment"],
                                item.program_minutes, ctx["weight"])
        return {
            "item_id": item.id, "kind": "program", "program": item.program, "title": w["title"], "url": None,
            "minutes": w["minutes"], "kcal": w["kcal"], "intensity": w["intensity"],
            "muscles": w["muscles"], "muscle_text": w["muscle_text"],
            "exercises": w["exercises"], "style": w["style"],
            "exercise_names": [e["name"] for e in w["exercises"]],
            "segments": w["segments"], "video_id": None,
        }
    v = item.video
    muscles = sorted({m for s in v.segments for m in s.get("muscles") or []}, key=list(ex.MUSCLES).index)
    names = list(dict.fromkeys(s["name"] for s in v.segments if s["category"] not in FLEX_CATS))
    return {
        "item_id": item.id, "kind": "video", "program": None, "title": v.title, "url": v.url,
        "minutes": round(v.total_minutes), "kcal": round(yt.video_kcal(v.segments, ctx["weight"])),
        "intensity": yt.intensity_of(v.segments),
        "muscles": muscles, "muscle_text": ex.describe_muscles(muscles),
        "exercises": None, "style": None, "exercise_names": names[:6],
        "segments": v.segments, "video_id": v.id,
        "needs_reanalysis": (v.version or 1) < yt.ANALYSIS_VERSION,
    }


def public(session: dict) -> dict:
    """ตัด segments ออกก่อนส่งให้หน้าเว็บ"""
    return {k: v for k, v in session.items() if k != "segments"}


def analyze(db: Session, user: User, week_items: list[list[ScheduleItem]]) -> tuple[list[list[dict]], dict]:
    ctx = user_ctx(user)
    sessions = [[session_of(it, ctx) for it in day] for day in week_items]
    return sessions, an.analyze_week(sessions, ctx["level"], ctx["goal"], ctx["weight"])
