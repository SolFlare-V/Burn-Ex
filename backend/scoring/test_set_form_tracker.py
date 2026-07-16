"""
Unit tests for SetFormTracker (TASK-6.4).

Verifies:
  1. add [100, 80, 60] → average() == 80.0
  2. No samples → average() == 100.0
  3. reset() clears state → subsequent average() == 100.0
  4. Single sample → average() == that value as float
  5. sample_count reflects the number of added samples
"""

import pytest
from backend.scoring.set_form_tracker import SetFormTracker


class TestSetFormTrackerAverageScenarios:
    """Functional tests for average computation."""

    def test_average_of_three_scores(self) -> None:
        """add [100, 80, 60] → average() returns 80.0."""
        tracker = SetFormTracker()
        tracker.add_sample(100)
        tracker.add_sample(80)
        tracker.add_sample(60)
        assert tracker.average() == 80.0

    def test_no_samples_returns_perfect_score(self) -> None:
        """No samples → average() returns 100.0 (perfect-score default)."""
        tracker = SetFormTracker()
        assert tracker.average() == 100.0

    def test_reset_clears_state(self) -> None:
        """reset() discards all samples; subsequent average() returns 100.0."""
        tracker = SetFormTracker()
        tracker.add_sample(50)
        tracker.add_sample(60)
        tracker.reset()
        assert tracker.average() == 100.0

    def test_single_sample_average_equals_sample_value(self) -> None:
        """Single sample → average() equals that value as float."""
        tracker = SetFormTracker()
        tracker.add_sample(73)
        assert tracker.average() == 73.0

    def test_average_returns_float(self) -> None:
        """average() always returns a float, even for whole-number means."""
        tracker = SetFormTracker()
        tracker.add_sample(90)
        result = tracker.average()
        assert isinstance(result, float)


class TestSetFormTrackerSampleCount:
    """Tests for the sample_count property."""

    def test_sample_count_starts_at_zero(self) -> None:
        """A freshly created tracker has sample_count == 0."""
        tracker = SetFormTracker()
        assert tracker.sample_count == 0

    def test_sample_count_increments_per_add(self) -> None:
        """sample_count increments by 1 for each add_sample call."""
        tracker = SetFormTracker()
        for expected in range(1, 6):
            tracker.add_sample(100)
            assert tracker.sample_count == expected

    def test_sample_count_resets_to_zero_after_reset(self) -> None:
        """reset() sets sample_count back to 0."""
        tracker = SetFormTracker()
        tracker.add_sample(80)
        tracker.add_sample(90)
        tracker.reset()
        assert tracker.sample_count == 0

    def test_sample_count_after_reset_and_readd(self) -> None:
        """sample_count counts correctly across a reset-and-readd cycle."""
        tracker = SetFormTracker()
        tracker.add_sample(100)
        tracker.add_sample(80)
        tracker.reset()
        tracker.add_sample(60)
        assert tracker.sample_count == 1
        assert tracker.average() == 60.0


class TestSetFormTrackerEdgeCases:
    """Edge-case and boundary tests."""

    def test_zero_score_sample(self) -> None:
        """Score of 0 is valid and is included in the average."""
        tracker = SetFormTracker()
        tracker.add_sample(0)
        tracker.add_sample(100)
        assert tracker.average() == 50.0

    def test_all_perfect_scores(self) -> None:
        """All 100 scores → average is 100.0."""
        tracker = SetFormTracker()
        for _ in range(10):
            tracker.add_sample(100)
        assert tracker.average() == 100.0

    def test_all_zero_scores(self) -> None:
        """All 0 scores → average is 0.0."""
        tracker = SetFormTracker()
        for _ in range(5):
            tracker.add_sample(0)
        assert tracker.average() == 0.0

    def test_multiple_resets_idempotent(self) -> None:
        """Calling reset() multiple times in a row is safe."""
        tracker = SetFormTracker()
        tracker.add_sample(75)
        tracker.reset()
        tracker.reset()
        assert tracker.average() == 100.0
        assert tracker.sample_count == 0

    def test_large_number_of_samples(self) -> None:
        """Tracker handles a large number of samples without overflow."""
        tracker = SetFormTracker()
        for score in range(101):          # 0..100 inclusive
            tracker.add_sample(score)
        expected = sum(range(101)) / 101  # 50.0
        assert abs(tracker.average() - expected) < 1e-9
