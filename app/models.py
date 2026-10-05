from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # เข้าสู่ระบบได้ 2 ทาง: LINE (line_user_id) หรือ ชื่อผู้ใช้ + รหัสผ่าน มีอย่างใดอย่างหนึ่งหรือทั้งคู่
    line_user_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(30))
    username_key: Mapped[str | None] = mapped_column(String(30), unique=True, index=True)   # ตัวพิมพ์เล็ก ใช้ค้นหา
    password_hash: Mapped[str | None] = mapped_column(String(200))
    failed_logins: Mapped[int] = mapped_column(default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    display_name: Mapped[str] = mapped_column(String(100))
    picture_url: Mapped[str | None] = mapped_column(String(500))

    # ข้อมูลร่างกาย (ว่างจนกว่าจะกรอกหน้า onboarding)
    height_cm: Mapped[float | None]
    weight_kg: Mapped[float | None]
    age: Mapped[int | None]
    sex: Mapped[str | None] = mapped_column(String(10))          # male / female
    activity: Mapped[str | None] = mapped_column(String(20))     # sedentary / light / moderate / active
    goal: Mapped[str | None] = mapped_column(String(20))         # ดู calc.GOALS
    kg_change: Mapped[float | None]
    daily_kcal_target: Mapped[int | None]
    fitness_level: Mapped[str | None] = mapped_column(String(20))  # beginner / intermediate / advanced
    equipment: Mapped[str | None] = mapped_column(String(20))      # none / dumbbell / gym

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Food(Base):
    """แคชผลประเมินจาก AI — ชื่อเดิมไม่ต้องเรียก AI ซ้ำ"""
    __tablename__ = "foods"

    id: Mapped[int] = mapped_column(primary_key=True)
    name_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    portion: Mapped[str] = mapped_column(String(200))
    kcal: Mapped[float]
    protein_g: Mapped[float | None]
    carb_g: Mapped[float | None]
    fat_g: Mapped[float | None]
    confidence: Mapped[str] = mapped_column(String(10), default="medium")
    source: Mapped[str] = mapped_column(String(10), default="ai")


class FoodLog(Base):
    __tablename__ = "food_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    food_id: Mapped[int | None] = mapped_column(ForeignKey("foods.id"))
    name: Mapped[str] = mapped_column(String(100))
    servings: Mapped[float]
    kcal: Mapped[int]
    eaten_on: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Video(Base):
    """ผลวิเคราะห์คลิป YouTube — ใช้ร่วมกันทุกคน (ไม่ขึ้นกับน้ำหนักผู้ใช้)"""
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(300), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    segments: Mapped[list] = mapped_column(JSON, default=list)
    total_minutes: Mapped[float] = mapped_column(default=0)
    version: Mapped[int] = mapped_column(default=1)   # รุ่นของการวิเคราะห์ (ดู video.ANALYSIS_VERSION)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScheduleItem(Base):
    __tablename__ = "schedule_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    weekday: Mapped[int]                                          # 0 = จันทร์ ... 6 = อาทิตย์
    remind_time: Mapped[str] = mapped_column(String(5))           # "HH:MM"
    video_id: Mapped[int | None] = mapped_column(ForeignKey("videos.id"))
    program: Mapped[str | None] = mapped_column(String(20))       # โปรแกรมสร้างท่าอัตโนมัติ (exercises.TARGETS)
    program_minutes: Mapped[int | None]
    note: Mapped[str | None] = mapped_column(String(200))
    last_sent_date: Mapped[date | None] = mapped_column(Date)

    user: Mapped[User] = relationship()
    video: Mapped[Video | None] = relationship()


class WorkoutLog(Base):
    __tablename__ = "workout_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    video_id: Mapped[int | None] = mapped_column(ForeignKey("videos.id"))
    title: Mapped[str | None] = mapped_column(String(300))
    minutes: Mapped[float | None]
    muscles: Mapped[list | None] = mapped_column(JSON)
    source: Mapped[str | None] = mapped_column(String(10))   # video / program / plan
    kcal: Mapped[float]
    done_on: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserVideo(Base):
    """คลังคลิปของแต่ละคน — คลิปที่เคยวิเคราะห์ ใช้เลือกใส่ตาราง"""
    __tablename__ = "user_videos"
    __table_args__ = (UniqueConstraint("user_id", "video_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DayStatus(Base):
    """ผลของแต่ละวันตามตาราง: done = ทำสำเร็จ, skipped = ข้าม"""
    __tablename__ = "day_status"
    __table_args__ = (UniqueConstraint("user_id", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    day: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10))


class ScheduleMove(Base):
    """การย้ายรายการในตารางเฉพาะสัปดาห์เดียว (ไม่แก้ตารางหลัก)"""
    __tablename__ = "schedule_moves"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("schedule_items.id", ondelete="CASCADE"))
    week_start: Mapped[date] = mapped_column(Date, index=True)
    to_weekday: Mapped[int]


class ReminderLog(Base):
    __tablename__ = "reminder_logs"
    __table_args__ = (UniqueConstraint("user_id", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    day: Mapped[date] = mapped_column(Date)


class WeeklyCheckin(Base):
    """บันทึกร่างกายรายสัปดาห์ (สัปดาห์เริ่มวันจันทร์)"""
    __tablename__ = "weekly_checkins"
    __table_args__ = (UniqueConstraint("user_id", "week_start"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    week_start: Mapped[date] = mapped_column(Date)
    weight_kg: Mapped[float]
    waist_cm: Mapped[float | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
