"""จัดการลิงก์ YouTube และคำนวณแคลอรี่จากผลวิเคราะห์คลิป"""
import re
from urllib.parse import parse_qs, urlparse

import requests

# ค่า MET โดยประมาณ อ้างอิงแนวทางจาก Compendium of Physical Activities
# AI เลือกได้เฉพาะหมวดในตารางนี้ ตัวเลขแคลอรี่จึงคำนวณในโค้ดเสมอ
CATEGORIES = {
    "warmup_stretch":      {"label": "วอร์มอัป/ยืดเหยียด",        "met": 2.5},
    "yoga":                {"label": "โยคะ",                     "met": 2.5},
    "pilates":             {"label": "พิลาทิส",                   "met": 3.0},
    "core_abs":            {"label": "บริหารหน้าท้อง/แกนกลาง",     "met": 3.8},
    "bodyweight_moderate": {"label": "บอดี้เวทระดับปานกลาง",        "met": 3.8},
    "weight_training":     {"label": "เวทเทรนนิ่ง (ดัมเบล/บาร์)",    "met": 5.0},
    "low_impact_cardio":   {"label": "คาร์ดิโอแรงกระแทกต่ำ",        "met": 4.0},
    "aerobic_dance":       {"label": "แอโรบิก/เต้น",               "met": 6.5},
    "bodyweight_vigorous": {"label": "บอดี้เวทหนัก (เช่น burpee)",   "met": 8.0},
    "hiit":                {"label": "HIIT",                      "met": 8.0},
    "jump_rope":           {"label": "กระโดดเชือก",               "met": 10.0},
    "rest":                {"label": "พักระหว่างเซ็ต",              "met": 1.3},
    "cooldown":            {"label": "คูลดาวน์",                   "met": 2.3},
}
DEFAULT_CATEGORY = "bodyweight_moderate"

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_video_id(url: str) -> str | None:
    """รองรับ watch?v=, youtu.be/, shorts/, embed/, live/ และ m.youtube.com"""
    url = url.strip()
    if not re.match(r"^https?://", url):
        url = "https://" + url
    p = urlparse(url)
    host = (p.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    vid = None
    if host == "youtu.be":
        vid = p.path.lstrip("/").split("/")[0]
    elif host in ("youtube.com", "music.youtube.com"):
        if p.path == "/watch":
            vid = parse_qs(p.query).get("v", [None])[0]
        else:
            parts = p.path.strip("/").split("/")
            if len(parts) >= 2 and parts[0] in ("shorts", "embed", "live", "v"):
                vid = parts[1]
    return vid if vid and _ID_RE.match(vid) else None


def canonical_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def fetch_title(video_id: str) -> str | None:
    """เช็กว่าคลิปเปิดสาธารณะผ่าน oEmbed (ฟรี ไม่ต้องใช้ key) — คืน None ถ้าเปิดไม่ได้"""
    try:
        r = requests.get("https://www.youtube.com/oembed",
                         params={"url": canonical_url(video_id), "format": "json"}, timeout=10)
        if r.status_code != 200:
            return None
        return r.json().get("title")
    except (requests.RequestException, ValueError):
        return None


def segment_kcal(category: str, minutes: float, weight_kg: float) -> float:
    met = CATEGORIES.get(category, CATEGORIES[DEFAULT_CATEGORY])["met"]
    return met * weight_kg * (minutes / 60)


def video_kcal(segments: list[dict], weight_kg: float) -> float:
    return sum(segment_kcal(s["category"], s["minutes"], weight_kg) for s in segments)


# ---------- ระดับความหนัก ----------
# คำนวณจาก MET ไม่ใช่ให้ AI เดา: ใช้นิยาม MET มาตรฐาน (เบา < 3, ปานกลาง 3–5.9, หนัก ≥ 6)
# ปรับให้นับช่วงหนักที่ยาวพอ (≥ 10 นาที) เป็นคลิปหนักแม้ค่าเฉลี่ยจะถูกช่วงวอร์มอัปดึงลง

INTENSITY = {
    "low": {"label": "เบา", "en": "Low"},
    "moderate": {"label": "ปานกลาง", "en": "Moderate"},
    "high": {"label": "หนัก", "en": "High"},
}
VIGOROUS_MET = 6.0
ANALYSIS_VERSION = 2   # v2 = มีข้อมูลกล้ามเนื้อรายช่วง


def met_of(category: str) -> float:
    return CATEGORIES.get(category, CATEGORIES[DEFAULT_CATEGORY])["met"]


def intensity_of(segments: list[dict]) -> str:
    active = [s for s in segments if s["category"] != "rest"]
    work = [s for s in active if s["category"] not in ("warmup_stretch", "cooldown")]
    active = work or active   # ไม่นับวอร์มอัป/คูลดาวน์ ยกเว้นทั้งคลิปเป็นการยืดเหยียด
    minutes = sum(s["minutes"] for s in active)
    if not minutes:
        return "low"
    avg = sum(met_of(s["category"]) * s["minutes"] for s in active) / minutes
    vigorous = sum(s["minutes"] for s in active if met_of(s["category"]) >= VIGOROUS_MET)
    if vigorous >= 10 or avg >= VIGOROUS_MET:
        return "high"
    return "moderate" if avg >= 3.5 else "low"
