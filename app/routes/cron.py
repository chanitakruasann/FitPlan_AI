"""แจ้งเตือน LINE ตามตาราง (เรียกจาก cron-job.org ทุก 5 นาที)"""
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config, line_msg, planning, video as yt
from ..db import get_db
from ..deps import TZ
from ..models import ReminderLog, ScheduleItem, User

router = APIRouter()


def reminder_text(sessions: list[dict]) -> str:
    lines = ["วันนี้มีออกกำลังกายตามตาราง 💪"]
    for s in sessions:
        lines.append(f"• {s['title']} ({s['minutes']} นาที, ความหนัก{yt.INTENSITY[s['intensity']]['label']})")
        if s["url"]:
            lines.append(f"  {s['url']}")
        elif s["exercises"]:
            for e in s["exercises"]:
                amount = f"{e['reps']} ครั้ง" if e["reps"] else f"{e['seconds']} วินาที"
                lines.append(f"  - {e['name']} {e['sets']} เซต x {amount}")
    lines.append("ทำเสร็จแล้วกด \"ทำสำเร็จ\" ในเว็บด้วยนะ")
    return "\n".join(lines)


@router.post("/cron/remind")
def cron_remind(x_cron_secret: str | None = Header(None), db: Session = Depends(get_db)):
    if not config.CRON_SECRET or not secrets.compare_digest(x_cron_secret or "", config.CRON_SECRET):
        raise HTTPException(401)
    now = datetime.now(TZ)
    d, hhmm = now.date(), now.strftime("%H:%M")
    sent_today = {uid for (uid,) in db.execute(select(ReminderLog.user_id).where(ReminderLog.day == d)).all()}
    user_ids = {uid for (uid,) in db.execute(select(ScheduleItem.user_id).distinct()).all()} - sent_today

    sent = failed = 0
    for uid in user_ids:
        user = db.get(User, uid)
        items = planning.planned_items(db, user, d)
        if not items:
            continue
        # เวลาเตือนของวันนี้ = เวลาที่ตั้งไว้ของรายการแรก (ถ้าย้ายมาจากวันอื่น ใช้เวลาของวันเดิม)
        native = [it for it in items if it.weekday == d.weekday()]
        remind_at = (native or items)[0].remind_time
        if remind_at > hhmm:
            continue
        try:
            if not user.line_user_id.startswith("dev-"):
                ctx = planning.user_ctx(user)
                line_msg.send_line(user.line_user_id, reminder_text([planning.session_of(it, ctx) for it in items]))
            db.add(ReminderLog(user_id=uid, day=d))
            db.commit()
            sent += 1
        except Exception:
            db.rollback()
            failed += 1
    return {"sent": sent, "failed": failed}
