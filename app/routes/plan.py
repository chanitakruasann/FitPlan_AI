"""ตารางออกกำลังกาย: เพิ่ม/ลบ/ตั้งเวลา, คะแนน และคำแนะนำจาก AI"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import ai, analysis as an, calc, exercises as ex, planning, video as yt
from ..db import get_db
from ..deps import TZ, require_user_api
from ..models import ScheduleItem, User, UserVideo, Video

router = APIRouter(prefix="/api/schedule")

DEFAULT_REMIND = "07:00"
MAX_ITEMS_PER_DAY = 5
TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"


@router.get("")
def schedule_get(user: User = Depends(require_user_api), db: Session = Depends(get_db)):
    week = planning.template_week(db, user)
    sessions, result = planning.analyze(db, user, week)
    days = []
    for i, day in enumerate(week):
        days.append({
            "weekday": i, "name": an.DAY_NAMES[i],
            "remind_time": day[0].remind_time if day else None,
            "items": [{**planning.public(s), "id": it.id} for it, s in zip(day, sessions[i])],
            "stats": result["days"][i],
        })
    library = db.scalars(select(Video).join(UserVideo, UserVideo.video_id == Video.id)
                         .where(UserVideo.user_id == user.id).order_by(UserVideo.id.desc())).all()
    level = planning.user_ctx(user)["level"]
    return {
        "days": days, "totals": result["totals"], "findings": result["findings"], "score": result["score"],
        "library": [{"id": v.id, "title": v.title, "minutes": round(v.total_minutes),
                     "intensity": yt.intensity_of(v.segments)} for v in library],
        "programs": [{"key": k, "label": t["label"]} for k, t in ex.TARGETS.items()],
        "program_minutes": ex.DEFAULT_MINUTES[level],
        "level": calc.LEVELS[level]["label"], "goal": calc.goal_label(user.goal, user.kg_change),
    }


class ScheduleItemIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    video_id: int | None = None
    program: str | None = None
    program_minutes: int | None = Field(default=None, ge=15, le=120)


class RemindTimeIn(BaseModel):
    remind_time: str = Field(pattern=TIME_PATTERN)


@router.post("/item")
def schedule_add(entry: ScheduleItemIn, user: User = Depends(require_user_api), db: Session = Depends(get_db)):
    if (entry.video_id is None) == (entry.program is None):
        raise HTTPException(422, "เลือกคลิปหรือโปรแกรมอย่างใดอย่างหนึ่ง")
    if entry.video_id is not None:
        v = db.get(Video, entry.video_id)
        if not v:
            raise HTTPException(404, "ไม่พบคลิปนี้")
    elif entry.program not in ex.TARGETS:
        raise HTTPException(422, "ไม่พบโปรแกรมนี้")
    day = planning.template_week(db, user)[entry.weekday]
    if len(day) >= MAX_ITEMS_PER_DAY:
        raise HTTPException(422, f"ใส่ได้สูงสุด {MAX_ITEMS_PER_DAY} รายการต่อวัน")
    it = ScheduleItem(user_id=user.id, weekday=entry.weekday, video_id=entry.video_id,
                      program=entry.program, program_minutes=entry.program_minutes,
                      remind_time=day[0].remind_time if day else DEFAULT_REMIND)
    db.add(it)
    db.commit()
    if entry.video_id is not None:
        from .workout import save_to_library
        save_to_library(db, user, v)
    return {"id": it.id}


@router.delete("/item/{item_id}")
def schedule_remove(item_id: int, user: User = Depends(require_user_api), db: Session = Depends(get_db)):
    it = db.get(ScheduleItem, item_id)
    if not it or it.user_id != user.id:
        raise HTTPException(404, "ไม่พบรายการนี้")
    from ..models import ScheduleMove
    for mv in db.scalars(select(ScheduleMove).where(ScheduleMove.item_id == it.id)):
        db.delete(mv)
    db.delete(it)
    db.commit()
    return {"ok": True}


@router.put("/day/{weekday}")
def schedule_set_time(weekday: int, body: RemindTimeIn,
                      user: User = Depends(require_user_api), db: Session = Depends(get_db)):
    if not 0 <= weekday <= 6:
        raise HTTPException(404)
    items = planning.template_week(db, user)[weekday]
    if not items:
        raise HTTPException(422, "เพิ่มรายการในวันนี้ก่อนตั้งเวลาเตือน")
    for it in items:
        it.remind_time = body.remind_time
    db.commit()
    return {"ok": True}


def advice_summary(week_sessions, result) -> str:
    lines = []
    for i, sessions in enumerate(week_sessions):
        st = result["days"][i]
        if st["is_rest"]:
            lines.append(f"{an.DAY_NAMES[i]}: วันพัก")
            continue
        titles = ", ".join(s["title"] for s in sessions)
        lines.append(
            f"{an.DAY_NAMES[i]}: {titles} | {st['active_min']} นาที, ความหนัก {yt.INTENSITY[st['intensity']]['label']}, "
            f"กล้ามเนื้อ: {ex.describe_muscles(st['muscles']) or '-'}")
    sc = result["score"]
    lines.append(f"คะแนนรวม {sc['total']}/100: " + ", ".join(f"{p['label']} {p['score']}" for p in sc["parts"]))
    lines.append("ผลวิเคราะห์:")
    lines += [f"- {f['text']}" for f in result["findings"]]
    return "\n".join(lines)


@router.post("/advice")
def schedule_advice(user: User = Depends(require_user_api), db: Session = Depends(get_db)):
    sessions, result = planning.analyze(db, user, planning.template_week(db, user))
    if not result["score"]:
        raise HTTPException(422, "เพิ่มรายการลงตารางก่อน แล้วค่อยขอคำแนะนำ")
    ctx = planning.user_ctx(user)
    try:
        return ai.schedule_advice(calc.LEVELS[ctx["level"]]["label"],
                                  calc.goal_label(user.goal, user.kg_change),
                                  advice_summary(sessions, result))
    except ai.AIError:
        raise HTTPException(502, "ขอคำแนะนำไม่สำเร็จ ลองอีกครั้ง")
