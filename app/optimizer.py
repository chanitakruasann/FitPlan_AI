"""ปรับตารางอัตโนมัติเมื่อผู้ใช้ข้ามวัน (Schedule Optimization)

ปัญหา: วันที่ s ไม่ได้ออกกำลังกาย ควรย้าย session ของวันนั้นไปวันไหนในสัปดาห์เดียวกัน หรือไม่ต้องชดเชย
ตัวแปรตัดสินใจ: วันปลายทาง d ∈ {วันที่ยังมาไม่ถึง} ∪ {ไม่ชดเชย}
ฟังก์ชันเป้าหมาย: คะแนนตารางของสัปดาห์ (analysis.analyze_week) — ยิ่งสูงยิ่งดี
ข้อจำกัด:
  1. ต้องเหลือวันพักอย่างน้อย 1 วัน (ถ้าตารางเดิมมีวันพัก)
  2. นาทีออกกำลังกายของวันปลายทางต้องไม่เกินเพดานต่อวันของระดับผู้ใช้
วิธีหา: ค้นหาครบทุกทางเลือก (exhaustive search) เพราะมีไม่เกิน 7 ทางเลือก จึงได้คำตอบที่ดีที่สุดแน่นอน
"""
from . import analysis as an


def _rest_days(week, skipped_day: int) -> int:
    """วันพักตามแผน (ไม่นับวันที่ข้าม เพราะไม่ใช่วันพักที่ตั้งใจไว้)"""
    return sum(1 for i, day in enumerate(week) if i != skipped_day and not any(
        s["minutes"] > 0 and s["category"] != "rest" for sess in day for s in sess["segments"]))


def _day_minutes(day) -> float:
    return sum(s["minutes"] for sess in day for s in sess["segments"] if s["category"] != "rest")


def propose(week: list[list[dict]], skipped_day: int, first_candidate: int, ctx: dict) -> dict:
    level, goal, weight = ctx["level"], ctx["goal"], ctx["weight"]
    day_max = an.LEVEL_RULES.get(level, an.LEVEL_RULES["beginner"])["day_max"]

    def score(w):
        res = an.analyze_week(w, level, goal, weight)
        return res["score"]["total"] if res["score"] else 0

    moving = week[skipped_day]
    original_score = score(week)
    base = [list(day) for day in week]
    base[skipped_day] = []
    base_score = score(base)
    keep_rest = _rest_days(week, skipped_day) >= 1

    options = []
    for d in range(first_candidate, 7):
        if d == skipped_day:
            continue
        trial = [list(day) for day in base]
        trial[d] = trial[d] + moving
        reason = None
        if keep_rest and _rest_days(trial, skipped_day) < 1:
            reason = "ทำให้ไม่เหลือวันพัก"
        elif _day_minutes(trial[d]) > day_max:
            reason = f"วันนั้นจะยาวเกิน {day_max} นาที"
        options.append({"day": d, "day_name": an.DAY_NAMES[d], "score": score(trial), "feasible": reason is None,
                        "reason": reason, "was_rest": not base[d]})

    feasible = [o for o in options if o["feasible"]]
    best = max(feasible, key=lambda o: (o["score"], -o["day"]), default=None)
    if best and best["score"] <= base_score:
        best = None   # ย้ายแล้วไม่ดีขึ้น → ไม่ต้องชดเชย
    return {
        "skipped_day": skipped_day, "skipped_name": an.DAY_NAMES[skipped_day],
        "original_score": original_score, "drop_score": base_score,
        "best": best, "options": options,
        "rest_after": _rest_days(base if best is None else [day + (moving if i == best["day"] else [])
                                                           for i, day in enumerate(base)], skipped_day),
    }


def explain(p: dict, titles: list[str]) -> str:
    what = ", ".join(titles) if titles else "โปรแกรมของวันนั้น"
    if not p["options"]:
        return f"วัน{p['skipped_name']}ไม่ได้ออกกำลังกายตามแผน และสัปดาห์นี้ไม่เหลือวันให้ชดเชยแล้ว เริ่มใหม่สัปดาห์หน้าได้เลย"
    if p["best"] is None:
        return (f"วัน{p['skipped_name']}ไม่ได้ออกกำลังกายตามแผน ระบบลองย้ายไปทุกวันที่เหลือแล้ว "
                f"แต่ไม่มีวันไหนทำให้ตารางดีขึ้นโดยยังพักได้พอ จึงแนะนำให้ข้าม {what} ไปเลย "
                f"(คะแนนสัปดาห์นี้ {p['drop_score']}/100)")
    b = p["best"]
    rest = f"และยังคงวันพักไว้ {p['rest_after']} วัน" if p["rest_after"] else ""
    return (f"วัน{p['skipped_name']}ไม่ได้ออกกำลังกายตามแผน ระบบเสนอย้าย {what} ไปวัน{b['day_name']} {rest} "
            f"คะแนนสัปดาห์นี้จะเป็น {b['score']}/100 (ถ้าไม่ชดเชยจะเหลือ {p['drop_score']}/100)").replace("  ", " ")
