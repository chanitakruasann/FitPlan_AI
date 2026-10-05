"""วิเคราะห์ตารางออกกำลังกายรายสัปดาห์ด้วยกฎที่อธิบายได้

อ้างอิงคำแนะนำของ WHO สำหรับผู้ใหญ่:
- แอโรบิกระดับปานกลาง 150–300 นาที/สัปดาห์ หรือระดับหนัก 75–150 นาที (นาทีหนักนับเป็น 2 เท่า)
- ฝึกกล้ามเนื้ออย่างน้อย 2 วัน/สัปดาห์
"""
from . import video as yt

DAY_NAMES = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]

CARDIO = {"low_impact_cardio", "aerobic_dance", "hiit", "jump_rope", "bodyweight_vigorous"}
STRENGTH = {"bodyweight_moderate", "weight_training", "bodyweight_vigorous", "core_abs"}
FLEX = {"warmup_stretch", "yoga", "pilates", "cooldown"}

VIGOROUS_MET = 6.0           # MET ≥ 6 นับเป็นระดับหนัก
STRENGTH_DAY_MIN = 10        # ฝึกกล้ามเนื้อ ≥ 10 นาที นับเป็นวันฝึกกล้ามเนื้อ
HARD_DAY_VIGOROUS_MIN = 10   # ระดับหนัก ≥ 10 นาที นับเป็นวันหนัก
WHO_MIN, WHO_MAX = 150, 300


def day_stats(videos: list[list[dict]], weight_kg: float) -> dict:
    """videos = รายการ segments ของแต่ละคลิปในวันนั้น"""
    moderate = vigorous = strength = flex = active = kcal = 0.0
    for segments in videos:
        for s in segments:
            cat, m = s["category"], s["minutes"]
            if cat == "rest":
                continue
            met = yt.CATEGORIES.get(cat, yt.CATEGORIES[yt.DEFAULT_CATEGORY])["met"]
            active += m
            kcal += yt.segment_kcal(cat, m, weight_kg)
            if cat in CARDIO:
                if met >= VIGOROUS_MET:
                    vigorous += m
                else:
                    moderate += m
            if cat in STRENGTH:
                strength += m
            if cat in FLEX:
                flex += m
    return {
        "active_min": round(active), "moderate_min": round(moderate), "vigorous_min": round(vigorous),
        "strength_min": round(strength), "flex_min": round(flex), "kcal": round(kcal),
        "is_rest": active == 0,
        "is_hard": vigorous >= HARD_DAY_VIGOROUS_MIN,
        "is_strength": strength >= STRENGTH_DAY_MIN,
    }


def analyze_week(week: list[list[list[dict]]], weight_kg: float) -> dict:
    """week[วัน 0–6] = รายการ segments ของแต่ละคลิป"""
    days = [day_stats(week[i], weight_kg) for i in range(7)]
    moderate = sum(d["moderate_min"] for d in days)
    vigorous = sum(d["vigorous_min"] for d in days)
    equivalent = moderate + 2 * vigorous
    strength_days = [i for i, d in enumerate(days) if d["is_strength"]]
    rest_days = [i for i, d in enumerate(days) if d["is_rest"]]
    hard_pairs = [(i, (i + 1) % 7) for i in range(7) if days[i]["is_hard"] and days[(i + 1) % 7]["is_hard"]]
    active_total = sum(d["active_min"] for d in days)

    totals = {
        "active_min": active_total,
        "cardio_equivalent_min": equivalent,
        "moderate_min": moderate,
        "vigorous_min": vigorous,
        "strength_days": len(strength_days),
        "rest_days": len(rest_days),
        "flex_min": sum(d["flex_min"] for d in days),
        "kcal": sum(d["kcal"] for d in days),
    }

    findings: list[dict] = []
    if active_total == 0:
        findings.append({"level": "info", "text": "ยังไม่มีคลิปในตาราง เพิ่มคลิปลงแต่ละวันเพื่อเริ่มวิเคราะห์"})
        return {"days": days, "totals": totals, "findings": findings}

    # 1) คาร์ดิโอเทียบเกณฑ์ WHO
    if equivalent < WHO_MIN:
        findings.append({"level": "warn", "text":
            f"คาร์ดิโอรวม {equivalent} นาทีต่อสัปดาห์ (นับนาทีระดับหนักเป็น 2 เท่า) "
            f"ยังไม่ถึง {WHO_MIN} นาทีตามคำแนะนำของ WHO ขาดอีกประมาณ {WHO_MIN - equivalent} นาที"})
    elif equivalent <= WHO_MAX:
        findings.append({"level": "good", "text":
            f"คาร์ดิโอรวม {equivalent} นาทีต่อสัปดาห์ อยู่ในช่วง {WHO_MIN}–{WHO_MAX} นาทีที่ WHO แนะนำ"})
    else:
        findings.append({"level": "good", "text":
            f"คาร์ดิโอรวม {equivalent} นาทีต่อสัปดาห์ เกินช่วงที่ WHO แนะนำ ได้ประโยชน์เพิ่ม "
            "แต่ควรมีวันพักให้ร่างกายฟื้นตัว"})

    # 2) วันฝึกกล้ามเนื้อ
    if len(strength_days) < 2:
        findings.append({"level": "warn", "text":
            f"มีวันฝึกกล้ามเนื้อ {len(strength_days)} วัน WHO แนะนำอย่างน้อย 2 วันต่อสัปดาห์ "
            "ลองเพิ่มคลิปบอดี้เวทหรือเวทเทรนนิ่ง"})
    else:
        names = ", ".join(DAY_NAMES[i] for i in strength_days)
        findings.append({"level": "good", "text": f"ฝึกกล้ามเนื้อ {len(strength_days)} วัน ({names}) ครบตามคำแนะนำ"})

    # 3) วันหนักติดกัน
    for a, b in hard_pairs:
        findings.append({"level": "warn", "text":
            f"วัน{DAY_NAMES[a]}กับวัน{DAY_NAMES[b]}เป็นวันหนักติดกัน "
            "ลองเปลี่ยนวันใดวันหนึ่งเป็นคลิปเบา เช่น โยคะหรือคาร์ดิโอแรงกระแทกต่ำ"})

    # 4) วันพัก
    if not rest_days:
        findings.append({"level": "warn", "text": "ไม่มีวันพักเลย ควรมีอย่างน้อย 1 วันต่อสัปดาห์ให้กล้ามเนื้อฟื้นตัว"})
    else:
        findings.append({"level": "good", "text": f"มีวันพัก {len(rest_days)} วัน"})

    # 5) วอร์มอัป/ยืดเหยียด
    no_flex_days = [i for i, d in enumerate(days) if not d["is_rest"] and d["flex_min"] == 0]
    if no_flex_days:
        names = ", ".join(DAY_NAMES[i] for i in no_flex_days)
        findings.append({"level": "warn", "text":
            f"วัน{names} ไม่มีช่วงวอร์มอัปหรือยืดเหยียดเลย ลองเพิ่มคลิปยืดเหยียดสั้นๆ ก่อนหรือหลังออกกำลังกาย"})

    return {"days": days, "totals": totals, "findings": findings}
