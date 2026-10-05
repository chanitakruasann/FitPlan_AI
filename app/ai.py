"""เรียก Gemini API — ใช้ประเมินแคลอรี่อาหาร (และวิเคราะห์คลิป YouTube ในขั้นต่อไป)"""
import json

import requests

from . import config


class AIError(Exception):
    pass


class NotFoodError(AIError):
    pass


FOOD_PROMPT = """คุณเป็นนักโภชนาการ ประเมินพลังงานและสารอาหารของอาหารต่อไปนี้ \
ใน 1 หน่วยบริโภคที่คนไทยกินกันทั่วไป
อาหาร: {name}

ตอบเป็น JSON เท่านั้น ตามรูปแบบนี้:
{{"portion": "ขนาด 1 หน่วย เช่น 1 จาน (ประมาณ 350 กรัม)",
 "kcal": ตัวเลข, "protein_g": ตัวเลข, "carb_g": ตัวเลข, "fat_g": ตัวเลข,
 "confidence": "high" หรือ "medium" หรือ "low",
 "is_food": true หรือ false}}
ถ้าข้อความไม่ใช่ชื่ออาหารหรือเครื่องดื่ม ให้ is_food เป็น false"""


def _gemini_json(prompt: str, video_url: str | None = None, timeout: int = 60) -> dict:
    if not config.GEMINI_API_KEY:
        raise AIError("ยังไม่ได้ตั้งค่า GEMINI_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent"
    parts = [{"text": prompt}]
    gen_config = {"responseMimeType": "application/json", "temperature": 0.2}
    if video_url:
        # Gemini อ่านคลิป YouTube สาธารณะได้โดยตรง
        parts.insert(0, {"file_data": {"file_uri": video_url}})
        gen_config["mediaResolution"] = "MEDIA_RESOLUTION_LOW"  # ลดจำนวน token ต่อวินาทีของวิดีโอ
    body = {"contents": [{"parts": parts}], "generationConfig": gen_config}
    try:
        r = requests.post(url, headers={"x-goog-api-key": config.GEMINI_API_KEY}, json=body, timeout=timeout)
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(text)
    except (requests.RequestException, KeyError, IndexError, ValueError) as e:
        raise AIError(str(e)) from e


def _num(value, lo: float, hi: float) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if lo <= v <= hi else None


def estimate_food(name: str) -> dict:
    data = _gemini_json(FOOD_PROMPT.format(name=name))
    if data.get("is_food") is False:
        raise NotFoodError(name)
    kcal = _num(data.get("kcal"), 0, 3000)
    if kcal is None:
        raise AIError("ค่าแคลอรี่ที่ได้ไม่สมเหตุสมผล")
    confidence = data.get("confidence")
    return {
        "portion": str(data.get("portion") or "1 หน่วย")[:200],
        "kcal": round(kcal),
        "protein_g": _num(data.get("protein_g"), 0, 300),
        "carb_g": _num(data.get("carb_g"), 0, 500),
        "fat_g": _num(data.get("fat_g"), 0, 300),
        "confidence": confidence if confidence in ("high", "medium", "low") else "medium",
    }


class NotWorkoutError(AIError):
    pass


VIDEO_PROMPT = """ดูคลิปนี้แล้วแยกช่วงการออกกำลังกายตามลำดับเวลา
คลิปอาจพูดภาษาใดก็ได้ หรือมีแค่เพลงไม่มีคนพูด ให้ดูจากท่าทางในภาพเป็นหลัก \
ใช้เสียงพูดหรือข้อความบนจอเป็นข้อมูลเสริมเท่านั้น
แต่ละช่วงให้เลือก category จากรายการนี้เท่านั้น:
{categories}

และระบุกล้ามเนื้อหลักที่ช่วงนั้นใช้ (1–4 อย่าง) จากรายการนี้เท่านั้น:
{muscles}

ตอบเป็น JSON เท่านั้น ตามรูปแบบนี้:
{{"is_workout": true หรือ false,
 "total_minutes": ความยาวคลิปเป็นนาที,
 "segments": [
   {{"start": "mm:ss", "name": "ชื่อท่าเป็นภาษาไทย ตามด้วยชื่อสากลภาษาอังกฤษในวงเล็บ เช่น สควอท (Squat)",
     "category": "หนึ่งในรายการด้านบน", "minutes": ตัวเลข,
     "muscles": ["รหัสกล้ามเนื้อ เช่น quads", "glutes"]}}
 ]}}
กติกา:
- รวมท่าที่ต่อเนื่องและอยู่ category เดียวกันเป็นช่วงเดียวได้ ไม่เกิน 30 ช่วง
- ช่วงพักระหว่างเซ็ตให้ใช้ category "rest" ช่วงพูดอธิบายที่ไม่ได้ขยับให้ใช้ "rest" และ muscles เป็น []
- ช่วงวอร์มอัป ยืดเหยียด และคูลดาวน์ ให้ muscles เป็น []
- minutes ของทุกช่วงรวมกันต้องใกล้เคียง total_minutes
- ถ้าคลิปไม่ใช่คลิปให้ทำตามเพื่อออกกำลังกาย ให้ is_workout เป็น false และ segments เป็น []"""


def analyze_video(video_url: str, categories: dict) -> dict:
    from .exercises import MUSCLES

    cat_lines = "\n".join(f"- {k}: {v['label']}" for k, v in categories.items())
    muscle_lines = "\n".join(f"- {k}: {v}" for k, v in MUSCLES.items())
    data = _gemini_json(VIDEO_PROMPT.format(categories=cat_lines, muscles=muscle_lines),
                        video_url=video_url, timeout=180)
    if data.get("is_workout") is False:
        raise NotWorkoutError(video_url)

    segments = []
    for s in (data.get("segments") or [])[:30]:
        minutes = _num(s.get("minutes"), 0, 180)
        if not minutes:
            continue
        cat = s.get("category")
        cat = cat if cat in categories else "bodyweight_moderate"
        raw = s.get("muscles") if isinstance(s.get("muscles"), list) else []
        muscles = [] if cat == "rest" else list(dict.fromkeys(m for m in raw if m in MUSCLES))[:4]
        segments.append({
            "start": str(s.get("start") or "")[:8],
            "name": str(s.get("name") or "ออกกำลังกาย")[:100],
            "category": cat,
            "minutes": round(minutes, 1),
            "muscles": muscles,
        })
    if not segments:
        raise AIError("แยกช่วงการออกกำลังกายไม่ได้")

    total = _num(data.get("total_minutes"), 0, 600) or sum(s["minutes"] for s in segments)
    return {"segments": segments, "total_minutes": round(total, 1)}


def _suggestions(data: dict) -> list[str]:
    items = data.get("suggestions")
    if not isinstance(items, list):
        raise AIError("รูปแบบคำแนะนำไม่ถูกต้อง")
    out = [str(x).strip()[:300] for x in items if str(x).strip()][:5]
    if not out:
        raise AIError("ไม่มีคำแนะนำ")
    return out


ADVICE_PROMPT = """คุณเป็นเทรนเนอร์ ผู้ใช้เป็น{level} เป้าหมาย: {goal}
นี่คือตารางออกกำลังกายรายสัปดาห์ คะแนน และผลวิเคราะห์ที่ระบบคำนวณไว้แล้ว (ตัวเลขถูกต้อง ห้ามคำนวณใหม่):
{summary}

ตอบเป็นภาษาไทยที่เป็นกันเอง:
- "overview": สรุปภาพรวมตาราง 1–2 ประโยค เช่น ฝึกส่วนไหนกี่ครั้ง มีวันพักกี่วัน
- "suggestions": คำแนะนำ 2–4 ข้อ แต่ละข้อไม่เกิน 2 ประโยค เจาะจงว่าควรเปลี่ยนวันไหนเป็นอะไร \
(เช่น ส่วนบน, คาร์ดิโอเบา, Active Recovery) โดยอิงจากผลวิเคราะห์และเป้าหมาย
ถ้าตารางดีอยู่แล้ว ให้ชมสั้นๆ และแนะนำแค่จุดเล็กที่ปรับได้ ห้ามแนะนำอาหารเสริมหรือยา
ตอบเป็น JSON เท่านั้น: {{"overview": "...", "suggestions": ["ข้อ 1", "ข้อ 2"]}}"""


def schedule_advice(level: str, goal: str, summary: str) -> dict:
    data = _gemini_json(ADVICE_PROMPT.format(level=level, goal=goal, summary=summary))
    return {"overview": str(data.get("overview") or "").strip()[:400], "suggestions": _suggestions(data)}


PROGRESS_PROMPT = """คุณเป็นเทรนเนอร์ ผู้ใช้เป็น{level} เป้าหมาย: {goal}
นี่คือข้อมูลความก้าวหน้ารายสัปดาห์ที่ระบบคำนวณไว้แล้ว (เรียงจากเก่าไปใหม่ ตัวเลขถูกต้อง ห้ามคำนวณใหม่):
{summary}

ตอบเป็นภาษาไทยที่เป็นกันเอง:
- "overview": สรุปแนวโน้ม 2–3 ประโยค เช่น น้ำหนักเปลี่ยนอย่างไร ทำตามตารางได้เฉลี่ยกี่เปอร์เซ็นต์
- "suggestions": 1–3 ข้อ บอกว่าควรปรับตารางหรือไม่ ถ้ายังไม่จำเป็นให้บอกตรงๆ ว่ายังไม่ต้องปรับ
ถ้าน้ำหนักลดเร็วเกิน 1 กก./สัปดาห์ต่อเนื่อง ให้แนะนำให้ชะลอและกินให้พอ
ห้ามวินิจฉัยโรค ห้ามแนะนำอาหารเสริมหรือยา
ตอบเป็น JSON เท่านั้น: {{"overview": "...", "suggestions": ["ข้อ 1"]}}"""


def progress_insight(level: str, goal: str, summary: str) -> dict:
    data = _gemini_json(PROGRESS_PROMPT.format(level=level, goal=goal, summary=summary))
    return {"overview": str(data.get("overview") or "").strip()[:500], "suggestions": _suggestions(data)}
