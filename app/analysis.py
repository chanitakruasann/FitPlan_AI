"""วิเคราะห์และให้คะแนนตารางออกกำลังกายรายสัปดาห์ (Workout Schedule Score)

ข้อมูลเข้า: ตาราง 7 วัน แต่ละวันมีหลาย session แต่ละ session คือรายการ segment
(segment มาจากผลวิเคราะห์คลิป หรือโปรแกรมที่ระบบสร้าง: category, minutes, muscles)

คะแนนมี 5 ด้าน แต่ละด้าน 0–100 แล้วถ่วงน้ำหนักรวมเป็นคะแนนเดียว
เกณฑ์อ้างอิงแนวทางทั่วไปของ WHO / ACSM และปรับตามระดับผู้ใช้กับเป้าหมาย
"""
from . import exercises as ex, video as yt

DAY_NAMES = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]

CARDIO = {"low_impact_cardio", "aerobic_dance", "hiit", "jump_rope", "bodyweight_vigorous"}
STRENGTH = {"bodyweight_moderate", "weight_training", "bodyweight_vigorous", "core_abs"}
FLEX = {"warmup_stretch", "yoga", "pilates", "cooldown"}

MUSCLE_MIN = 3          # นาทีขั้นต่ำต่อกล้ามเนื้อ ถึงนับว่าวันนั้นฝึกกล้ามเนื้อนั้น
STRENGTH_DAY_MIN = 10
HIGH_DAY_VIGOROUS_MIN = 10

LEVEL_RULES = {
    #               วันหนักสูงสุด  ห่างกันขั้นต่ำ(วัน) ของกล้ามเนื้อเดิม  นาที/สัปดาห์   นาที/วันสูงสุด  วันพักที่เหมาะ
    "beginner":     {"max_high": 2, "min_diff": 3, "week": (90, 200),  "day_max": 60,  "rest": (2, 3), "max_streak": 4},
    "intermediate": {"max_high": 3, "min_diff": 2, "week": (150, 300), "day_max": 90,  "rest": (1, 3), "max_streak": 5},
    "advanced":     {"max_high": 4, "min_diff": 2, "week": (200, 450), "day_max": 120, "rest": (1, 2), "max_streak": 6},
}
GOAL_RULES = {
    # cardio = นาทีคาร์ดิโอเทียบเท่าระดับปานกลาง/สัปดาห์ (นาทีหนักนับ 2 เท่า)
    "lose_weight":  {"cardio": 250, "strength_days": 2, "group_freq": 1, "cardio_weight": .65},
    "lose_fat":     {"cardio": 150, "strength_days": 3, "group_freq": 2, "cardio_weight": .45},
    "build_muscle": {"cardio": 75,  "strength_days": 3, "group_freq": 2, "cardio_weight": .25, "cardio_max": 300},
    "strength":     {"cardio": 75,  "strength_days": 3, "group_freq": 2, "cardio_weight": .25, "cardio_max": 300},
    "fitness":      {"cardio": 150, "strength_days": 2, "group_freq": 1, "cardio_weight": .55, "high_min": 1},
    "maintain":     {"cardio": 150, "strength_days": 2, "group_freq": 1, "cardio_weight": .5},
}
PARTS = {
    "balance":   {"label": "ความสมดุลกล้ามเนื้อ", "weight": .25},
    "rest":      {"label": "วันพักและการฟื้นตัว", "weight": .20},
    "intensity": {"label": "ความหนัก", "weight": .20},
    "goal":      {"label": "ความเหมาะสมกับเป้าหมาย", "weight": .20},
    "duration":  {"label": "ระยะเวลารวม", "weight": .15},
}


def _clamp(x: float) -> int:
    return int(round(max(0, min(100, x))))


def _names(days) -> str:
    days = list(days)
    names = [f"วัน{DAY_NAMES[d]}" for d in days]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + f" และ{names[-1]}"


def day_stats(sessions: list[dict], weight_kg: float) -> dict:
    moderate = vigorous = strength = flex = active = kcal = 0.0
    muscle_min: dict[str, float] = {}
    for sess in sessions:
        for s in sess["segments"]:
            cat, m = s["category"], s["minutes"]
            if cat == "rest":
                continue
            met = yt.met_of(cat)
            active += m
            kcal += yt.segment_kcal(cat, m, weight_kg)
            if cat in CARDIO:
                if met >= yt.VIGOROUS_MET:
                    vigorous += m
                else:
                    moderate += m
            if cat in STRENGTH:
                strength += m
                for mu in s.get("muscles") or []:
                    muscle_min[mu] = muscle_min.get(mu, 0) + m
            if cat in FLEX:
                flex += m
    trained = sorted((mu for mu, m in muscle_min.items() if m >= MUSCLE_MIN), key=list(ex.MUSCLES).index)
    is_rest = active == 0
    return {
        "active_min": round(active), "moderate_min": round(moderate), "vigorous_min": round(vigorous),
        "strength_min": round(strength), "flex_min": round(flex), "kcal": round(kcal),
        "muscles": trained, "groups": ex.groups_of(trained),
        "is_rest": is_rest,
        "is_high": vigorous >= HIGH_DAY_VIGOROUS_MIN,
        "is_strength": strength >= STRENGTH_DAY_MIN,
        "intensity": None if is_rest else yt.intensity_of([s for sess in sessions for s in sess["segments"]]),
    }


def _circular_pairs(days: list[int]):
    """คู่วันที่ติดกันในลำดับวนรอบสัปดาห์ เช่น [0, 2, 6] → (0,2), (2,6), (6,0)"""
    if len(days) < 2:
        return []
    out = []
    for i, d in enumerate(days):
        nxt = days[(i + 1) % len(days)]
        diff = (nxt - d) % 7 or 7
        out.append((d, nxt, diff))
    return out


def _longest_training_streak(days: list[dict]) -> int:
    training = [not d["is_rest"] for d in days]
    if all(training):
        return 7
    best = run = 0
    for t in training + training:   # วนรอบ อาทิตย์ต่อจันทร์
        run = run + 1 if t else 0
        best = max(best, run)
    return min(best, 7)


def analyze_week(week: list[list[dict]], level: str, goal: str, weight_kg: float) -> dict:
    level = level if level in LEVEL_RULES else "beginner"
    goal = goal if goal in GOAL_RULES else "maintain"
    L, G = LEVEL_RULES[level], GOAL_RULES[goal]
    days = [day_stats(week[i], weight_kg) for i in range(7)]

    moderate = sum(d["moderate_min"] for d in days)
    vigorous = sum(d["vigorous_min"] for d in days)
    cardio_eq = moderate + 2 * vigorous
    active_total = sum(d["active_min"] for d in days)
    strength_days = [i for i, d in enumerate(days) if d["is_strength"]]
    rest_days = [i for i, d in enumerate(days) if d["is_rest"]]
    high_days = [i for i, d in enumerate(days) if d["is_high"]]
    group_days = {g: [i for i, d in enumerate(days) if g in d["groups"]] for g in ex.GROUPS}

    totals = {
        "active_min": active_total, "cardio_equivalent_min": cardio_eq,
        "moderate_min": moderate, "vigorous_min": vigorous,
        "strength_days": len(strength_days), "rest_days": len(rest_days), "high_days": len(high_days),
        "flex_min": sum(d["flex_min"] for d in days), "kcal": sum(d["kcal"] for d in days),
        "group_days": {g: len(v) for g, v in group_days.items()},
        "cardio_target": G["cardio"], "strength_target": G["strength_days"],
    }
    if active_total == 0:
        return {"days": days, "totals": totals, "score": None, "findings": [
            {"level": "info", "part": None, "text": "ยังไม่มีอะไรในตาราง เพิ่มคลิปหรือโปรแกรมลงแต่ละวันเพื่อเริ่มวิเคราะห์"}]}

    findings: list[dict] = []

    def note(level_, part, text):
        findings.append({"level": level_, "part": part, "text": text})

    # ---------- 1) ความสมดุลกล้ามเนื้อ ----------
    balance = 100.0
    lower, upper, core = (len(group_days[g]) for g in ("lower", "upper", "core"))
    if not strength_days:
        balance = 30
        note("warn", "balance", "ยังไม่มีวันฝึกกล้ามเนื้อเลย ลองเพิ่มโปรแกรมส่วนล่างหรือส่วนบนอย่างน้อยอย่างละ 1 วัน")
    else:
        for g, n in (("lower", lower), ("upper", upper)):
            if n < G["group_freq"]:
                balance -= 15 * (G["group_freq"] - n)
                note("warn", "balance",
                     f"{ex.GROUPS[g]['label']} ({ex.GROUPS[g]['en']}) ฝึก {n} ครั้งต่อสัปดาห์ "
                     f"สำหรับเป้าหมายนี้ควรฝึกอย่างน้อย {G['group_freq']} ครั้ง")
        if abs(lower - upper) >= 2:
            more, less = ("lower", "upper") if lower > upper else ("upper", "lower")
            balance -= 20
            note("warn", "balance",
                 f"สัปดาห์นี้ฝึก{ex.GROUPS[more]['label']} {max(lower, upper)} ครั้ง "
                 f"แต่{ex.GROUPS[less]['label']}เพียง {min(lower, upper)} ครั้ง ตารางอาจไม่สมดุล")
        chest = sum("chest" in d["muscles"] for d in days)
        back = sum("back" in d["muscles"] for d in days)
        if abs(chest - back) >= 2:
            balance -= 8
            note("warn", "balance", f"ฝึกอก {chest} ครั้ง แต่หลัง {back} ครั้ง ควรให้ใกล้เคียงกันเพื่อท่าทางที่ดี")
        if core == 0:
            balance -= 8
            note("warn", "balance", "ยังไม่มีการฝึกแกนกลางลำตัว ลองเพิ่มท่าหน้าท้องสั้นๆ ท้ายวันใดวันหนึ่ง")

        # การฟื้นตัว: กล้ามเนื้อเดียวกัน (ยกเว้นแกนกลาง) ต้องห่างกันอย่างน้อย min_diff วัน
        clashes: dict[tuple[int, int], list[str]] = {}
        for mu in ex.MUSCLES:
            if ex.MUSCLE_GROUP[mu] == "core":
                continue
            mdays = [i for i, d in enumerate(days) if mu in d["muscles"]]
            for a, b, diff in _circular_pairs(mdays):
                if diff < L["min_diff"]:
                    clashes.setdefault((a, b), []).append(mu)
        for (a, b), mus in clashes.items():
            balance -= 12
            group = ex.MUSCLE_GROUP[mus[0]]
            other = "ส่วนบน (Upper Body)" if group == "lower" else "ส่วนล่าง (Lower Body)"
            gap = (b - a) % 7 - 1
            gap_text = "ติดกัน" if gap == 0 else f"ห่างกันแค่ {gap} วัน"
            need = L["min_diff"] - 1
            note("warn", "balance",
                 f"{ex.describe_muscles(mus)} ถูกฝึก{_names([a])}และ{_names([b])} {gap_text} "
                 f"สำหรับ{_level_label(level)}ควรพักกล้ามเนื้อเดิมอย่างน้อย {need} วัน "
                 f"แนะนำปรับ{_names([b])}เป็น{other} หรือ Active Recovery")
        if balance >= 90 and strength_days:
            note("good", "balance",
                 f"ฝึกส่วนล่าง {lower} ครั้ง ส่วนบน {upper} ครั้ง แกนกลาง {core} ครั้ง สมดุลดี")

    # ---------- 2) วันพักและการฟื้นตัว ----------
    lo, hi = L["rest"]
    r = len(rest_days)
    if r == 0:
        rest = 30
        note("warn", "rest", "ไม่มีวันพักเลย ควรมีอย่างน้อย 1 วันต่อสัปดาห์ให้ร่างกายฟื้นตัว")
    elif r < lo:
        rest = 75
        note("warn", "rest", f"มีวันพัก {r} วัน สำหรับ{_level_label(level)}แนะนำ {lo}–{hi} วัน")
    elif r <= hi:
        rest = 100
        note("good", "rest", f"มีวันพัก {r} วัน ({_names(rest_days)}) เหมาะกับระดับของคุณ")
    else:
        rest = max(40, 100 - 15 * (r - hi))
        note("warn", "rest", f"มีวันพัก {r} วัน ค่อนข้างมาก ลองเพิ่มกิจกรรมเบาๆ เช่น เดินหรือโยคะ 1–2 วัน")
    streak = _longest_training_streak(days)
    if r and streak > L["max_streak"]:
        rest -= 15
        note("warn", "rest", f"มีวันออกกำลังกายต่อเนื่อง {streak} วันโดยไม่พัก ลองแทรกวันพักไว้ตรงกลาง")

    # ---------- 3) ความหนัก ----------
    intensity = 100.0
    h = len(high_days)
    if h > L["max_high"]:
        intensity -= 25 * (h - L["max_high"])
        note("warn", "intensity",
             f"มีวันหนัก (เช่น HIIT) {h} วันต่อสัปดาห์ อาจหนักเกินไปสำหรับ{_level_label(level)} "
             f"แนะนำไม่เกิน {L['max_high']} วัน")
    for a, b, diff in _circular_pairs(high_days):
        if diff == 1:
            intensity -= 20
            note("warn", "intensity",
                 f"{_names([a])}กับ{_names([b])}เป็นวันหนักติดกัน ลองเปลี่ยนวันใดวันหนึ่งเป็นคาร์ดิโอเบาหรือโยคะ")
    if G.get("high_min") and h < G["high_min"]:
        intensity -= 15
        note("warn", "intensity", "เป้าหมายเพิ่มความฟิตควรมีวันที่หนัก (เช่น HIIT) อย่างน้อย 1 วันต่อสัปดาห์")
    if intensity >= 90:
        note("good", "intensity", f"ความหนักเหมาะสม มีวันหนัก {h} วัน และไม่ติดกัน" if h else "ความหนักเหมาะสม")

    # ---------- 4) ความเหมาะสมกับเป้าหมาย ----------
    cw = G["cardio_weight"]
    cardio_ratio = min(1, cardio_eq / G["cardio"])
    strength_ratio = min(1, len(strength_days) / G["strength_days"])
    goal_score = 100 * (cw * cardio_ratio + (1 - cw) * strength_ratio)
    gl = ex_goal_label(goal)
    if cardio_eq < G["cardio"]:
        note("warn", "goal",
             f"คาร์ดิโอรวม {cardio_eq} นาที (นับนาทีหนักเป็น 2 เท่า) เป้าหมาย{gl}ควรได้ประมาณ "
             f"{G['cardio']} นาทีต่อสัปดาห์ ขาดอีก {G['cardio'] - cardio_eq} นาที")
    if len(strength_days) < G["strength_days"]:
        note("warn", "goal",
             f"มีวันฝึกกล้ามเนื้อ {len(strength_days)} วัน เป้าหมาย{gl}ควรมีอย่างน้อย {G['strength_days']} วัน")
    if G.get("cardio_max") and cardio_eq > G["cardio_max"]:
        goal_score -= 15
        note("warn", "goal", f"คาร์ดิโอ {cardio_eq} นาทีค่อนข้างมากสำหรับเป้าหมาย{gl} อาจกระทบการฟื้นตัวของกล้ามเนื้อ")
    if goal_score >= 95:
        note("good", "goal", f"สัดส่วนคาร์ดิโอและการฝึกกล้ามเนื้อเหมาะกับเป้าหมาย{gl}")

    # ---------- 5) ระยะเวลารวม ----------
    wlo, whi = L["week"]
    if active_total < wlo:
        duration = 100 * active_total / wlo
        note("warn", "duration", f"ออกกำลังกายรวม {active_total} นาทีต่อสัปดาห์ น้อยกว่าช่วงที่แนะนำ ({wlo}–{whi} นาที)")
    elif active_total <= whi:
        duration = 100
        note("good", "duration", f"ออกกำลังกายรวม {active_total} นาทีต่อสัปดาห์ อยู่ในช่วงที่เหมาะ ({wlo}–{whi} นาที)")
    else:
        duration = max(50, 100 - (active_total - whi) / whi * 100)
        note("warn", "duration", f"ออกกำลังกายรวม {active_total} นาทีต่อสัปดาห์ มากกว่าช่วงที่แนะนำ ({wlo}–{whi} นาที)")
    long_days = [i for i, d in enumerate(days) if d["active_min"] > L["day_max"]]
    if long_days:
        duration -= 10 * len(long_days)
        note("warn", "duration", f"{_names(long_days)}ยาวเกิน {L['day_max']} นาที ลองแบ่งไปวันอื่น")
    no_flex = [i for i, d in enumerate(days) if not d["is_rest"] and d["flex_min"] == 0]
    if no_flex:
        note("warn", "duration", f"{_names(no_flex)}ไม่มีช่วงวอร์มอัปหรือยืดเหยียด ควรเพิ่ม 5 นาทีก่อนและหลังออกกำลังกาย")

    parts = {"balance": _clamp(balance), "rest": _clamp(rest), "intensity": _clamp(intensity),
             "goal": _clamp(goal_score), "duration": _clamp(duration)}
    total = _clamp(sum(parts[k] * PARTS[k]["weight"] for k in parts))
    # เรียง: ควรปรับก่อน แล้วค่อยสิ่งที่ดี
    findings.sort(key=lambda f: {"warn": 0, "info": 1, "good": 2}[f["level"]])
    return {
        "days": days, "totals": totals, "findings": findings,
        "score": {"total": total, "parts": [{"key": k, "label": PARTS[k]["label"], "score": v} for k, v in parts.items()]},
    }


def _level_label(level: str) -> str:
    from .calc import LEVELS
    return LEVELS[level]["label"]


def ex_goal_label(goal: str) -> str:
    from .calc import GOALS
    return GOALS[goal]["label"]
