"""คลังท่าออกกำลังกาย กล้ามเนื้อ และตัวสร้างโปรแกรม ("วันนี้อยากออกขา")

ทุกอย่างคำนวณด้วยกฎ — จำนวนเซต/ครั้ง/เวลาพัก อิงช่วงที่แนะนำทั่วไปสำหรับแต่ละเป้าหมาย
(เช่นแนวทางของ ACSM: แข็งแรง 1–6 ครั้ง, กล้ามโต 8–12 ครั้ง, ความทนทาน 12–20 ครั้ง)
"""
from . import video as yt

# ---------- กล้ามเนื้อ ----------

MUSCLES = {
    "quads": "ต้นขาหน้า", "hamstrings": "ต้นขาหลัง", "glutes": "ก้น", "calves": "น่อง",
    "chest": "อก", "back": "หลัง", "shoulders": "ไหล่", "arms": "แขน",
    "abs": "หน้าท้อง", "obliques": "เอวด้านข้าง",
}
GROUPS = {
    "lower": {"label": "ส่วนล่าง", "en": "Lower Body", "muscles": ["quads", "hamstrings", "glutes", "calves"]},
    "upper": {"label": "ส่วนบน", "en": "Upper Body", "muscles": ["chest", "back", "shoulders", "arms"]},
    "core": {"label": "แกนกลาง", "en": "Core", "muscles": ["abs", "obliques"]},
}
MUSCLE_GROUP = {m: g for g, v in GROUPS.items() for m in v["muscles"]}


def groups_of(muscles) -> list[str]:
    return sorted({MUSCLE_GROUP[m] for m in muscles if m in MUSCLE_GROUP}, key=list(GROUPS).index)


def describe_muscles(muscles) -> str:
    """เช่น 'ส่วนล่าง (ต้นขาหน้า, ก้น), แกนกลาง (หน้าท้อง)'"""
    parts = []
    for g in groups_of(muscles):
        names = [MUSCLES[m] for m in GROUPS[g]["muscles"] if m in muscles]
        parts.append(f"{GROUPS[g]['label']} ({', '.join(names)})")
    return ", ".join(parts)


# ---------- เป้าหมายที่เลือกได้ ----------

TARGETS = {
    "legs":      {"label": "ขาและก้น",   "muscles": ["quads", "hamstrings", "glutes", "calves"]},
    "chest":     {"label": "อก",        "muscles": ["chest"], "fill": ["arms", "shoulders"]},
    "back":      {"label": "หลัง",       "muscles": ["back"], "fill": ["shoulders", "arms"]},
    "shoulders": {"label": "ไหล่",       "muscles": ["shoulders"], "fill": ["arms", "chest"]},
    "arms":      {"label": "แขน",       "muscles": ["arms"], "fill": ["shoulders", "chest"]},
    "core":      {"label": "หน้าท้อง",    "muscles": ["abs", "obliques"]},
    "upper":     {"label": "ร่างกายส่วนบน", "muscles": ["chest", "back", "shoulders", "arms"]},
    "full":      {"label": "ทั้งตัว",      "muscles": ["quads", "glutes", "hamstrings", "chest", "back", "shoulders", "abs"]},
}

# ---------- คลังท่า ----------
# equip: none < dumbbell < gym (ท่าที่ใช้อุปกรณ์น้อยกว่าใช้ได้เสมอ)
# level: 1 เริ่มต้น, 2 กลาง, 3 สูง (ระดับขั้นต่ำที่ควรทำ)
# pattern: กันไม่ให้เลือกท่าซ้ำแนวเดียวกันในโปรแกรมเดียว
# kind: reps หรือ time (วินาที)


def _ex(key, th, en, muscles, equip, level, pattern, compound, cue, kind="reps"):
    return {"key": key, "name": th, "en": en, "muscles": muscles, "equip": equip, "level": level,
            "pattern": pattern, "compound": compound, "cue": cue, "kind": kind}


EXERCISES = [
    # ส่วนล่าง
    _ex("squat", "สควอท", "Bodyweight Squat", ["quads", "glutes"], "none", 1, "squat", True,
        "เท้ากว้างเท่าไหล่ ดันสะโพกไปด้านหลัง เข่าชี้ตามปลายเท้า"),
    _ex("goblet_squat", "ก็อบเล็ตสควอท", "Goblet Squat", ["quads", "glutes"], "dumbbell", 1, "squat", True,
        "ถือดัมเบลชิดอก หลังตรง ย่อลงจนต้นขาขนานพื้น"),
    _ex("back_squat", "บาร์เบลสควอท", "Barbell Back Squat", ["quads", "glutes", "hamstrings"], "gym", 2, "squat", True,
        "บาร์วางบนบ่า เกร็งท้อง ย่อลงช้าๆ ดันพื้นขึ้น"),
    _ex("leg_press", "เลกเพรส", "Leg Press", ["quads", "glutes"], "gym", 1, "squat_machine", True,
        "ไม่ล็อกเข่าตอนเหยียดสุด หลังแนบพนัก"),
    _ex("reverse_lunge", "ลันจ์ถอยหลัง", "Reverse Lunge", ["quads", "glutes"], "none", 1, "lunge", True,
        "ก้าวถอยหลัง ย่อจนเข่าหลังเกือบแตะพื้น สลับข้าง (นับข้างละครั้ง)"),
    _ex("split_squat", "บัลแกเรียนสปลิทสควอท", "Bulgarian Split Squat", ["quads", "glutes"], "none", 2, "lunge", True,
        "วางหลังเท้าบนเก้าอี้ ย่อขาหน้าลงตรงๆ ทำครบข้างหนึ่งแล้วค่อยสลับ"),
    _ex("step_up", "ก้าวขึ้นเก้าอี้", "Step-up", ["quads", "glutes"], "none", 1, "step", True,
        "ใช้เก้าอี้หรือขั้นบันไดที่มั่นคง ดันส้นเท้าขึ้น สลับข้าง"),
    _ex("rdl", "ดัมเบลโรมาเนียนเดดลิฟต์", "Dumbbell Romanian Deadlift", ["hamstrings", "glutes"], "dumbbell", 1, "hinge", True,
        "เข่างอเล็กน้อย พับสะโพกไปด้านหลัง หลังตรงตลอด"),
    _ex("glute_bridge", "กลูตบริดจ์", "Glute Bridge", ["glutes", "hamstrings"], "none", 1, "bridge", False,
        "นอนหงาย ชันเข่า ยกสะโพกจนลำตัวเป็นเส้นตรง บีบก้นค้างไว้ 1 วินาที"),
    _ex("single_leg_bridge", "กลูตบริดจ์ขาเดียว", "Single-leg Glute Bridge", ["glutes", "hamstrings"], "none", 2, "bridge", False,
        "เหยียดขาข้างหนึ่งขึ้น ยกสะโพกด้วยขาอีกข้าง สลับข้าง"),
    _ex("leg_curl", "เลกเคิร์ล", "Lying Leg Curl", ["hamstrings"], "gym", 1, "curl_leg", False,
        "งอเข่าดึงขึ้นช้าๆ ไม่ยกสะโพก"),
    _ex("jump_squat", "จัมพ์สควอท", "Jump Squat", ["quads", "glutes", "calves"], "none", 2, "jump", True,
        "ย่อแล้วกระโดดขึ้น ลงพื้นเบาๆ ด้วยเข่างอ"),
    _ex("wall_sit", "นั่งพิงกำแพง", "Wall Sit", ["quads"], "none", 1, "iso_leg", False,
        "หลังแนบกำแพง ต้นขาขนานพื้น เข่าอยู่เหนือข้อเท้า", kind="time"),
    _ex("calf_raise", "เขย่งปลายเท้า", "Calf Raise", ["calves"], "none", 1, "calf", False,
        "เขย่งขึ้นสุด ค้าง 1 วินาที แล้วลดส้นเท้าลงช้าๆ"),
    # อก
    _ex("incline_pushup", "วิดพื้นมือวางบนโต๊ะ", "Incline Push-up", ["chest", "arms", "shoulders"], "none", 1, "push_incline_easy", True,
        "วางมือบนโต๊ะหรือขอบเตียงที่มั่นคง ลำตัวตรง ลดอกเข้าหาขอบ"),
    _ex("knee_pushup", "วิดพื้นคุกเข่า", "Knee Push-up", ["chest", "arms", "shoulders"], "none", 1, "push_h", True,
        "คุกเข่า ลำตัวตรงจากเข่าถึงหัว ลดอกลงใกล้พื้น"),
    _ex("pushup", "วิดพื้น", "Push-up", ["chest", "arms", "shoulders"], "none", 2, "push_h", True,
        "มือกว้างกว่าไหล่เล็กน้อย เกร็งท้อง ลำตัวตรงทั้งขึ้นและลง"),
    _ex("decline_pushup", "วิดพื้นเท้าสูง", "Decline Push-up", ["chest", "shoulders", "arms"], "none", 3, "push_incline", True,
        "วางเท้าบนเก้าอี้ ลำตัวตรง ลดอกลงช้าๆ"),
    _ex("db_press", "ดัมเบลเชสต์เพรส", "Dumbbell Chest Press", ["chest", "arms", "shoulders"], "dumbbell", 1, "push_h_load", True,
        "นอนบนม้านั่งหรือพื้น ดันดัมเบลขึ้นเหนืออก ลดลงช้าๆ"),
    _ex("bench_press", "บาร์เบลเบนช์เพรส", "Barbell Bench Press", ["chest", "arms", "shoulders"], "gym", 2, "push_h_load", True,
        "สะบักบีบเข้าหากัน ลดบาร์ลงแตะกลางอก ควรมีคนช่วยดูเมื่อยกหนัก"),
    _ex("chest_press_machine", "เครื่องเชสต์เพรส", "Machine Chest Press", ["chest", "arms"], "gym", 1, "push_h_machine", True,
        "ปรับเบาะให้ด้ามจับอยู่ระดับกลางอก ดันออกไม่ล็อกข้อศอก"),
    _ex("db_fly", "ดัมเบลฟลาย", "Dumbbell Fly", ["chest"], "dumbbell", 2, "fly", False,
        "ข้อศอกงอเล็กน้อย กางแขนลงจนรู้สึกตึงที่อก แล้วหุบขึ้น"),
    # หลัง
    _ex("superman", "ซูเปอร์แมน", "Superman", ["back", "glutes"], "none", 1, "back_ext", False,
        "นอนคว่ำ ยกแขนและขาขึ้นพร้อมกัน ค้าง 2 วินาที"),
    _ex("bird_dog", "เบิร์ดด็อก", "Bird Dog", ["back", "glutes", "abs"], "none", 1, "bird_dog", False,
        "คุกเข่าสี่ขา เหยียดแขนและขาฝั่งตรงข้ามให้ขนานพื้น ค้าง 2 วินาที สลับข้าง"),
    _ex("prone_yt", "ยกแขนท่า Y-T นอนคว่ำ", "Prone Y-T Raise", ["back", "shoulders"], "none", 1, "back_raise", False,
        "นอนคว่ำ ยกแขนเป็นตัว Y แล้วตัว T บีบสะบัก"),
    _ex("db_row", "ดัมเบลโรว์ทีละข้าง", "One-arm Dumbbell Row", ["back", "arms"], "dumbbell", 1, "row", True,
        "มือและเข่าข้างหนึ่งวางบนม้านั่ง ดึงดัมเบลเข้าหาสะโพก นับข้างละครั้ง"),
    _ex("bent_row", "ดัมเบลเบนต์โอเวอร์โรว์", "Bent-over Dumbbell Row", ["back", "arms"], "dumbbell", 2, "row2", True,
        "พับสะโพก หลังตรง ดึงดัมเบลสองข้างเข้าหาเอว"),
    _ex("lat_pulldown", "แลตพูลดาวน์", "Lat Pulldown", ["back", "arms"], "gym", 1, "pull_v", True,
        "ดึงบาร์ลงหน้าอก อกเปิด ไม่เอนตัวไปด้านหลังมาก"),
    _ex("cable_row", "เคเบิลโรว์", "Seated Cable Row", ["back", "arms"], "gym", 1, "row", True,
        "นั่งหลังตรง ดึงด้ามจับเข้าหาท้อง บีบสะบัก"),
    _ex("pullup", "ดึงข้อ", "Pull-up", ["back", "arms"], "gym", 3, "pull_v", True,
        "ห้อยตัวเต็มแขน ดึงจนคางพ้นบาร์ ลงช้าๆ"),
    # ไหล่
    _ex("pike_pushup", "ไพค์พุชอัพ", "Pike Push-up", ["shoulders", "arms"], "none", 2, "push_v", True,
        "ยกสะโพกสูงเป็นรูปตัว V ลดศีรษะลงระหว่างมือ"),
    _ex("db_shoulder_press", "ดัมเบลโชว์เดอร์เพรส", "Dumbbell Shoulder Press", ["shoulders", "arms"], "dumbbell", 1, "push_v", True,
        "นั่งหรือยืนหลังตรง ดันดัมเบลขึ้นเหนือศีรษะ ไม่แอ่นหลัง"),
    _ex("lateral_raise", "ยกดัมเบลด้านข้าง", "Lateral Raise", ["shoulders"], "dumbbell", 1, "raise", False,
        "ยกแขนออกด้านข้างถึงระดับไหล่ ใช้น้ำหนักเบา"),
    # แขน
    _ex("bench_dip", "ดิปบนเก้าอี้", "Bench Dip", ["arms", "shoulders"], "none", 1, "triceps", False,
        "มือจับขอบเก้าอี้ ลดตัวลงจนข้อศอกประมาณ 90 องศา"),
    _ex("diamond_pushup", "วิดพื้นมือชิด", "Diamond Push-up", ["arms", "chest"], "none", 3, "triceps_push", True,
        "มือชิดกันเป็นรูปเพชรใต้อก ข้อศอกแนบลำตัว"),
    _ex("db_curl", "ดัมเบลเคิร์ล", "Dumbbell Curl", ["arms"], "dumbbell", 1, "biceps", False,
        "ข้อศอกแนบลำตัว ยกดัมเบลขึ้น ลดลงช้าๆ"),
    _ex("db_triceps_ext", "ดัมเบลไทรเซ็ปเหนือศีรษะ", "Overhead Triceps Extension", ["arms"], "dumbbell", 1, "triceps", False,
        "จับดัมเบลสองมือเหนือศีรษะ งอข้อศอกลดลงหลังศีรษะ"),
    _ex("cable_pushdown", "เคเบิลไทรเซ็ปพุชดาวน์", "Cable Triceps Pushdown", ["arms"], "gym", 1, "triceps_cable", False,
        "ข้อศอกแนบลำตัว กดด้ามจับลงจนแขนเหยียด"),
    # แกนกลาง
    _ex("plank", "แพลงก์", "Plank", ["abs"], "none", 1, "plank", False,
        "ข้อศอกอยู่ใต้ไหล่ ลำตัวตรง ไม่ปล่อยสะโพกตก", kind="time"),
    _ex("dead_bug", "เดดบั๊ก", "Dead Bug", ["abs"], "none", 1, "anti_ext", False,
        "นอนหงาย หลังส่วนล่างแนบพื้น เหยียดแขนขาฝั่งตรงข้ามสลับกัน"),
    _ex("bicycle_crunch", "ไบซิเคิลครันช์", "Bicycle Crunch", ["abs", "obliques"], "none", 1, "crunch_rot", False,
        "บิดศอกเข้าหาเข่าฝั่งตรงข้ามช้าๆ นับข้างละครั้ง"),
    _ex("russian_twist", "รัสเซียนทวิสต์", "Russian Twist", ["obliques", "abs"], "none", 1, "rotation", False,
        "นั่งเอนหลังเล็กน้อย บิดลำตัวซ้ายขวา นับข้างละครั้ง"),
    _ex("side_plank", "ไซด์แพลงก์", "Side Plank", ["obliques", "abs"], "none", 2, "side_plank", False,
        "ข้อศอกใต้ไหล่ ยกสะโพกให้ลำตัวตรง ทำข้างละครั้ง", kind="time"),
    _ex("leg_raise", "ยกขานอนหงาย", "Lying Leg Raise", ["abs"], "none", 2, "leg_raise", False,
        "หลังส่วนล่างแนบพื้น ยกขาขึ้นช้าๆ ลดลงโดยไม่ให้ส้นแตะพื้น"),
    _ex("mountain_climber", "เมาน์เทนไคลม์เบอร์", "Mountain Climber", ["abs", "shoulders"], "none", 1, "climber", False,
        "ท่าวิดพื้น ดึงเข่าเข้าหาอกสลับเร็วๆ สะโพกนิ่ง", kind="time"),
]
EX_BY_KEY = {e["key"]: e for e in EXERCISES}
EQUIP_RANK = {"none": 0, "dumbbell": 1, "gym": 2}
LEVEL_RANK = {"beginner": 1, "intermediate": 2, "advanced": 3}

# ---------- การกำหนดเซตและจำนวนครั้ง ----------

PRESCRIPTION = {
    # sets ตามระดับ (เริ่มต้น, กลาง, สูง), ช่วงจำนวนครั้ง, พักระหว่างเซต (วินาที)
    "strength":     {"sets": (3, 4, 5), "reps": (5, 8),   "rest": 120, "style": "แบบเซตปกติ เน้นน้ำหนักที่ท้าทาย"},
    "build_muscle": {"sets": (3, 3, 4), "reps": (8, 12),  "rest": 75,  "style": "แบบเซตปกติ เน้นให้กล้ามเนื้อล้าใกล้ครั้งสุดท้าย"},
    "lose_weight":  {"sets": (2, 3, 3), "reps": (12, 15), "rest": 40,  "style": "แบบวงจร พักสั้น เพื่อให้หัวใจเต้นเร็วต่อเนื่อง"},
    "lose_fat":     {"sets": (2, 3, 4), "reps": (10, 15), "rest": 45,  "style": "แบบวงจร พักสั้น และคงแรงต้านไว้เพื่อรักษากล้ามเนื้อ"},
    "fitness":      {"sets": (2, 3, 3), "reps": (12, 15), "rest": 40,  "style": "แบบวงจร ผสมแรงและความทนทาน"},
    "maintain":     {"sets": (2, 3, 3), "reps": (10, 12), "rest": 60,  "style": "แบบเซตปกติ ระดับปานกลาง"},
}
PLYO = {"jump", "climber"}   # ท่ากระโดด/คาร์ดิโอ ไม่ใส่ในโปรแกรมเน้นแรงหรือกล้าม
HOLD_SECONDS = {"beginner": 20, "intermediate": 30, "advanced": 45}
MAX_EXERCISES = {"beginner": 4, "intermediate": 5, "advanced": 6}
MIN_EXERCISES = 3
DEFAULT_MINUTES = {"beginner": 30, "intermediate": 45, "advanced": 60}
WARMUP_MIN, COOLDOWN_MIN = 5, 5
SECONDS_PER_REP = 3.5


def _pick(target_muscles: list[str], level: str, equipment: str, goal: str, limit: int) -> list[dict]:
    lv, eq = LEVEL_RANK[level], EQUIP_RANK[equipment]
    heavy_goal = goal in ("strength", "build_muscle")
    pool = [e for e in EXERCISES
            if e["level"] <= lv and EQUIP_RANK[e["equip"]] <= eq and set(e["muscles"]) & set(target_muscles)
            and not (heavy_goal and e["pattern"] in PLYO)]
    chosen, covered, patterns = [], set(), set()
    while pool and len(chosen) < limit:
        def score(e):
            primary = e["muscles"][0] in target_muscles
            new = len(set(e["muscles"]) & set(target_muscles) - covered)
            return (new * 3 + primary * 3 + e["compound"] * 2
                    + (EQUIP_RANK[e["equip"]] if heavy_goal else 0)   # เป้ากล้าม/แรง ใช้อุปกรณ์ที่มีให้เต็มที่
                    + e["level"] * 0.5)                                # ท่าที่ตรงระดับมากกว่า
        best = max(pool, key=score)
        pool.remove(best)
        if best["pattern"] in patterns:
            continue
        chosen.append(best)
        patterns.add(best["pattern"])
        covered |= set(best["muscles"])
    # ท่าใหญ่ก่อน ท่าเล็กทีหลัง (ลำดับที่ปลอดภัยและได้ผลกว่า)
    return sorted(chosen, key=lambda e: (not e["compound"], e["muscles"][0] in GROUPS["core"]["muscles"]))


def _exercise_seconds(item: dict) -> float:
    work = item["seconds"] if item["seconds"] else item["reps"] * SECONDS_PER_REP
    return item["sets"] * work + (item["sets"] - 1) * item["rest_sec"] + 60   # +1 นาทีเปลี่ยนท่า/จัดอุปกรณ์


def generate_workout(target: str, level: str, goal: str, equipment: str,
                     minutes: int | None, weight_kg: float) -> dict:
    goal = goal if goal in PRESCRIPTION else "maintain"
    rx = PRESCRIPTION[goal]
    li = LEVEL_RANK[level] - 1
    minutes = minutes or DEFAULT_MINUTES[level]
    budget = (minutes - WARMUP_MIN - COOLDOWN_MIN) * 60

    lo, hi = rx["reps"]
    # เป้าแข็งแรง: ยิ่งชำนาญยิ่งยกหนักขึ้นด้วยจำนวนครั้งน้อยลง / เป้าอื่น: ยิ่งชำนาญยิ่งทำได้มากครั้งขึ้น
    steps = (hi, (lo + hi) // 2, lo) if goal == "strength" else (lo, (lo + hi) // 2, hi)
    reps = steps[li]
    picked = _pick(TARGETS[target]["muscles"], level, equipment, goal, MAX_EXERCISES[level])
    fill = TARGETS[target].get("fill")
    if fill and len(picked) < MIN_EXERCISES:   # ท่าของส่วนนั้นมีน้อย (เช่น ไม่มีอุปกรณ์) เติมท่าของกล้ามเนื้อที่ทำงานร่วมกัน
        used_patterns = {e["pattern"] for e in picked}
        extra = [e for e in _pick(fill, level, equipment, goal, MAX_EXERCISES[level])
                 if e["pattern"] not in used_patterns and e not in picked]
        picked += extra[:MIN_EXERCISES - len(picked)]

    target_muscles = TARGETS[target]["muscles"]
    items, used = [], 0.0
    for e in picked:
        # นับเฉพาะกล้ามเนื้อเป้าหมายของวันนั้น (กล้ามเนื้อช่วยไม่นับ) เพื่อไม่ให้การวิเคราะห์ความสมดุลเพี้ยน
        focus = [m for m in e["muscles"] if m in target_muscles] or e["muscles"][:1]
        item = {
            "key": e["key"], "name": e["name"], "en": e["en"], "muscles": focus, "cue": e["cue"],
            "sets": rx["sets"][li], "rest_sec": rx["rest"],
            "reps": None if e["kind"] == "time" else reps,
            "seconds": HOLD_SECONDS[level] if e["kind"] == "time" else None,
            "equip": e["equip"],
        }
        need = _exercise_seconds(item)
        if items and used + need > budget:
            # ลดเซตลงก่อนตัดท่าทิ้ง
            if item["sets"] > 2:
                item["sets"] -= 1
                need = _exercise_seconds(item)
            if used + need > budget:
                break
        items.append(item)
        used += need

    work_min = round(used / 60)
    total_min = WARMUP_MIN + work_min + COOLDOWN_MIN
    segments = [{"start": "", "name": "วอร์มอัป", "category": "warmup_stretch", "minutes": WARMUP_MIN, "muscles": []}]
    for it in items:
        cat = ("core_abs" if set(it["muscles"]) <= set(GROUPS["core"]["muscles"])
               else "weight_training" if it["equip"] != "none" else "bodyweight_moderate")
        segments.append({"start": "", "name": it["name"], "category": cat,
                         "minutes": round(_exercise_seconds(it) / 60, 1), "muscles": it["muscles"]})
    segments.append({"start": "", "name": "ยืดเหยียด", "category": "cooldown", "minutes": COOLDOWN_MIN, "muscles": []})

    all_muscles = sorted({m for it in items for m in it["muscles"]}, key=list(MUSCLES).index)
    return {
        "target": target,
        "title": f"วันฝึก{TARGETS[target]['label']}",
        "style": rx["style"],
        "exercises": items,
        "minutes": total_min,
        "kcal": round(yt.video_kcal(segments, weight_kg)),
        "intensity": yt.intensity_of(segments),
        "muscles": all_muscles,
        "muscle_text": describe_muscles(all_muscles),
        "segments": segments,
    }


def recent_overlap(target: str, recent: dict[int, set[str]]) -> list[tuple[int, list[str]]]:
    """recent = {จำนวนวันที่ผ่านมา: กล้ามเนื้อที่ฝึก} → [(days_ago, กล้ามเนื้อที่ซ้ำ)]"""
    want = set(TARGETS[target]["muscles"]) - set(GROUPS["core"]["muscles"])   # แกนกลางฟื้นตัวเร็ว ฝึกถี่ได้
    out = []
    for days_ago in sorted(recent):
        same = [m for m in MUSCLES if m in want and m in recent[days_ago]]
        if same:
            out.append((days_ago, same))
    return out
