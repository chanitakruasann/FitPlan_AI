"""สูตรคำนวณข้อมูลร่างกาย — ทำในโค้ด ไม่ใช้ AI เพื่อให้ผลคงที่และอธิบายได้"""

ACTIVITY = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725}
ACTIVITY_LABELS = {
    "sedentary": "นั่งทำงานเป็นหลัก แทบไม่ได้ออกกำลังกาย",
    "light": "ขยับบ้าง ออกกำลังกาย 1–3 วัน/สัปดาห์",
    "moderate": "ออกกำลังกาย 3–5 วัน/สัปดาห์",
    "active": "ออกกำลังกายหนักเกือบทุกวัน",
}

LEVELS = {
    "beginner": {"label": "ผู้เริ่มต้น", "hint": "เพิ่งเริ่ม หรือออกกำลังกายสม่ำเสมอไม่ถึง 3 เดือน"},
    "intermediate": {"label": "ระดับกลาง", "hint": "ออกกำลังกายสม่ำเสมอ 3–12 เดือน ทำท่าพื้นฐานได้ถูกต้อง"},
    "advanced": {"label": "ระดับสูง", "hint": "ออกกำลังกายสม่ำเสมอมากกว่า 1 ปี"},
}

EQUIPMENT = {
    "none": "ไม่มีอุปกรณ์ (ใช้น้ำหนักตัว)",
    "dumbbell": "มีดัมเบลที่บ้าน",
    "gym": "เข้ายิมได้",
}

# เป้าหมาย: ส่วนต่างแคลอรี่จาก TDEE และการใช้ช่องจำนวนกิโล
GOALS = {
    "lose_weight":  {"label": "ลดน้ำหนัก",       "kcal_delta": -500, "kg": "required", "kg_label": "อยากลดกี่กิโล"},
    "lose_fat":     {"label": "ลดไขมัน",         "kcal_delta": -300, "kg": "required", "kg_label": "อยากลดกี่กิโล"},
    "build_muscle": {"label": "เพิ่มกล้ามเนื้อ",   "kcal_delta": 250,  "kg": "optional", "kg_label": "อยากเพิ่มกี่กิโล (ไม่บังคับ)"},
    "strength":     {"label": "เพิ่มความแข็งแรง",  "kcal_delta": 0,    "kg": None},
    "fitness":      {"label": "เพิ่มความฟิต",     "kcal_delta": 0,    "kg": None},
    "maintain":     {"label": "รักษาน้ำหนัก",     "kcal_delta": 0,    "kg": None},
}
LEGACY_GOALS = {"lose": "lose_weight", "gain": "build_muscle"}   # ค่าจากเวอร์ชันก่อน
LOSING_GOALS = {"lose_weight", "lose_fat"}

KCAL_PER_KG = 7700
MIN_AGE = 18


def goal_label(goal: str, kg_change: float | None) -> str:
    g = GOALS[goal]
    if g["kg"] and kg_change:
        return f"{g['label']} {kg_change:g} กก."
    return g["label"]


def bmi(weight_kg: float, height_cm: float) -> float:
    return weight_kg / (height_cm / 100) ** 2


def bmr(weight_kg: float, height_cm: float, age: int, sex: str) -> float:
    """Mifflin-St Jeor"""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if sex == "male" else base - 161


def validate_profile(height_cm, weight_kg, age, sex, activity, goal, kg_change, fitness_level, equipment) -> list[str]:
    errors = []
    if fitness_level not in LEVELS:
        errors.append("เลือกระดับการออกกำลังกายของคุณ")
    if equipment not in EQUIPMENT:
        errors.append("เลือกอุปกรณ์ที่มี")
    if height_cm is None or not 100 <= height_cm <= 250:
        errors.append("ส่วนสูงต้องอยู่ระหว่าง 100–250 ซม.")
    if weight_kg is None or not 30 <= weight_kg <= 300:
        errors.append("น้ำหนักต้องอยู่ระหว่าง 30–300 กก.")
    if age is None or not MIN_AGE <= age <= 100:
        errors.append(f"เว็บนี้ออกแบบสำหรับอายุ {MIN_AGE} ปีขึ้นไป")
    if sex not in ("male", "female"):
        errors.append("เลือกเพศ")
    if activity not in ACTIVITY:
        errors.append("เลือกระดับกิจกรรม")
    if goal not in GOALS:
        errors.append("เลือกเป้าหมาย")
        return errors

    need = GOALS[goal]["kg"]
    if need == "required" and (kg_change is None or not 0.5 <= kg_change <= 50):
        errors.append("จำนวนกิโลต้องอยู่ระหว่าง 0.5–50 กก.")
    elif need == "optional" and kg_change is not None and not 0.5 <= kg_change <= 30:
        errors.append("จำนวนกิโลที่อยากเพิ่มต้องอยู่ระหว่าง 0.5–30 กก.")
    elif goal in LOSING_GOALS and not errors:
        target_w = weight_kg - kg_change
        if bmi(target_w, height_cm) < 18.5:
            errors.append(
                f"น้ำหนักเป้าหมาย {target_w:.1f} กก. จะทำให้ BMI ต่ำกว่า 18.5 "
                "ซึ่งต่ำกว่าเกณฑ์ปกติ ลองลดจำนวนกิโลลง"
            )
    return errors


def daily_target(weight_kg, height_cm, age, sex, activity, goal, kg_change) -> dict:
    goal = LEGACY_GOALS.get(goal, goal)
    b = bmr(weight_kg, height_cm, age, sex)
    tdee = b * ACTIVITY[activity]
    target = tdee + GOALS[goal]["kcal_delta"]

    floor = max(b, 1500 if sex == "male" else 1200)   # ไม่ให้ต่ำกว่าเกณฑ์ปลอดภัย
    target = max(target, floor)

    diff = abs(target - tdee)
    weeks = None
    if GOALS[goal]["kg"] and kg_change and diff > 0:
        weeks = round(kg_change * KCAL_PER_KG / diff / 7, 1)

    return {
        "target": round(target),
        "tdee": round(tdee),
        "bmr": round(b),
        "bmi": round(bmi(weight_kg, height_cm), 1),
        "weeks": weeks,
    }
