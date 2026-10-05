"""สรุปความก้าวหน้ารายสัปดาห์และ streak"""
from datetime import date, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .deps import TZ
from .models import DayStatus, User, WeeklyCheckin, WorkoutLog


def joined_on(user: User) -> date | None:
    c = user.created_at
    if c is None:
        return None
    if c.tzinfo is None:   # SQLite เก็บเวลาเป็น UTC แบบไม่มีโซน
        c = c.replace(tzinfo=timezone.utc)
    return c.astimezone(TZ).date()
from .planning import week_plan, week_start


def week_metrics(db: Session, user: User, ws: date, today: date) -> dict:
    we = ws + timedelta(days=6)
    plan = week_plan(db, user, ws)
    start = joined_on(user)
    # วันก่อนสมัครไม่นับเป็นวันตามแผน
    planned_days = [ws + timedelta(days=i) for i in range(7) if plan[i] and (not start or ws + timedelta(days=i) >= start)]
    statuses = {s.day: s.status for s in db.scalars(select(DayStatus).where(
        DayStatus.user_id == user.id, DayStatus.day >= ws, DayStatus.day <= we))}
    logs = db.scalars(select(WorkoutLog).where(
        WorkoutLog.user_id == user.id, WorkoutLog.done_on >= ws, WorkoutLog.done_on <= we)).all()
    active_dates = {l.done_on for l in logs} | {d for d, s in statuses.items() if s == "done"}
    done_planned = sum(1 for d in planned_days if statuses.get(d) == "done")
    due = [d for d in planned_days if d <= today]
    checkin = db.scalar(select(WeeklyCheckin).where(WeeklyCheckin.user_id == user.id, WeeklyCheckin.week_start == ws))
    return {
        "week_start": ws.isoformat(),
        "planned_days": len(planned_days),
        "done_planned_days": done_planned,
        "exercise_days": len(active_dates),
        "adherence": round(100 * done_planned / len(due)) if due else None,
        "kcal": round(sum(l.kcal for l in logs)),
        "minutes": round(sum(l.minutes or 0 for l in logs)),
        "weight_kg": checkin.weight_kg if checkin else None,
        "waist_cm": checkin.waist_cm if checkin else None,
    }


def streak(db: Session, user: User, today: date) -> int:
    """จำนวนวันติดต่อกันที่ทำตามแผน (วันพักตามแผนนับด้วย) นับถึงวันนี้หรือเมื่อวาน"""
    first = min(filter(None, [
        db.scalar(select(func.min(DayStatus.day)).where(DayStatus.user_id == user.id)),
        db.scalar(select(func.min(WorkoutLog.done_on)).where(WorkoutLog.user_id == user.id)),
    ]), default=None)
    if not first:
        return 0
    statuses = {s.day: s.status for s in db.scalars(select(DayStatus).where(
        DayStatus.user_id == user.id, DayStatus.day >= first))}
    did = {d for (d,) in db.execute(select(WorkoutLog.done_on).where(
        WorkoutLog.user_id == user.id, WorkoutLog.done_on >= first)).all()}
    plans: dict[date, list] = {}

    def followed(d: date) -> bool | None:
        ws = week_start(d)
        if ws not in plans:
            plans[ws] = week_plan(db, user, ws)
        planned = bool(plans[ws][d.weekday()])
        st = statuses.get(d)
        if st == "skipped":
            return not planned   # ข้ามแต่ย้ายไปวันอื่นแล้ว = ยังทำตามแผน
        if st == "done" or d in did:
            return True
        return None if planned else True   # มีแผนแต่ยังไม่บันทึก = ยังไม่รู้

    count, d = 0, today
    if followed(today) is not True:
        d = today - timedelta(days=1)   # วันนี้ยังไม่จบ ไม่ทำให้ streak ขาด
    while d >= first:
        if followed(d) is not True:
            break
        count += 1
        d -= timedelta(days=1)
    return count
