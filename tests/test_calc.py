from app import calc


def ok(**kw):
    base = dict(height_cm=160, weight_kg=60, age=25, sex="female", activity="light",
                goal="lose_weight", kg_change=3, fitness_level="beginner", equipment="none")
    return calc.validate_profile(**{**base, **kw})


def test_bmr_female():
    assert calc.bmr(60, 160, 25, "female") == 1314


def test_goal_deltas():
    lose = calc.daily_target(70, 170, 30, "male", "moderate", "lose_weight", 5)
    fat = calc.daily_target(70, 170, 30, "male", "moderate", "lose_fat", 5)
    muscle = calc.daily_target(70, 170, 30, "male", "moderate", "build_muscle", None)
    fit = calc.daily_target(70, 170, 30, "male", "moderate", "fitness", None)
    assert lose["target"] == lose["tdee"] - 500
    assert fat["target"] == fat["tdee"] - 300
    assert muscle["target"] == muscle["tdee"] + 250 and muscle["weeks"] is None
    assert fit["target"] == fit["tdee"]


def test_legacy_goal_still_works():
    assert calc.daily_target(70, 170, 30, "male", "light", "lose", 5)["target"] > 0


def test_target_never_below_floor():
    r = calc.daily_target(45, 150, 60, "female", "sedentary", "lose_weight", 2)
    assert r["target"] >= max(r["bmr"], 1200)


def test_requires_level_and_equipment():
    errs = ok(fitness_level="", equipment="")
    assert any("ระดับ" in e for e in errs) and any("อุปกรณ์" in e for e in errs)


def test_kg_rules_per_goal():
    assert ok(goal="lose_fat", kg_change=None)            # ลดไขมันต้องใส่กิโล
    assert not ok(goal="build_muscle", kg_change=None)    # เพิ่มกล้ามไม่บังคับ
    assert not ok(goal="strength", kg_change=None)
    assert any("18.5" in e for e in ok(height_cm=170, weight_kg=55, kg_change=5))


def test_rejects_minor():
    assert ok(age=16)
