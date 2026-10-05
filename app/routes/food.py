from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import ai
from ..db import get_db
from ..deps import require_user_api, today
from ..models import Food, FoodLog, User

router = APIRouter(prefix="/api/food")


class FoodQuery(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class FoodLogIn(BaseModel):
    food_id: int | None = None
    name: str | None = Field(default=None, max_length=100)
    servings: float = Field(gt=0, le=10)
    kcal_per_serving: float | None = Field(default=None, ge=0, le=5000)


def food_dict(f: Food) -> dict:
    return {"id": f.id, "name": f.name, "portion": f.portion, "kcal": f.kcal,
            "protein_g": f.protein_g, "carb_g": f.carb_g, "fat_g": f.fat_g, "confidence": f.confidence}


def name_key(name: str) -> str:
    return " ".join(name.lower().split())


@router.post("/estimate")
def food_estimate(q: FoodQuery, user: User = Depends(require_user_api), db: Session = Depends(get_db)):
    key = name_key(q.name)
    food = db.scalar(select(Food).where(Food.name_key == key))
    if food:
        return food_dict(food)
    try:
        data = ai.estimate_food(q.name.strip())
    except ai.NotFoodError:
        raise HTTPException(422, "ไม่พบอาหารชื่อนี้ ลองพิมพ์ชื่อเมนูให้ชัดขึ้น")
    except ai.AIError:
        raise HTTPException(502, "ประเมินแคลอรี่ไม่สำเร็จ ใส่ค่าแคลอรี่เองด้านล่างได้")
    food = Food(name_key=key, name=q.name.strip(), source="ai", **data)
    db.add(food)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        food = db.scalar(select(Food).where(Food.name_key == key))
    return food_dict(food)


@router.post("/log")
def food_log(entry: FoodLogIn, user: User = Depends(require_user_api), db: Session = Depends(get_db)):
    if entry.food_id is not None:
        food = db.get(Food, entry.food_id)
        if not food:
            raise HTTPException(404, "ไม่พบอาหารนี้")
        name = food.name
        per = entry.kcal_per_serving if entry.kcal_per_serving is not None else food.kcal
    else:
        if not entry.name or not entry.name.strip() or entry.kcal_per_serving is None:
            raise HTTPException(422, "ใส่ชื่ออาหารและแคลอรี่")
        name, per = entry.name.strip(), entry.kcal_per_serving
    log = FoodLog(user_id=user.id, food_id=entry.food_id, name=name,
                  servings=entry.servings, kcal=round(per * entry.servings), eaten_on=today())
    db.add(log)
    db.commit()
    return {"id": log.id}


@router.delete("/log/{log_id}")
def food_log_delete(log_id: int, user: User = Depends(require_user_api), db: Session = Depends(get_db)):
    log = db.get(FoodLog, log_id)
    if not log or log.user_id != user.id:
        raise HTTPException(404, "ไม่พบรายการนี้")
    db.delete(log)
    db.commit()
    return {"ok": True}
