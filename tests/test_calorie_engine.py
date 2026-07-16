"""
TASK-16.2 — Unit tests for the CalorieEngine.

Verify: pytest tests/test_calorie_engine.py passes.
"""
import pytest
import time

from backend.calories.engine import CalorieEngine

# MET values from config/met_values.yaml
MET = {
    "squat": 5.0,
    "push_up": 8.0,
    "lunge": 4.5,
    "bicep_curl": 3.5,
    "shoulder_press": 4.0,
    "plank": 4.0,
}

WEIGHT_KG = 70.0


# ---------------------------------------------------------------------------
# Weight gate
# ---------------------------------------------------------------------------

def test_zero_weight_raises():
    with pytest.raises(ValueError, match="weight_kg"):
        CalorieEngine(weight_kg=0.0)


def test_negative_weight_raises():
    with pytest.raises(ValueError):
        CalorieEngine(weight_kg=-10.0)


def test_positive_weight_ok():
    engine = CalorieEngine(weight_kg=WEIGHT_KG)
    assert engine.weight_kg == WEIGHT_KG


# ---------------------------------------------------------------------------
# MET calculation — each exercise
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("exercise,met", MET.items())
def test_met_calculation_per_exercise(exercise, met):
    """
    calories = MET × weight_kg × duration_hours
    Test with 30-minute segment: calories ≈ met * 70 * 0.5
    """
    engine = CalorieEngine(weight_kg=WEIGHT_KG)
    t0 = 1_000_000.0
    t1 = t0 + 1800.0  # 30 minutes
    engine.start_segment(exercise, t0)
    seg = engine.close_segment(t1)

    expected = met * WEIGHT_KG * (1800.0 / 3600.0)
    assert abs(seg.calories - expected) < 0.001, (
        f"{exercise}: expected {expected:.4f}, got {seg.calories:.4f}"
    )


def test_squat_30min_formula():
    """Explicit formula check: squat 30 min = 5.0 * 70 * 0.5 = 175.0 kcal."""
    engine = CalorieEngine(weight_kg=WEIGHT_KG)
    t0 = 0.0
    engine.start_segment("squat", t0)
    seg = engine.close_segment(t0 + 1800.0)
    assert abs(seg.calories - 175.0) < 0.001


# ---------------------------------------------------------------------------
# Segmented accumulation across exercise change
# ---------------------------------------------------------------------------

def test_change_exercise_creates_two_segments():
    engine = CalorieEngine(weight_kg=WEIGHT_KG)
    t0 = 0.0
    engine.start_segment("squat", t0)
    engine.change_exercise("push_up", t0 + 600.0)   # 10 min squat, then push_up

    segs = engine.segments
    assert len(segs) == 2
    assert segs[0].exercise_type == "squat"
    assert segs[0].end_time is not None       # closed
    assert segs[1].exercise_type == "push_up"
    assert segs[1].end_time is None            # open


def test_running_total_sums_closed_segments():
    engine = CalorieEngine(weight_kg=WEIGHT_KG)
    t0 = 0.0
    engine.start_segment("squat", t0)
    engine.change_exercise("push_up", t0 + 3600.0)   # 1 hr squat

    total = engine.running_total()
    expected_squat = MET["squat"] * WEIGHT_KG * 1.0
    assert abs(total - expected_squat) < 0.01


def test_accumulation_two_closed_segments():
    engine = CalorieEngine(weight_kg=WEIGHT_KG)
    t0 = 0.0
    engine.start_segment("squat", t0)
    engine.change_exercise("push_up", t0 + 3600.0)  # 1hr squat
    engine.close_segment(t0 + 7200.0)                # 1hr push_up

    total = engine.running_total()
    expected = (MET["squat"] * WEIGHT_KG * 1.0 +
                MET["push_up"] * WEIGHT_KG * 1.0)
    assert abs(total - expected) < 0.01


# ---------------------------------------------------------------------------
# running_estimate — closed + open segment
# ---------------------------------------------------------------------------

def test_running_estimate_includes_open_segment():
    engine = CalorieEngine(weight_kg=WEIGHT_KG)
    t0 = 0.0
    engine.start_segment("squat", t0)
    # Estimate after 30 minutes (no closed segments)
    estimate = engine.running_estimate(t0 + 1800.0)
    expected = MET["squat"] * WEIGHT_KG * 0.5
    assert abs(estimate - expected) < 0.001


def test_running_estimate_closed_plus_open():
    engine = CalorieEngine(weight_kg=WEIGHT_KG)
    t0 = 0.0
    engine.start_segment("squat", t0)
    engine.change_exercise("push_up", t0 + 3600.0)  # 1hr squat closed
    # Estimate 30 min into push_up
    estimate = engine.running_estimate(t0 + 5400.0)
    expected = (MET["squat"] * WEIGHT_KG * 1.0 +
                MET["push_up"] * WEIGHT_KG * 0.5)
    assert abs(estimate - expected) < 0.01


def test_running_estimate_no_segments_returns_zero():
    engine = CalorieEngine(weight_kg=WEIGHT_KG)
    assert engine.running_estimate(1000.0) == 0.0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_close_without_open_raises():
    engine = CalorieEngine(weight_kg=WEIGHT_KG)
    with pytest.raises(RuntimeError):
        engine.close_segment(100.0)


def test_double_start_raises():
    engine = CalorieEngine(weight_kg=WEIGHT_KG)
    engine.start_segment("squat", 0.0)
    with pytest.raises(RuntimeError):
        engine.start_segment("squat", 10.0)


def test_unknown_exercise_raises_key_error():
    engine = CalorieEngine(weight_kg=WEIGHT_KG)
    with pytest.raises(KeyError):
        engine.start_segment("jumping_jacks", 0.0)


def test_zero_duration_segment():
    """Segment with zero duration should produce 0 calories."""
    engine = CalorieEngine(weight_kg=WEIGHT_KG)
    t = 1000.0
    engine.start_segment("squat", t)
    seg = engine.close_segment(t)
    assert seg.calories == 0.0
    assert seg.duration_seconds == 0
