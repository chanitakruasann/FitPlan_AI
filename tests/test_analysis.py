from app import analysis as an, exercises as ex, optimizer
from tests.conftest import HIIT


def prog(target, level="beginner", goal="lose_weight", eq="none"):
    return {"segments": ex.generate_workout(target, level, goal, eq, None, 60)["segments"]}


def clip(segments):
    return {"segments": segments}


def texts(r):
    return " ".join(f["text"] for f in r["findings"])


def test_empty_week_has_no_score():
    r = an.analyze_week([[] for _ in range(7)], "beginner", "maintain", 60)
    assert r["score"] is None and r["findings"][0]["level"] == "info"


def test_users_example_flags_leg_days_too_close():
    # จันทร์ ขา, อังคาร อก, พุธ ขา, พฤหัส หลัง, ศุกร์ หน้าท้อง, เสาร์ HIIT, อาทิตย์ พัก
    week = [[prog("legs")], [prog("chest")], [prog("legs")], [prog("back")], [prog("core")], [clip(HIIT)], []]
    r = an.analyze_week(week, "beginner", "lose_weight", 60)
    t = texts(r)
    assert "วันจันทร์และวันพุธ" in t and "แนะนำปรับวันพุธเป็นส่วนบน" in t
    assert r["totals"]["group_days"]["lower"] == 2
    assert r["totals"]["rest_days"] == 1
    assert 0 < r["score"]["total"] < 100
    assert [p["key"] for p in r["score"]["parts"]] == ["balance", "rest", "intensity", "goal", "duration"]


def test_same_example_is_fine_for_intermediate():
    week = [[prog("legs", "intermediate")], [prog("chest", "intermediate")], [prog("legs", "intermediate")],
            [prog("back", "intermediate")], [prog("core", "intermediate")], [clip(HIIT)], []]
    r = an.analyze_week(week, "intermediate", "lose_weight", 60)
    assert "วันจันทร์และวันพุธ" not in texts(r)   # ห่าง 48 ชม. พอสำหรับระดับกลาง


def test_lower_upper_imbalance():
    week = [[prog("legs")], [], [prog("legs")], [], [prog("legs")], [prog("chest")], []]
    r = an.analyze_week(week, "intermediate", "maintain", 60)
    assert "ฝึกส่วนล่าง 3 ครั้ง แต่ส่วนบนเพียง 1 ครั้ง" in texts(r)


def test_too_many_hiit_for_beginner():
    week = [[clip(HIIT)], [], [clip(HIIT)], [], [clip(HIIT)], [], []]
    beginner = an.analyze_week(week, "beginner", "fitness", 60)
    advanced = an.analyze_week(week, "advanced", "fitness", 60)
    assert "อาจหนักเกินไปสำหรับผู้เริ่มต้น" in texts(beginner)
    intensity = lambda r: next(p["score"] for p in r["score"]["parts"] if p["key"] == "intensity")
    assert intensity(beginner) < intensity(advanced)


def test_consecutive_high_days_wrap_sunday_monday():
    week = [[clip(HIIT)], [], [], [], [], [], [clip(HIIT)]]
    assert "วันอาทิตย์กับวันจันทร์เป็นวันหนักติดกัน" in texts(an.analyze_week(week, "advanced", "fitness", 60))


def test_goal_changes_score():
    cardio_week = [[clip(HIIT)], [], [clip(HIIT)], [], [clip(HIIT)], [], []]
    goal = lambda g: next(p["score"] for p in an.analyze_week(cardio_week, "advanced", g, 60)["score"]["parts"]
                          if p["key"] == "goal")
    assert goal("fitness") > goal("build_muscle")


def test_optimizer_moves_skipped_session_and_keeps_a_rest_day():
    # พุธข้ามวันขา → ควรย้ายไปวันที่เหลือ (พฤหัส–อาทิตย์) และต้องเหลือวันพัก
    week = [[prog("legs")], [], [prog("legs")], [], [prog("chest")], [], []]
    p = optimizer.propose(week, skipped_day=2, first_candidate=3, ctx={
        "level": "intermediate", "goal": "maintain", "weight": 60})
    assert p["best"] is not None and p["best"]["day"] in (3, 5, 6)
    assert p["best"]["score"] > p["drop_score"]
    assert p["rest_after"] >= 1
    assert "ระบบเสนอย้าย" in optimizer.explain(p, ["วันฝึกขาและก้น"])


def test_optimizer_respects_rest_day_constraint():
    full = [[prog("core")]] * 6 + [[]]   # มีวันพักวันเดียวคือวันอาทิตย์
    p = optimizer.propose([list(d) for d in full], skipped_day=4, first_candidate=5, ctx={
        "level": "advanced", "goal": "maintain", "weight": 60})
    sunday = next(o for o in p["options"] if o["day"] == 6)
    assert not sunday["feasible"] and "วันพัก" in sunday["reason"]


def test_optimizer_with_no_days_left():
    week = [[], [], [], [], [], [], [prog("legs")]]
    p = optimizer.propose(week, skipped_day=6, first_candidate=7, ctx={
        "level": "beginner", "goal": "maintain", "weight": 60})
    assert p["best"] is None and "ไม่เหลือวันให้ชดเชย" in optimizer.explain(p, [])
