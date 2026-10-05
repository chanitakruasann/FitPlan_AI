import pytest

from app import exercises as ex


@pytest.mark.parametrize("level", ["beginner", "intermediate", "advanced"])
@pytest.mark.parametrize("equipment", ["none", "dumbbell", "gym"])
@pytest.mark.parametrize("target", list(ex.TARGETS))
def test_every_combination_gives_a_workout(level, equipment, target):
    for goal in ex.PRESCRIPTION:
        w = ex.generate_workout(target, level, goal, equipment, None, 60)
        assert len(w["exercises"]) >= 3
        assert w["minutes"] <= ex.DEFAULT_MINUTES[level] + 2
        for e in w["exercises"]:
            assert ex.LEVEL_RANK[level] >= ex.EX_BY_KEY[e["key"]]["level"]
            assert ex.EQUIP_RANK[equipment] >= ex.EQUIP_RANK[e["equip"]]


def test_legs_targets_leg_muscles():
    w = ex.generate_workout("legs", "intermediate", "build_muscle", "dumbbell", 45, 70)
    assert all(set(e["muscles"]) & set(ex.TARGETS["legs"]["muscles"]) for e in w["exercises"])
    assert {e["reps"] for e in w["exercises"] if e["reps"]} == {10}   # 8–12 ระดับกลาง
    assert w["muscle_text"].startswith("ส่วนล่าง")


def test_strength_reps_drop_with_experience():
    beg = ex.generate_workout("legs", "beginner", "strength", "gym", 60, 70)
    adv = ex.generate_workout("legs", "advanced", "strength", "gym", 60, 70)
    assert beg["exercises"][0]["reps"] > adv["exercises"][0]["reps"]
    assert beg["exercises"][0]["sets"] < adv["exercises"][0]["sets"]
    assert not any(ex.EX_BY_KEY[e["key"]]["pattern"] in ex.PLYO for e in adv["exercises"])


def test_no_duplicate_patterns():
    w = ex.generate_workout("full", "advanced", "fitness", "gym", 60, 70)
    patterns = [ex.EX_BY_KEY[e["key"]]["pattern"] for e in w["exercises"]]
    assert len(patterns) == len(set(patterns))


def test_time_budget_respected():
    short = ex.generate_workout("full", "advanced", "build_muscle", "gym", 20, 70)
    assert short["minutes"] <= 22 and len(short["exercises"]) >= 1


def test_recent_overlap_ignores_core():
    assert ex.recent_overlap("legs", {1: {"quads", "abs"}}) == [(1, ["quads"])]
    assert ex.recent_overlap("core", {1: {"abs"}}) == []
