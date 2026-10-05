"""คลิป, โปรแกรมสร้างท่า, หน้า "วันนี้", ทำสำเร็จ/ข้าม และการปรับตารางอัตโนมัติ"""
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import ai, analysis as an, exercises as ex, optimizer, planning, video as yt
from ..db import get_db
from ..deps import require_user_api, today
from ..models import DayStatus, FoodLog, ScheduleMove, User, UserVideo, Video, WorkoutLog
from ..progress import streak

router = APIRouter(prefix="/api")


# ---------- คลิป ----------

class VideoQuery(BaseModel):
    url: str = Field(min_length=5, max_length=300)


class WorkoutLogIn(BaseModel):
    video_id: int
    portion: float = Field(default=1.0, gt=0, le=1)


def video_dict(v: Video, weight_kg: float) -> dict:
    segments = [{
        **s,
        "label": yt.CATEGORIES.get(s["category"], yt.CATEGORIES[yt.DEFAULT_CATEGORY])["label"],
        "kcal": round(yt.segment_kcal(s["category"], s["minutes"], weight_kg)),
        "muscle_text": ", ".join(ex.MUSCLES[m] for m in s.get("muscles") or []),
    } for s in v.segments]
    muscles = sorted({m for s in v.segments for m in s.get("muscles") or []}, key=list(ex.MUSCLES).index)
    active = sum(s["minutes"] for s in v.segments if s["category"] != "rest")
    return {
        "id": v.id, "url": v.url, "title": v.title,
        "total_minutes": v.total_minutes, "active_minutes": round(active, 1),
        "kcal": round(yt.video_kcal(v.segments, weight_kg)),
        "intensity": yt.intensity_of(v.segments),
        "muscles": muscles, "muscle_text": ex.describe_muscles(muscles),
        "segments": segments,
    }


def save_to_library(db: Session, user: User, v: Video) -> None:
    if not db.scalar(select(UserVideo).where(UserVideo.user_id == user.id, UserVideo.video_id == v.id)):
        db.add(UserVideo(user_id=user.id, video_id=v.id))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()


@router.post("/video/analyze")
def video_analyze(q: VideoQuery, user: User = Depends(require_user_api), db: Session = Depends(get_db)):
    vid = yt.extract_video_id(q.url)
    if not vid:
        raise HTTPException(422, "ลิงก์นี้ไม่ใช่ลิงก์คลิป YouTube ลองคัดลอกลิงก์จากปุ่มแชร์")
    url = yt.canonical_url(vid)
    v = db.scalar(select(Video).where(Video.url == url))
    if v and (v.version or 1) >= yt.ANALYSIS_VERSION:
        save_to_library(db, user, v)
        return video_dict(v, user.weight_kg)

    title = v.title if v else yt.fetch_title(vid)
    if title is None:
        raise HTTPException(422, "เปิดคลิปนี้ไม่ได้ คลิปต้องเป็นสาธารณะและยังไม่ถูกลบ")
    try:
        result = ai.analyze_video(url, yt.CATEGORIES)
    except ai.NotWorkoutError:
        raise HTTPException(422, "คลิปนี้ดูไม่ใช่คลิปออกกำลังกายแบบทำตาม ลองคลิปอื่น")
    except ai.AIError:
        raise HTTPException(502, "วิเคราะห์คลิปไม่สำเร็จ ลองอีกครั้ง หรือลองคลิปที่สั้นกว่านี้")

    if v:   # ผลวิเคราะห์รุ่นเก่า (ยังไม่มีข้อมูลกล้ามเนื้อ) → อัปเดต
        v.segments, v.total_minutes, v.version = result["segments"], result["total_minutes"], yt.ANALYSIS_VERSION
        db.commit()
    else:
        v = Video(url=url, title=title[:300], version=yt.ANALYSIS_VERSION, **result)
        db.add(v)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            v = db.scalar(select(Video).where(Video.url == url))
    save_to_library(db, user, v)
    return video_dict(v, user.weight_kg)


@router.post("/workout/log")
def workout_log(entry: WorkoutLogIn, user: User = Depends(require_user_api), db: Session = Depends(get_db)):
    v = db.get(Video, entry.video_id)
    if not v:
        raise HTTPException(404, "ไม่พบคลิปนี้")
    kcal = yt.video_kcal(v.segments, user.weight_kg) * entry.portion
    muscles = sorted({m for s in v.segments for m in s.get("muscles") or []})
    log = WorkoutLog(user_id=user.id, video_id=v.id, title=v.title, kcal=round(kcal, 1),
                     minutes=round(v.total_minutes * entry.portion, 1), muscles=muscles,
                     source="video", done_on=today())
    db.add(log)
    db.commit()
    return {"id": log.id, "kcal": round(kcal)}


@router.delete("/workout/log/{log_id}")
def workout_log_delete(log_id: int, user: User = Depends(require_user_api), db: Session = Depends(get_db)):
    log = db.get(WorkoutLog, log_id)
    if not log or log.user_id != user.id:
        raise HTTPException(404, "ไม่พบรายการนี้")
    db.delete(log)
    db.commit()
    return {"ok": True}


# ---------- "วันนี้อยากออก..." ----------

class GenerateIn(BaseModel):
    target: str
    minutes: int | None = Field(default=None, ge=15, le=120)


def recent_muscles(db: Session, user: User, d: date, days: int = 2) -> dict[int, set[str]]:
    """กล้ามเนื้อที่ฝึกในช่วง {days} วันก่อนวันที่ d → {จำนวนวันที่ผ่านมา: กล้ามเนื้อ}"""
    out: dict[int, set[str]] = {}
    logs = db.scalars(select(WorkoutLog).where(
        WorkoutLog.user_id == user.id, WorkoutLog.done_on >= d - timedelta(days=days), WorkoutLog.done_on < d))
    for l in logs:
        out.setdefault((d - l.done_on).days, set()).update(l.muscles or [])
    return out


def _generate(user: User, target: str, minutes: int | None) -> dict:
    if target not in ex.TARGETS:
        raise HTTPException(422, "เลือกส่วนที่อยากฝึก")
    ctx = planning.user_ctx(user)
    return ex.generate_workout(target, ctx["level"], ctx["goal"], ctx["equipment"], minutes, ctx["weight"])


@router.post("/workout/generate")
def workout_generate(body: GenerateIn, user: User = Depends(require_user_api), db: Session = Depends(get_db)):
    w = _generate(user, body.target, body.minutes)
    warnings = []
    for days_ago, mus in ex.recent_overlap(body.target, recent_muscles(db, user, today())):
        when = "เมื่อวาน" if days_ago == 1 else f"{days_ago} วันก่อน"
        warnings.append(f"{', '.join(ex.MUSCLES[m] for m in mus)} เพิ่งฝึกไป{when} "
                        "ควรพักกล้ามเนื้อกลุ่มเดิมอย่างน้อย 48 ชั่วโมง ลองเลือกส่วนอื่น หรือทำเบาลง")
    return {**{k: v for k, v in w.items() if k != "segments"}, "warnings": warnings}


@router.post("/workout/log-program")
def workout_log_program(body: GenerateIn, user: User = Depends(require_user_api), db: Session = Depends(get_db)):
    w = _generate(user, body.target, body.minutes)
    log = WorkoutLog(user_id=user.id, title=w["title"], kcal=w["kcal"], minutes=w["minutes"],
                     muscles=w["muscles"], source="program", done_on=today())
    db.add(log)
    db.commit()
    return {"id": log.id, "kcal": w["kcal"]}


# ---------- หน้า "วันนี้" ----------

def _day_plan(db: Session, user: User, d: date) -> dict | None:
    items = planning.planned_items(db, user, d)
    if not items:
        return None
    ctx = planning.user_ctx(user)
    sessions = [planning.session_of(it, ctx) for it in items]
    segs = [s for sess in sessions for s in sess["segments"]]
    muscles = sorted({m for sess in sessions for m in sess["muscles"]}, key=list(ex.MUSCLES).index)
    status = db.scalar(select(DayStatus.status).where(DayStatus.user_id == user.id, DayStatus.day == d))
    return {
        "date": d.isoformat(), "day_name": an.DAY_NAMES[d.weekday()],
        "sessions": [planning.public(s) for s in sessions],
        "minutes": sum(s["minutes"] for s in sessions), "kcal": sum(s["kcal"] for s in sessions),
        "intensity": yt.intensity_of(segs),
        "groups": [ex.GROUPS[g]["en"] for g in ex.groups_of(muscles)],
        "muscle_text": ex.describe_muscles(muscles),
        "status": status,
    }


@router.get("/today")
def today_summary(user: User = Depends(require_user_api), db: Session = Depends(get_db)):
    d = today()
    logs = db.scalars(select(FoodLog).where(FoodLog.user_id == user.id, FoodLog.eaten_on == d).order_by(FoodLog.id)).all()
    workouts = db.scalars(select(WorkoutLog).where(
        WorkoutLog.user_id == user.id, WorkoutLog.done_on == d).order_by(WorkoutLog.id)).all()
    eaten = sum(l.kcal for l in logs)
    burned = round(sum(w.kcal for w in workouts))
    target = user.daily_kcal_target

    yesterday = d - timedelta(days=1)
    pending = _day_plan(db, user, yesterday)
    if pending and pending["status"]:
        pending = None

    return {
        "date": d.isoformat(), "day_name": an.DAY_NAMES[d.weekday()],
        "target": target, "eaten": eaten, "burned": burned, "remaining": target + burned - eaten,
        "logs": [{"id": l.id, "name": l.name, "servings": l.servings, "kcal": l.kcal} for l in logs],
        "workouts": [{"id": w.id, "title": w.title or "ออกกำลังกาย", "kcal": round(w.kcal), "source": w.source}
                     for w in workouts if w.source != "plan"],
        "plan": _day_plan(db, user, d),
        "pending": pending,
        "streak": streak(db, user, d),
    }


# ---------- ทำสำเร็จ / ข้าม / ปรับตาราง ----------

class DayIn(BaseModel):
    day: Literal["today", "yesterday"] = "today"


def _resolve(day: str) -> date:
    d = today()
    return d if day == "today" else d - timedelta(days=1)


def _set_status(db: Session, user: User, d: date, status: str) -> None:
    row = db.scalar(select(DayStatus).where(DayStatus.user_id == user.id, DayStatus.day == d))
    if row:
        row.status = status
    else:
        db.add(DayStatus(user_id=user.id, day=d, status=status))


def _clear_plan_logs(db: Session, user: User, d: date) -> None:
    for l in db.scalars(select(WorkoutLog).where(
            WorkoutLog.user_id == user.id, WorkoutLog.done_on == d, WorkoutLog.source == "plan")):
        db.delete(l)


@router.post("/day/complete")
def day_complete(body: DayIn, user: User = Depends(require_user_api), db: Session = Depends(get_db)):
    d = _resolve(body.day)
    items = planning.planned_items(db, user, d)
    if not items:
        raise HTTPException(422, "วันนี้ไม่มีโปรแกรมในตาราง")
    ctx = planning.user_ctx(user)
    _clear_plan_logs(db, user, d)
    total = 0
    for it in items:
        s = planning.session_of(it, ctx)
        db.add(WorkoutLog(user_id=user.id, video_id=s["video_id"], title=s["title"], kcal=s["kcal"],
                          minutes=s["minutes"], muscles=s["muscles"], source="plan", done_on=d))
        total += s["kcal"]
    _set_status(db, user, d, "done")
    db.commit()
    return {"ok": True, "kcal": total, "streak": streak(db, user, today())}


def _proposal(db: Session, user: User, d: date) -> dict:
    t = today()
    ws = planning.week_start(d)
    plan = planning.week_plan(db, user, ws)
    ctx = planning.user_ctx(user)
    statuses = {s.day: s.status for s in db.scalars(select(DayStatus).where(
        DayStatus.user_id == user.id, DayStatus.day >= ws, DayStatus.day < ws + timedelta(days=7)))}
    week = []
    for i, day_items in enumerate(plan):
        day_date = ws + timedelta(days=i)
        if day_date != d and day_date < t and statuses.get(day_date) == "skipped":
            week.append([])   # วันที่ข้ามไปแล้ว ไม่นับ
        else:
            week.append([planning.session_of(it, ctx) for it in day_items])
    first = (t - ws).days if d < t else d.weekday() + 1
    if ws != planning.week_start(t):   # ข้ามวันอาทิตย์ของสัปดาห์ก่อน → ไม่มีวันให้ชดเชย
        first = 7
    p = optimizer.propose(week, d.weekday(), first, ctx)
    titles = [s["title"] for s in week[d.weekday()]]
    return {**p, "message": optimizer.explain(p, titles), "from_date": d.isoformat()}


@router.post("/day/skip")
def day_skip(body: DayIn, user: User = Depends(require_user_api), db: Session = Depends(get_db)):
    d = _resolve(body.day)
    if not planning.planned_items(db, user, d):
        raise HTTPException(422, "วันนี้ไม่มีโปรแกรมในตาราง")
    _clear_plan_logs(db, user, d)
    _set_status(db, user, d, "skipped")
    db.commit()
    return _proposal(db, user, d)


@router.post("/day/undo")
def day_undo(body: DayIn, user: User = Depends(require_user_api), db: Session = Depends(get_db)):
    d = _resolve(body.day)
    row = db.scalar(select(DayStatus).where(DayStatus.user_id == user.id, DayStatus.day == d))
    if row:
        db.delete(row)
    _clear_plan_logs(db, user, d)
    db.commit()
    return {"ok": True}


class ApplyIn(BaseModel):
    from_day: Literal["today", "yesterday"]
    to_weekday: int = Field(ge=0, le=6)


@router.post("/reschedule/apply")
def reschedule_apply(body: ApplyIn, user: User = Depends(require_user_api), db: Session = Depends(get_db)):
    d = _resolve(body.from_day)
    ws = planning.week_start(d)
    target = ws + timedelta(days=body.to_weekday)
    if planning.week_start(today()) != ws or target < today() or target == d:
        raise HTTPException(422, "ย้ายได้เฉพาะวันที่ยังมาไม่ถึงในสัปดาห์นี้")
    items = planning.planned_items(db, user, d)
    if not items:
        raise HTTPException(422, "ไม่มีโปรแกรมให้ย้าย")
    for it in items:
        mv = db.scalar(select(ScheduleMove).where(ScheduleMove.item_id == it.id, ScheduleMove.week_start == ws))
        if mv:
            mv.to_weekday = body.to_weekday
        else:
            db.add(ScheduleMove(user_id=user.id, item_id=it.id, week_start=ws, to_weekday=body.to_weekday))
    db.commit()
    return {"ok": True, "to_day_name": an.DAY_NAMES[body.to_weekday]}
