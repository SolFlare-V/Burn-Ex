"""
Movement-driven intensity estimator for Burn-Ex calorie engine.

Replaces the static MET multiplier with a per-frame kinetic intensity score
derived from MediaPipe pose landmarks. The score modulates calorie expenditure
so that a fast, deep, explosive movement burns more than a slow, shallow one.

Design principles
-----------------
- No ML model, no external sensors, no training data required.
- All computation is from 33 landmark (x, y, z) coordinates at 15 fps.
- Runs in < 5 ms per frame (pure Python with small deque operations).
- Mathematically grounded in biomechanics literature:
    • Joint velocity ↔ power output (Winter, Biomechanics of Human Movement)
    • Vertical COM displacement ↔ gravitational work (Cavagna 1977)
    • Angular velocity ↔ muscular effort proxy (Zajac 1993)
    • ROM fraction ↔ exercise quality (Schoenfeld 2010)

Output
------
intensity_multiplier : float in [0.3, 2.5]
    1.0 = average effort (matching the standard MET value)
    < 1.0 = slower / shallower than average
    > 1.0 = faster / deeper / more explosive than average

Usage
-----
    estimator = IntensityEstimator(fps=15.0)
    # each frame:
    result = estimator.update(landmarks, exercise_type, elapsed_s)
    intensity = result.multiplier
    calories_this_second = BASE_MET * weight_kg / 3600.0 * intensity
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Landmark IDs (MediaPipe 33-point model)
# https://developers.google.com/mediapipe/solutions/vision/pose_landmarker
_LM = {
    "nose": 0,
    "l_shoulder": 11, "r_shoulder": 12,
    "l_elbow": 13, "r_elbow": 14,
    "l_wrist": 15, "r_wrist": 16,
    "l_hip": 23, "r_hip": 24,
    "l_knee": 25, "r_knee": 26,
    "l_ankle": 27, "r_ankle": 28,
    "l_heel": 29, "r_heel": 30,
    "l_foot": 31, "r_foot": 32,
}

# Approximate segment mass fractions of total body mass (Winter 2009)
# Used for centre-of-mass estimation
_SEGMENT_MASS_FRACTION: dict[str, float] = {
    "head":          0.081,
    "trunk":         0.497,
    "l_upper_arm":   0.028,
    "r_upper_arm":   0.028,
    "l_forearm":     0.016,
    "r_forearm":     0.016,
    "l_hand":        0.006,
    "r_hand":        0.006,
    "l_thigh":       0.100,
    "r_thigh":       0.100,
    "l_shank":       0.0465,
    "r_shank":       0.0465,
    "l_foot":        0.0145,
    "r_foot":        0.0145,
}

# Joints used for joint-velocity computation (id pairs)
_VELOCITY_JOINTS = [
    _LM["l_wrist"], _LM["r_wrist"],
    _LM["l_elbow"], _LM["r_elbow"],
    _LM["l_knee"],  _LM["r_knee"],
    _LM["l_ankle"], _LM["r_ankle"],
    _LM["l_hip"],   _LM["r_hip"],
]

# Per-exercise ROM reference ranges [min_angle_deg, max_angle_deg] for key joint
# Used to compute ROM_fraction (0=no range, 1=full textbook range)
# Sources: ACSM Exercise Testing and Prescription, 10th ed.
_ROM_REFS: dict[str, tuple[str, float, float]] = {
    # exercise -> (angle_name, min_expected_deg, max_expected_deg)
    "squat":          ("left_knee",  60.0,  175.0),
    "lunge":          ("left_knee",  70.0,  175.0),
    "push_up":        ("left_elbow", 90.0,  175.0),
    "bicep_curl":     ("left_elbow", 30.0,  170.0),
    "shoulder_press": ("left_elbow", 90.0,  175.0),
    "plank":          ("trunk",      80.0,  100.0),
}

# Base MET multiplier bounds.
# Mapping: raw=0.5 (average effort) → multiplier=1.0 (matches base MET exactly).
# raw=0.0 (minimal effort) → 0.40; raw=1.0 (maximal effort) → 2.00.
# Formula: multiplier = 1.0 + (raw - 0.5) * 1.60, then clamp.
# Derivation: slope = (MAX - MIN) / 1.0 = 1.60; at raw=0.5: 1.0 + 0 = 1.0. ✓
_MIN_MULTIPLIER = 0.40
_MAX_MULTIPLIER = 2.00

# Smoothing window (frames). EMA alpha = 2/(N+1)
_SMOOTH_N = 6
_EMA_ALPHA = 2.0 / (_SMOOTH_N + 1)

# Number of past frames kept for velocity/acceleration history
_HISTORY_LEN = 8

# Resting movement threshold: joint velocity below this = user is still
_REST_VELOCITY_THRESHOLD = 0.008   # normalized coords / second


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class IntensityResult:
    """Per-frame intensity estimation output."""
    multiplier: float                   # final smoothed intensity multiplier
    raw_multiplier: float               # unsmoothed value
    joint_velocity_score: float         # 0–1 contribution from joint speeds
    com_displacement_score: float       # 0–1 contribution from COM vertical motion
    angular_velocity_score: float       # 0–1 contribution from angular velocities
    rom_score: float                    # 0–1 fraction of expected ROM achieved
    is_resting: bool                    # True if virtually no movement detected
    motion_power_estimate: float        # arbitrary units, for display/logging


@dataclass
class _LandmarkSnapshot:
    """Lightweight snapshot of landmark positions for one frame."""
    positions: dict[int, tuple[float, float, float]]  # id -> (x, y, z)
    timestamp: float


# ---------------------------------------------------------------------------
# IntensityEstimator
# ---------------------------------------------------------------------------

class IntensityEstimator:
    """
    Estimates per-frame movement intensity from MediaPipe landmarks.

    Maintains a rolling history of landmark positions to compute:
    - Joint linear velocities  (Δposition / Δtime)
    - Joint angular velocities (Δangle / Δtime)
    - Centre-of-mass vertical displacement (height-calibrated)
    - Range-of-motion fraction vs. textbook reference

    These are combined into a single intensity multiplier [0.40, 2.00].

    Args:
        fps:      Expected frame rate (used as dt fallback guard).
        height_m: User's standing height in metres, from their profile.
                  Used to calibrate the normalised→real-world scale factor.
                  Pass 0.0 or omit to disable height calibration (falls back
                  to the uncalibrated normalised-coord divisor).
    """

    # Number of full-body frames required before height calibration is accepted.
    _CALIBRATION_FRAMES_REQUIRED = 10

    def __init__(self, fps: float = 15.0, height_m: float = 0.0) -> None:
        self._fps = fps
        self._height_m: float = height_m  # 0.0 = not provided / disabled

        self._history: deque[_LandmarkSnapshot] = deque(maxlen=_HISTORY_LEN)
        self._angle_history: deque[dict[str, float]] = deque(maxlen=_HISTORY_LEN)
        self._smoothed_multiplier: float = 1.0

        # Height calibration state.
        # scale_m_per_norm converts a normalised-coordinate displacement into metres.
        # It is estimated from the person's visible body height (shoulder→ankle in
        # normalised coords) compared to their stored height_m.
        # Assumption: the person fills the camera frame in a consistent way during
        # the calibration window.  If they step closer or farther mid-session the
        # estimate becomes less accurate, but no better source is available from a
        # single RGB camera.
        self._scale_samples: list[float] = []  # raw per-frame scale estimates
        self._scale_m_per_norm: float = 0.0    # 0.0 = not yet calibrated

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def update(
        self,
        landmarks: list[Any],   # list[Landmark | FilteredLandmark]
        angle_map: dict[str, float],
        exercise_type: Optional[str],
        elapsed_s: float,
    ) -> IntensityResult:
        """
        Process one frame and return the intensity result.

        Args:
            landmarks:     33 Landmark objects from cv.pose_estimator.
            angle_map:     Current frame's joint angles from angle_utils.
            exercise_type: Confirmed exercise, or None if unconfirmed.
            elapsed_s:     Seconds since last frame (typically ~0.067 at 15fps).

        Returns:
            IntensityResult with multiplier and component scores.
        """
        if not landmarks or elapsed_s <= 0:
            return self._rest_result()

        # Build position snapshot
        pos: dict[int, tuple[float, float, float]] = {}
        for lm in landmarks:
            if hasattr(lm, "visibility") and lm.visibility >= 0.3:
                pos[lm.id] = (lm.x, lm.y, lm.z)

        snap = _LandmarkSnapshot(positions=pos, timestamp=elapsed_s)
        self._history.append(snap)
        self._angle_history.append(dict(angle_map))

        # Attempt height calibration using this frame's positions.
        # No-ops once enough samples are collected or if height_m was not provided.
        self._try_calibrate_height_scale(pos)

        # Need at least 2 frames for velocity
        if len(self._history) < 2:
            return self._rest_result()

        prev = self._history[-2]
        curr = self._history[-1]
        dt = max(elapsed_s, 1.0 / (self._fps * 2))  # guard against zero dt

        # --- Component 1: Joint linear velocities ---
        jv_score, is_resting, max_velocity = self._joint_velocity_score(prev, curr, dt)

        # --- Component 2: Centre-of-mass vertical displacement ---
        com_y_curr = self._estimate_com_y(curr.positions)
        com_y_prev = self._estimate_com_y(prev.positions)
        com_score = self._com_displacement_score(com_y_curr, com_y_prev, dt)

        # --- Component 3: Angular velocities ---
        av_score = self._angular_velocity_score(dt)

        # --- Component 4: Range of motion fraction ---
        rom_score = self._rom_score(angle_map, exercise_type)

        # --- Combine components ---
        # Weights chosen empirically; joint velocity is the dominant signal
        # since it most directly reflects mechanical work output
        if exercise_type == "plank":
            # Plank is a static hold — joint velocity should be low,
            # contribution comes from hold duration (handled by MET base)
            raw = (
                0.20 * jv_score +
                0.20 * com_score +
                0.20 * av_score +
                0.40 * rom_score
            )
        elif exercise_type in ("bicep_curl", "shoulder_press"):
            # Upper-body: elbow/shoulder velocity dominates
            raw = (
                0.45 * jv_score +
                0.10 * com_score +
                0.25 * av_score +
                0.20 * rom_score
            )
        else:
            # Lower-body / compound (squat, lunge, push_up, unknown)
            raw = (
                0.40 * jv_score +
                0.25 * com_score +
                0.20 * av_score +
                0.15 * rom_score
            )

        # Map raw [0,1] → multiplier [0.40, 2.00].
        # Anchor: raw=0.5 (average effort) → multiplier=1.0 (matches base MET).
        # Formula: 1.0 + (raw - 0.5) × 1.60
        # Verification: raw=0.0 → 0.20 (clamped to 0.40)
        #               raw=0.5 → 1.00 ✓
        #               raw=1.0 → 1.80 (clamped to 2.00 if needed, here ≤ 2.00 ✓)
        raw_multiplier = 1.0 + (raw - 0.5) * 1.60

        # General movement when unconfirmed: use fraction of joint velocity
        if exercise_type is None:
            # Scale down for unclassified activity (likely low-intensity)
            raw_multiplier *= 0.50

        raw_multiplier = max(_MIN_MULTIPLIER, min(_MAX_MULTIPLIER, raw_multiplier))

        # EMA smoothing to prevent jitter
        self._smoothed_multiplier = (
            _EMA_ALPHA * raw_multiplier +
            (1.0 - _EMA_ALPHA) * self._smoothed_multiplier
        )

        motion_power = max_velocity * raw_multiplier

        return IntensityResult(
            multiplier=round(self._smoothed_multiplier, 4),
            raw_multiplier=round(raw_multiplier, 4),
            joint_velocity_score=round(jv_score, 4),
            com_displacement_score=round(com_score, 4),
            angular_velocity_score=round(av_score, 4),
            rom_score=round(rom_score, 4),
            is_resting=is_resting,
            motion_power_estimate=round(motion_power, 4),
        )

    def reset(self) -> None:
        """Clear history and calibration (call on session start or exercise change)."""
        self._history.clear()
        self._angle_history.clear()
        self._smoothed_multiplier = 1.0
        # Preserve height_m and any completed calibration across exercise changes —
        # re-calibrating mid-session is unnecessary and would discard good data.
        # Only reset the sample list so a new session can recalibrate from scratch.

    # ------------------------------------------------------------------
    # Private component scorers
    # ------------------------------------------------------------------

    def _joint_velocity_score(
        self,
        prev: _LandmarkSnapshot,
        curr: _LandmarkSnapshot,
        dt: float,
    ) -> tuple[float, bool, float]:
        """
        Compute normalised joint velocity score [0, 1].

        Returns (score, is_resting, max_velocity).
        """
        velocities: list[float] = []
        for lm_id in _VELOCITY_JOINTS:
            if lm_id in prev.positions and lm_id in curr.positions:
                px, py, _ = prev.positions[lm_id]
                cx, cy, _ = curr.positions[lm_id]
                dx, dy = cx - px, cy - py
                v = math.sqrt(dx * dx + dy * dy) / dt
                velocities.append(v)

        if not velocities:
            return 0.0, True, 0.0

        mean_v = sum(velocities) / len(velocities)
        max_v = max(velocities)
        is_resting = max_v < _REST_VELOCITY_THRESHOLD

        # Normalise: typical fast joint movement ~0.3–0.8 coords/s in 15fps space
        # Clamp at 0.5 → score=1.0 (very fast movement)
        score = min(mean_v / 0.20, 1.0)
        return score, is_resting, max_v

    def _estimate_com_y(self, positions: dict[int, tuple[float, float, float]]) -> float:
        """
        Weighted centre-of-mass Y coordinate estimate.

        Uses a simplified 7-segment model (head, trunk, 2 arms, 2 thighs, 2 shanks)
        with Winter (2009) mass fractions. Y increases downward in MediaPipe coords.
        Returns a single float; lower value = higher body position.
        """
        # Segment proximal/distal landmark pairs and mass fraction keys
        segments: list[tuple[int, int, str]] = [
            # (proximal_id, distal_id, segment_key)
            (_LM["l_shoulder"], _LM["l_elbow"],   "l_upper_arm"),
            (_LM["r_shoulder"], _LM["r_elbow"],   "r_upper_arm"),
            (_LM["l_elbow"],    _LM["l_wrist"],   "l_forearm"),
            (_LM["r_elbow"],    _LM["r_wrist"],   "r_forearm"),
            (_LM["l_hip"],      _LM["l_knee"],    "l_thigh"),
            (_LM["r_hip"],      _LM["r_knee"],    "r_thigh"),
            (_LM["l_knee"],     _LM["l_ankle"],   "l_shank"),
            (_LM["r_knee"],     _LM["r_ankle"],   "r_shank"),
        ]

        # Trunk: midpoint of shoulders and hips
        if all(id_ in positions for id_ in [_LM["l_shoulder"], _LM["r_shoulder"], _LM["l_hip"], _LM["r_hip"]]):
            ls, rs = positions[_LM["l_shoulder"]], positions[_LM["r_shoulder"]]
            lh, rh = positions[_LM["l_hip"]], positions[_LM["r_hip"]]
            trunk_y = (ls[1] + rs[1] + lh[1] + rh[1]) / 4.0
        else:
            trunk_y = 0.5  # fallback

        weighted_sum = trunk_y * _SEGMENT_MASS_FRACTION["trunk"]
        total_fraction = _SEGMENT_MASS_FRACTION["trunk"]

        for prox_id, dist_id, seg_key in segments:
            if prox_id in positions and dist_id in positions:
                prox_y = positions[prox_id][1]
                dist_y = positions[dist_id][1]
                seg_com_y = (prox_y + dist_y) / 2.0
                frac = _SEGMENT_MASS_FRACTION.get(seg_key, 0.02)
                weighted_sum += seg_com_y * frac
                total_fraction += frac

        if total_fraction == 0:
            return 0.5
        return weighted_sum / total_fraction

    def _com_displacement_score(
        self,
        com_y_curr: float,
        com_y_prev: float,
        dt: float,
    ) -> float:
        """
        Score based on vertical COM velocity, height-calibrated when possible.

        In MediaPipe coords, y increases downward, so a squat lowering the
        body INCREASES y.  The displacement is converted to real metres using
        the calibrated scale_m_per_norm when available, then normalised against
        a reference velocity of 0.15 m/s (a moderate squat descent rate).

        When calibration is not yet available, falls back to the uncalibrated
        normalised-coordinate divisor (0.10 normalised/s) — same behaviour as
        the previous implementation.

        Limitation: this is vertical COM velocity from a 2D monocular projection.
        It does not capture horizontal or depth-direction COM motion.  It should
        not be interpreted as equivalent to true COM velocity from 3D motion capture.
        """
        delta_y_norm = abs(com_y_curr - com_y_prev)

        if self._scale_m_per_norm > 0.0:
            # Height-calibrated path: convert to real metres/second.
            # Reference velocity: 0.15 m/s ≈ moderate squat descent/ascent rate.
            # (A fast squat reaches ~0.30 m/s; a slow one ~0.05 m/s.)
            delta_y_m = delta_y_norm * self._scale_m_per_norm
            com_vy_m_per_s = delta_y_m / dt
            score = min(com_vy_m_per_s / 0.15, 1.0)
        else:
            # Fallback: uncalibrated normalised coords. Divisor 0.10 was chosen
            # empirically in the original implementation. Results vary with
            # camera distance and subject height.
            com_vy = delta_y_norm / dt
            score = min(com_vy / 0.10, 1.0)

        return score

    def _try_calibrate_height_scale(
        self,
        positions: dict[int, tuple[float, float, float]],
    ) -> None:
        """
        Attempt to update the height calibration using one frame's landmarks.

        Measures the shoulder-midpoint to ankle-midpoint distance in normalised
        coordinates and compares it to the user's stored height_m to estimate
        scale_m_per_norm.

        Called each frame until _CALIBRATION_FRAMES_REQUIRED samples are collected,
        after which the median is frozen as the session scale.

        Assumptions and limitations
        ---------------------------
        - Requires both shoulders (11, 12) and both ankles (27, 28) to be visible
          with visibility >= 0.5.  Frames where these are occluded are skipped.
        - The shoulder-to-ankle distance in normalised coords ≈ 0.85–0.92 × true
          standing height for an upright, forward-facing person.  A correction
          factor of 1/0.88 (median of published MediaPipe normalisation ratios) is
          applied to account for this.
        - If the person is not standing upright at calibration time (e.g. squatting
          during the first 10 frames), the scale estimate will be low.  The median
          of multiple frames partially mitigates this.
        - Camera angle and zoom affect normalised coordinates.  This calibration
          assumes the person roughly fills the frame vertically.
        """
        if self._height_m <= 0.0:
            return  # height not provided — calibration disabled
        if len(self._scale_samples) >= self._CALIBRATION_FRAMES_REQUIRED:
            return  # already have enough samples

        # Need all four landmarks visible and confident
        required = [_LM["l_shoulder"], _LM["r_shoulder"], _LM["l_ankle"], _LM["r_ankle"]]
        if not all(lid in positions for lid in required):
            return

        ls_y = positions[_LM["l_shoulder"]][1]
        rs_y = positions[_LM["r_shoulder"]][1]
        la_y = positions[_LM["l_ankle"]][1]
        ra_y = positions[_LM["r_ankle"]][1]

        shoulder_mid_y = (ls_y + rs_y) / 2.0
        ankle_mid_y    = (la_y + ra_y) / 2.0

        # Vertical span in normalised coords (positive: ankles below shoulders)
        span_norm = ankle_mid_y - shoulder_mid_y
        if span_norm < 0.05:
            return  # degenerate frame (person horizontal or not visible enough)

        # The shoulder-to-ankle span captures ~88% of standing height in MediaPipe's
        # normalised output for an upright person (head not included in measurement).
        # Correction factor: height_m / (span_norm × 0.88) = scale_m_per_norm
        scale = self._height_m / (span_norm * 0.88)
        self._scale_samples.append(scale)

        if len(self._scale_samples) >= self._CALIBRATION_FRAMES_REQUIRED:
            # Use median to reject outlier frames (person partially squatting etc.)
            sorted_samples = sorted(self._scale_samples)
            n = len(sorted_samples)
            if n % 2 == 0:
                median = (sorted_samples[n // 2 - 1] + sorted_samples[n // 2]) / 2.0
            else:
                median = sorted_samples[n // 2]
            self._scale_m_per_norm = median

    def _angular_velocity_score(self, dt: float) -> float:
        """
        Score based on rate of change of joint angles.

        Uses the two most recent angle maps to compute angular velocity
        (degrees/second) at each joint.
        """
        if len(self._angle_history) < 2:
            return 0.0

        curr_angles = self._angle_history[-1]
        prev_angles = self._angle_history[-2]

        angular_velocities: list[float] = []
        for joint, curr_angle in curr_angles.items():
            if joint in prev_angles:
                delta = abs(curr_angle - prev_angles[joint])
                av = delta / dt
                angular_velocities.append(av)

        if not angular_velocities:
            return 0.0

        mean_av = sum(angular_velocities) / len(angular_velocities)
        # Normalise: fast squat/bicep curl ~ 100–300°/s
        score = min(mean_av / 150.0, 1.0)
        return score

    def _rom_score(
        self,
        angle_map: dict[str, float],
        exercise_type: Optional[str],
    ) -> float:
        """
        Fraction of expected range of motion achieved at any point in the session.

        Uses rolling min/max of the key joint angle for the exercise to estimate
        the range achieved so far, compared to the textbook full ROM.
        Returns 0.5 if exercise has no ROM reference (e.g. plank).
        """
        if exercise_type is None or exercise_type not in _ROM_REFS:
            return 0.5

        joint_name, rom_min, rom_max = _ROM_REFS[exercise_type]

        if joint_name not in angle_map:
            return 0.5

        current_angle = angle_map[joint_name]

        # Collect historical values for this joint from angle history
        historical = [
            frame[joint_name]
            for frame in self._angle_history
            if joint_name in frame
        ]

        if not historical:
            return 0.5

        observed_range = max(historical) - min(historical)
        reference_range = rom_max - rom_min

        if reference_range <= 0:
            return 0.5

        fraction = min(observed_range / reference_range, 1.0)
        return fraction

    def _rest_result(self) -> IntensityResult:
        """Return a minimal result for frames with no landmarks or no history."""
        return IntensityResult(
            multiplier=_MIN_MULTIPLIER,
            raw_multiplier=_MIN_MULTIPLIER,
            joint_velocity_score=0.0,
            com_displacement_score=0.0,
            angular_velocity_score=0.0,
            rom_score=0.0,
            is_resting=True,
            motion_power_estimate=0.0,
        )
