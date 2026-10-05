from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import ai, calc, planning
from ..db import get_db
from ..deps import require_user_api, today
from ..models import User, WeeklyCheckin
from ..progress import streak, week_metrics

router = APIRouter(prefix="/api")
WEEKS = 8


def _weeks(db: Session, user: User) -> list[dict]:
    t = today()
    this = planning.week_start(t)
    return [week_metrics(db, user, this - timedelta(weeks=i), t) for i in reversed(range(WEEKS))]


@router.get("/progress")
def progress(user: User = Depends(require_user_api), db: Session = Depends(get_db)):
    weeks = _weeks(db, user)
    return {"weeks": weeks, "this_week": weeks[-1], "streak": streak(db, user, today()),
            "current_weight": user.weight_kg}


class CheckinIn(BaseModel):
    weight_kg: float = Field(ge=30, le=300)
    waist_cm: float | None = Field(default=None, ge=40, le=250)


@router.post("/checkin")
def checkin(body: CheckinIn, user: User = Depends(require_user_api), db: Session = Depends(get_db)):
    ws = planning.week_start(today())
    row = db.scalar(select(WeeklyCheckin).where(WeeklyCheckin.user_id == user.id, WeeklyCheckin.week_start == ws))
    if row:
        row.weight_kg, row.waist_cm = body.weight_kg, body.waist_cm
    else:
        db.add(WeeklyCheckin(user_id=user.id, week_start=ws, weight_kg=body.weight_kg, waist_cm=body.waist_cm))
    # น้ำหนักใหม่ → แคลอรี่ต่อวันและแคลที่เผาจากการออกกำลังกายเปลี่ยนตาม
    user.weight_kg = body.weight_kg
    user.daily_kcal_target = calc.daily_target(user.weight_kg, user.height_cm, user.age, user.sex,
                                               user.activity, user.goal, user.kg_change)["target"]
    db.commit()
    return {"ok": True, "daily_kcal_target": user.daily_kcal_target}


@router.post("/progress/insight")
def progress_insight(user: User = Depends(require_user_api), db: Session = Depends(get_db)):
    weeks = [w for w in _weeks(db, user) if w["planned_days"] or w["exercise_days"] or w["weight_kg"]]
    if len(weeks) < 2:
        raise HTTPException(422, "ต้องมีข้อมูลอย่างน้อย 2 สัปดาห์ก่อน ลองบันทึกน้ำหนักและออกกำลังกายต่ออีกสักสัปดาห์")
    lines = []
    for w in weeks:
        adherence = f" ({w['adherence']}%)" if w["adherence"] is not None else ""
        lines.append(
            f"สัปดาห์ {w['week_start']}: น้ำหนัก {w['weight_kg'] or '-'} กก., รอบเอว {w['waist_cm'] or '-'} ซม., "
            f"ทำตามแผน {w['done_planned_days']}/{w['planned_days']} วัน"
            f"{adherence}, "
            f"ออกกำลังกาย {w['exercise_days']} วัน, {w['minutes']} นาที, เผา {w['kcal']} แคล")
    ctx = planning.user_ctx(user)
    try:
        return ai.progress_insight(calc.LEVELS[ctx["level"]]["label"],
                                   calc.goal_label(user.goal, user.kg_change), "\n".join(lines))
    except ai.AIError:
        raise HTTPException(502, "วิเคราะห์ความก้าวหน้าไม่สำเร็จ ลองอีกครั้ง")
