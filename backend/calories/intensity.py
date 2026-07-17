"""
Movement-driven intensity estimator for Burn-Ex calorie engine.

Improvements over v1:
  Step 0  — Corrected multiplier mapping: raw=0.5 → 1.0 (was 1.40).
  P1-I1   — Height-calibrated COM scaling.
  P1-I2   — Confidence-weighted MET exposed via classify_frame.
  P1-I3   — Per-rep ROM tracking (direction-reversal, not window-based).
  P1-I4   — General activity mode for unclassified movement.
  P1-I5   — Static hold model (postural sway + tremor).
  P1-I6   — Calorie confidence score and CI.
  P2-I7   — Height-scaled external energy proxy (ΔPE + ΔKE approximation).
  P2-I8   — Fatigue estimation (velocity/ROM decline vs. baseline).
  P2-I9   — Symmetry analysis (L/R velocity asymmetry).

All estimates derived from monocular RGB pose landmarks only.
No sensors, no IMUs, no heart-rate data used or required.
"""
from __future__ import annotations

import math
import statistics
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Landmark IDs (MediaPipe 33-point model)
# ---------------------------------------------------------------------------
_LM = {
    "nose": 0,
    "l_shoulder": 11, "r_shoulder": 12,
    "l_elbow": 13,    "r_elbow": 14,
    "l_wrist": 15,    "r_wrist": 16,
    "l_hip": 23,      "r_hip": 24,
    "l_knee": 25,     "r_knee": 26,
    "l_ankle": 27,    "r_ankle": 28,
    "l_heel": 29,     "r_heel": 30,
    "l_foot": 31,     "r_foot": 32,
}

# ---------------------------------------------------------------------------
# Segment mass fractions — Winter (2009) Table 4.1
# ---------------------------------------------------------------------------
_SEGMENT_MASS_FRACTION: dict[str, float] = {
    "trunk":       0.497,
    "l_upper_arm": 0.028, "r_upper_arm": 0.028,
    "l_forearm":   0.016, "r_forearm":   0.016,
    "l_hand":      0.006, "r_hand":      0.006,
    "l_thigh":     0.100, "r_thigh":     0.100,
    "l_shank":     0.0465,"r_shank":     0.0465,
    "l_foot":      0.0145,"r_foot":      0.0145,
}

# ---------------------------------------------------------------------------
# Joint sets
# ---------------------------------------------------------------------------
_VELOCITY_JOINTS = [
    _LM["l_wrist"], _LM["r_wrist"],
    _LM["l_elbow"], _LM["r_elbow"],
    _LM["l_knee"],  _LM["r_knee"],
    _LM["l_ankle"], _LM["r_ankle"],
    _LM["l_hip"],   _LM["r_hip"],
]
_LEFT_JOINTS  = [_LM["l_wrist"], _LM["l_elbow"], _LM["l_knee"], _LM["l_ankle"], _LM["l_hip"]]
_RIGHT_JOINTS = [_LM["r_wrist"], _LM["r_elbow"], _LM["r_knee"], _LM["r_ankle"], _LM["r_hip"]]

# ---------------------------------------------------------------------------
# ROM reference ranges — ACSM Exercise Testing & Prescription, 10th ed.
# (joint_name, min_deg, max_deg)
# ---------------------------------------------------------------------------
_ROM_REFS: dict[str, tuple[str, float, float]] = {
    "squat":          ("left_knee",  60.0, 175.0),
    "lunge":          ("left_knee",  70.0, 175.0),
    "push_up":        ("left_elbow", 90.0, 175.0),
    "bicep_curl":     ("left_elbow", 30.0, 170.0),
    "shoulder_press": ("left_elbow", 90.0, 175.0),
    "plank":          ("trunk",      80.0, 100.0),
}

# ---------------------------------------------------------------------------
# General activity MET tiers — approximations from Ainsworth (2011)
# Thresholds are in normalised coords/s (camera-distance dependent).
# ---------------------------------------------------------------------------
_GENERAL_ACTIVITY_TIERS: list[tuple[float, float]] = [
    (0.005, 1.3),        # sedentary / standing still
    (0.025, 2.0),        # light (stretching, reaching)
    (0.080, 3.5),        # moderate (walking, stepping)
    (float("inf"), 5.0), # vigorous unclassified movement
]

# ---------------------------------------------------------------------------
# Physics constants — used only for the external energy proxy (P2-I7)
# ---------------------------------------------------------------------------
_GRAVITY_M_S2 = 9.81
# Approximate mechanical efficiency for dynamic exercise.
# Source: Cavagna & Kaneko (1977) — used only as a scaling denominator.
# This value does NOT validate the energy proxy against true metabolic cost.
_MECHANICAL_EFFICIENCY_APPROX = 0.25

# ---------------------------------------------------------------------------
# Multiplier bounds — Step 0 corrected mapping
# raw=0.5 → 1.0 (matches base MET); raw=0.0 → 0.40; raw=1.0 → 1.80
# ---------------------------------------------------------------------------
_MIN_MULTIPLIER = 0.40
_MAX_MULTIPLIER = 2.00

# ---------------------------------------------------------------------------
# EMA smoothing: α = 2/(N+1), N=6 frames
# ---------------------------------------------------------------------------
_SMOOTH_N = 6
_EMA_ALPHA = 2.0 / (_SMOOTH_N + 1)

# ---------------------------------------------------------------------------
# History lengths
# ---------------------------------------------------------------------------
_HISTORY_LEN         = 8
_STATIC_HISTORY_LEN  = 30   # ~2s at 15fps for sway/tremor
_CONFIDENCE_HIST_LEN = 20
_FATIGUE_BASELINE_N  = 60   # frames to establish baseline
_FATIGUE_WINDOW_N    = 30   # recent window for comparison

# ---------------------------------------------------------------------------
# Velocity thresholds
# ---------------------------------------------------------------------------
_REST_VELOCITY_THRESHOLD   = 0.008   # below this = user is still
_STATIC_VELOCITY_THRESHOLD = 0.012   # below this = static hold

# ---------------------------------------------------------------------------
# Height calibration
# ---------------------------------------------------------------------------
_CALIBRATION_FRAMES_REQUIRED = 10
# Shoulder-to-ankle span ≈ 88% of standing height for an upright person
# in MediaPipe's normalised output.
_SHOULDER_ANKLE_HEIGHT_RATIO = 0.88


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class IntensityResult:
    """Per-frame intensity estimation output."""
    multiplier: float              # final smoothed intensity multiplier [0.40,2.00]
    raw_multiplier: float          # unsmoothed value before EMA
    joint_velocity_score: float    # 0–1 from joint speeds
    com_displacement_score: float  # 0–1 from height-calibrated COM vertical velocity
    angular_velocity_score: float  # 0–1 from joint angular velocities
    rom_score: float               # 0–1 per-rep ROM fraction
    energy_proxy_score: float      # 0–1 external energy proxy (P2-I7)
    is_resting: bool               # True if near-zero movement
    is_static_hold: bool           # True if static hold detected (P1-I5)
    static_effort_score: float     # 0.5–1.5 static muscular effort proxy (P1-I5)
    static_hold_duration_s: float  # cumulative static hold time this segment
    motion_power_estimate: float   # informal units for logging
    general_activity_met: float    # MET tier for unclassified movement (P1-I4)
    calorie_confidence: float      # 0–1 internal consistency estimate (P1-I6)
    calorie_ci_relative_error: float  # relative half-width of CI, e.g. 0.15=±15%
    fatigue_multiplier: float      # 1.0–1.15 metabolic cost increase proxy (P2-I8)
    fatigue_index: float           # 0–1 fatigue indicator
    symmetry_index: float          # 0–1, 1.0 = perfectly symmetric (P2-I9)


@dataclass
class _LandmarkSnapshot:
    """Lightweight snapshot of landmark positions for one frame."""
    positions: dict[int, tuple[float, float, float]]
    timestamp: float


# ---------------------------------------------------------------------------
# Per-rep ROM tracker (P1-I3)
# ---------------------------------------------------------------------------

class _RepROMTracker:
    """
    Tracks ROM per rep phase using direction-reversal detection.

    Unlike the previous rolling-window approach (which measured angular
    velocity within a fixed window and over-scored fast movements), this
    tracks the total arc swept per rep phase.  A slow deep squat and a fast
    deep squat receive the same score if they reach the same joint angle.
    """

    def __init__(self) -> None:
        self.prev_angle: Optional[float] = None
        self.direction: int = 0        # +1 increasing, -1 decreasing, 0 unknown
        self.rep_min: float = float("inf")
        self.rep_max: float = float("-inf")
        self.completed_rom: float = 0.5  # last completed rep phase ROM fraction

    def update(self, angle: float, reference_range: float) -> float:
        if self.prev_angle is None:
            self.prev_angle = angle
            self.rep_min = angle
            self.rep_max = angle
            return self.completed_rom

        delta = angle - self.prev_angle
        if abs(delta) < 0.2:
            self.prev_angle = angle
            return self.completed_rom

        new_direction = 1 if delta > 0 else -1
        self.rep_min = min(self.rep_min, angle)
        self.rep_max = max(self.rep_max, angle)

        if self.direction != 0 and new_direction != self.direction:
            observed = self.rep_max - self.rep_min
            if reference_range > 0:
                self.completed_rom = min(observed / reference_range, 1.0)
            self.rep_min = angle
            self.rep_max = angle

        self.direction = new_direction
        self.prev_angle = angle
        return self.completed_rom

    def reset(self) -> None:
        self.prev_angle = None
        self.direction = 0
        self.rep_min = float("inf")
        self.rep_max = float("-inf")
        self.completed_rom = 0.5


# ---------------------------------------------------------------------------
# IntensityEstimator
# ---------------------------------------------------------------------------

class IntensityEstimator:
    """
    Estimates per-frame movement intensity from MediaPipe pose landmarks.

    Args:
        fps:      Expected frame rate (dt fallback guard).
        height_m: User's standing height in metres from their profile.
                  Used for height-calibrated COM scaling (P1-I1).
                  Pass 0.0 to disable — falls back to uncalibrated mode.
    """

    def __init__(self, fps: float = 15.0, height_m: float = 0.0) -> None:
        self._fps = fps
        self._height_m = height_m

        self._history: deque[_LandmarkSnapshot] = deque(maxlen=_HISTORY_LEN)
        self._angle_history: deque[dict[str, float]] = deque(maxlen=_HISTORY_LEN)
        self._smoothed_multiplier: float = 1.0

        # Height calibration (P1-I1)
        self._scale_samples: list[float] = []
        self._scale_m_per_norm: float = 0.0

        # Per-rep ROM trackers keyed by exercise type (P1-I3)
        self._rom_trackers: dict[str, _RepROMTracker] = {}

        # Static hold state (P1-I5)
        self._com_y_buffer: deque[float] = deque(maxlen=_STATIC_HISTORY_LEN)
        self._static_hold_duration_s: float = 0.0

        # Confidence history (P1-I6)
        self._multiplier_history: deque[float] = deque(maxlen=_CONFIDENCE_HIST_LEN)

        # Fatigue state (P2-I8)
        self._baseline_velocity: float = 0.0
        self._baseline_rom: float = 0.0
        self._baseline_established: bool = False
        self._baseline_frame_count: int = 0
        self._baseline_vel_acc: float = 0.0
        self._baseline_rom_acc: float = 0.0
        self._recent_vel_buf: deque[float] = deque(maxlen=_FATIGUE_WINDOW_N)
        self._recent_rom_buf: deque[float] = deque(maxlen=_FATIGUE_WINDOW_N)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def update(
        self,
        landmarks: list[Any],
        angle_map: dict[str, float],
        exercise_type: Optional[str],
        elapsed_s: float,
        classifier_confidence: float = 0.5,
        weight_kg: float = 70.0,
    ) -> IntensityResult:
        """
        Process one frame and return the intensity result.

        Args:
            landmarks:             33 Landmark objects from CV pipeline.
            angle_map:             Joint angles from angle_utils.
            exercise_type:         Confirmed exercise, or None.
            elapsed_s:             Seconds since last frame (~0.067 at 15fps).
            classifier_confidence: Top-class probability from ML pipeline.
            weight_kg:             User weight in kg (for energy proxy, P2-I7).
        """
        if not landmarks or elapsed_s <= 0:
            return self._rest_result()

        pos: dict[int, tuple[float, float, float]] = {}
        for lm in landmarks:
            if hasattr(lm, "visibility") and lm.visibility >= 0.3:
                pos[lm.id] = (lm.x, lm.y, lm.z)

        snap = _LandmarkSnapshot(positions=pos, timestamp=elapsed_s)
        self._history.append(snap)
        self._angle_history.append(dict(angle_map))

        # Height calibration attempt (P1-I1)
        self._try_calibrate_height_scale(pos)

        if len(self._history) < 2:
            return self._rest_result()

        prev = self._history[-2]
        curr = self._history[-1]
        dt = max(elapsed_s, 1.0 / (self._fps * 2))

        # Component 1: joint linear velocities
        jv_score, is_resting, mean_velocity, max_velocity = self._joint_velocity_score(prev, curr, dt)

        # Component 2: COM vertical displacement (height-calibrated)
        com_y_curr = self._estimate_com_y(curr.positions)
        com_y_prev = self._estimate_com_y(prev.positions)
        self._com_y_buffer.append(com_y_curr)
        com_score = self._com_displacement_score(com_y_curr, com_y_prev, dt)

        # Component 3: angular velocities
        av_score = self._angular_velocity_score(dt)

        # Component 4: per-rep ROM (P1-I3)
        rom_score = self._rom_score_per_rep(angle_map, exercise_type)

        # Component 5: external energy proxy (P2-I7)
        energy_score = self._energy_proxy_score(com_y_curr, com_y_prev, dt, weight_kg)

        # Static hold detection (P1-I5)
        static_effort, is_static = self._static_effort_score(max_velocity, angle_map, dt)

        # General activity MET for unclassified periods (P1-I4)
        general_met = self._general_activity_met(pos, prev, dt) if exercise_type is None else 0.0

        # Fatigue multiplier (P2-I8)
        fatigue_mult, fatigue_idx = self._update_fatigue(mean_velocity, rom_score)

        # Symmetry index (P2-I9)
        sym_idx = self._symmetry_score(prev, curr, dt)

        # Combine components into raw score
        if is_static:
            # Static hold: override with isometric effort proxy, skip velocity weighting
            raw_multiplier = static_effort
        elif exercise_type == "plank":
            raw = (0.20 * jv_score + 0.20 * com_score +
                   0.20 * av_score + 0.30 * rom_score + 0.10 * energy_score)
            raw_multiplier = 1.0 + (raw - 0.5) * 1.60
        elif exercise_type in ("bicep_curl", "shoulder_press"):
            raw = (0.42 * jv_score + 0.08 * com_score +
                   0.22 * av_score + 0.18 * rom_score + 0.10 * energy_score)
            raw_multiplier = 1.0 + (raw - 0.5) * 1.60
        elif exercise_type is not None:
            # Lower-body / compound
            raw = (0.35 * jv_score + 0.22 * com_score +
                   0.18 * av_score + 0.15 * rom_score + 0.10 * energy_score)
            raw_multiplier = 1.0 + (raw - 0.5) * 1.60
        else:
            # Unclassified — multiplier unused; general_met drives calories
            raw = 0.35 * jv_score + 0.22 * com_score + 0.18 * av_score
            raw_multiplier = 1.0 + (raw - 0.5) * 1.60

        # Apply fatigue multiplier before clamping (P2-I8)
        raw_multiplier = raw_multiplier * fatigue_mult

        raw_multiplier = max(_MIN_MULTIPLIER, min(_MAX_MULTIPLIER, raw_multiplier))

        # EMA smoothing
        self._smoothed_multiplier = (
            _EMA_ALPHA * raw_multiplier + (1.0 - _EMA_ALPHA) * self._smoothed_multiplier
        )
        self._multiplier_history.append(self._smoothed_multiplier)

        # Confidence score (P1-I6)
        confidence, ci_err = self._compute_confidence(len(pos), classifier_confidence)

        return IntensityResult(
            multiplier=round(self._smoothed_multiplier, 4),
            raw_multiplier=round(raw_multiplier, 4),
            joint_velocity_score=round(jv_score, 4),
            com_displacement_score=round(com_score, 4),
            angular_velocity_score=round(av_score, 4),
            rom_score=round(rom_score, 4),
            energy_proxy_score=round(energy_score, 4),
            is_resting=is_resting,
            is_static_hold=is_static,
            static_effort_score=round(static_effort, 4),
            static_hold_duration_s=round(self._static_hold_duration_s, 2),
            motion_power_estimate=round(max_velocity * raw_multiplier, 4),
            general_activity_met=round(general_met, 3),
            calorie_confidence=round(confidence, 4),
            calorie_ci_relative_error=round(ci_err, 4),
            fatigue_multiplier=round(fatigue_mult, 4),
            fatigue_index=round(fatigue_idx, 4),
            symmetry_index=round(sym_idx, 4),
        )

    def reset(self) -> None:
        """Clear per-exercise history. Keeps height calibration and baseline."""
        self._history.clear()
        self._angle_history.clear()
        self._smoothed_multiplier = 1.0
        self._rom_trackers.clear()
        self._com_y_buffer.clear()
        self._static_hold_duration_s = 0.0
        self._multiplier_history.clear()
        # Fatigue baseline persists across exercise changes within a session.
        self._recent_vel_buf.clear()
        self._recent_rom_buf.clear()

    # ------------------------------------------------------------------
    # Height calibration (P1-I1)
    # ------------------------------------------------------------------

    def _try_calibrate_height_scale(
        self, positions: dict[int, tuple[float, float, float]]
    ) -> None:
        if self._height_m <= 0.0:
            return
        if len(self._scale_samples) >= _CALIBRATION_FRAMES_REQUIRED:
            return
        required = [_LM["l_shoulder"], _LM["r_shoulder"], _LM["l_ankle"], _LM["r_ankle"]]
        if not all(lid in positions for lid in required):
            return
        shoulder_mid_y = (positions[_LM["l_shoulder"]][1] + positions[_LM["r_shoulder"]][1]) / 2.0
        ankle_mid_y    = (positions[_LM["l_ankle"]][1]    + positions[_LM["r_ankle"]][1])    / 2.0
        span_norm = ankle_mid_y - shoulder_mid_y
        if span_norm < 0.05:
            return
        scale = self._height_m / (span_norm * _SHOULDER_ANKLE_HEIGHT_RATIO)
        self._scale_samples.append(scale)
        if len(self._scale_samples) >= _CALIBRATION_FRAMES_REQUIRED:
            sorted_s = sorted(self._scale_samples)
            n = len(sorted_s)
            self._scale_m_per_norm = (sorted_s[n // 2] if n % 2 else
                                      (sorted_s[n // 2 - 1] + sorted_s[n // 2]) / 2.0)

    # ------------------------------------------------------------------
    # Joint velocity (Component 1)
    # ------------------------------------------------------------------

    def _joint_velocity_score(
        self, prev: _LandmarkSnapshot, curr: _LandmarkSnapshot, dt: float
    ) -> tuple[float, bool, float, float]:
        velocities: list[float] = []
        for lm_id in _VELOCITY_JOINTS:
            if lm_id in prev.positions and lm_id in curr.positions:
                dx = curr.positions[lm_id][0] - prev.positions[lm_id][0]
                dy = curr.positions[lm_id][1] - prev.positions[lm_id][1]
                velocities.append(math.sqrt(dx * dx + dy * dy) / dt)
        if not velocities:
            return 0.0, True, 0.0, 0.0
        mean_v = sum(velocities) / len(velocities)
        max_v  = max(velocities)
        is_resting = max_v < _REST_VELOCITY_THRESHOLD
        score = min(mean_v / 0.20, 1.0)
        return score, is_resting, mean_v, max_v

    # ------------------------------------------------------------------
    # COM estimation + displacement (Component 2, P1-I1)
    # ------------------------------------------------------------------

    def _estimate_com_y(self, positions: dict[int, tuple[float, float, float]]) -> float:
        segments = [
            (_LM["l_shoulder"], _LM["l_elbow"],  "l_upper_arm"),
            (_LM["r_shoulder"], _LM["r_elbow"],  "r_upper_arm"),
            (_LM["l_elbow"],    _LM["l_wrist"],  "l_forearm"),
            (_LM["r_elbow"],    _LM["r_wrist"],  "r_forearm"),
            (_LM["l_hip"],      _LM["l_knee"],   "l_thigh"),
            (_LM["r_hip"],      _LM["r_knee"],   "r_thigh"),
            (_LM["l_knee"],     _LM["l_ankle"],  "l_shank"),
            (_LM["r_knee"],     _LM["r_ankle"],  "r_shank"),
        ]
        if all(i in positions for i in [_LM["l_shoulder"], _LM["r_shoulder"],
                                         _LM["l_hip"],      _LM["r_hip"]]):
            trunk_y = (positions[_LM["l_shoulder"]][1] + positions[_LM["r_shoulder"]][1] +
                       positions[_LM["l_hip"]][1]      + positions[_LM["r_hip"]][1]) / 4.0
        else:
            trunk_y = 0.5
        w_sum = trunk_y * _SEGMENT_MASS_FRACTION["trunk"]
        w_tot = _SEGMENT_MASS_FRACTION["trunk"]
        for p_id, d_id, key in segments:
            if p_id in positions and d_id in positions:
                seg_y = (positions[p_id][1] + positions[d_id][1]) / 2.0
                frac  = _SEGMENT_MASS_FRACTION.get(key, 0.02)
                w_sum += seg_y * frac
                w_tot += frac
        return w_sum / w_tot if w_tot else 0.5

    def _com_displacement_score(self, com_y_curr: float, com_y_prev: float, dt: float) -> float:
        delta_y_norm = abs(com_y_curr - com_y_prev)
        if self._scale_m_per_norm > 0.0:
            com_vy_m = delta_y_norm * self._scale_m_per_norm / dt
            return min(com_vy_m / 0.15, 1.0)
        return min((delta_y_norm / dt) / 0.10, 1.0)

    # ------------------------------------------------------------------
    # Angular velocity (Component 3)
    # ------------------------------------------------------------------

    def _angular_velocity_score(self, dt: float) -> float:
        if len(self._angle_history) < 2:
            return 0.0
        avs = [abs(self._angle_history[-1][j] - self._angle_history[-2][j]) / dt
               for j in self._angle_history[-1] if j in self._angle_history[-2]]
        if not avs:
            return 0.0
        return min(sum(avs) / len(avs) / 150.0, 1.0)

    # ------------------------------------------------------------------
    # Per-rep ROM (Component 4, P1-I3)
    # ------------------------------------------------------------------

    def _rom_score_per_rep(
        self, angle_map: dict[str, float], exercise_type: Optional[str]
    ) -> float:
        if exercise_type is None or exercise_type not in _ROM_REFS:
            return 0.5
        joint_name, rom_min, rom_max = _ROM_REFS[exercise_type]
        if joint_name not in angle_map:
            return 0.5
        reference_range = rom_max - rom_min
        if reference_range <= 0:
            return 0.5
        if exercise_type not in self._rom_trackers:
            self._rom_trackers[exercise_type] = _RepROMTracker()
        return self._rom_trackers[exercise_type].update(
            angle_map[joint_name], reference_range
        )

    # ------------------------------------------------------------------
    # External energy proxy (Component 5, P2-I7)
    # ------------------------------------------------------------------

    def _energy_proxy_score(
        self, com_y_curr: float, com_y_prev: float, dt: float, weight_kg: float
    ) -> float:
        """
        Approximate external mechanical energy proxy from 2D COM displacement.

        This is NOT true mechanical work.  It estimates ΔPE + ΔKE from
        vertical COM motion scaled by user height.  It does not account for
        horizontal motion, rotational energy, internal work, or depth-direction
        movement from a monocular RGB camera.  Use as a heuristic signal only.
        """
        if self._scale_m_per_norm <= 0.0:
            return 0.0
        delta_y_m = (com_y_curr - com_y_prev) * self._scale_m_per_norm
        delta_pe  = weight_kg * _GRAVITY_M_S2 * abs(delta_y_m)
        v_com     = delta_y_m / dt
        delta_ke  = 0.5 * weight_kg * v_com * v_com
        w_proxy   = delta_pe + delta_ke
        kcal      = w_proxy / (_MECHANICAL_EFFICIENCY_APPROX * 4184.0)
        # 0.0003 kcal/frame ≈ active squat at 15fps — used only for normalisation
        return min(kcal / 0.0003, 1.0)

    # ------------------------------------------------------------------
    # Static hold model (P1-I5)
    # ------------------------------------------------------------------

    def _static_effort_score(
        self, max_velocity: float, angle_map: dict[str, float], dt: float
    ) -> tuple[float, bool]:
        """
        Estimate isometric muscular effort from postural sway and joint tremor.

        Returns (static_effort_score, is_static_hold).
        Sway proxy: Paillard (2012) — sway amplitude correlates with postural
        control cost during static holds.  Joint tremor is an additional proxy.
        These are approximations, not direct measurements of isometric force.
        """
        if max_velocity >= _STATIC_VELOCITY_THRESHOLD:
            self._static_hold_duration_s = 0.0
            return 0.0, False

        self._static_hold_duration_s += dt

        if len(self._com_y_buffer) >= 5:
            sway = statistics.stdev(self._com_y_buffer)
        else:
            sway = 0.0

        tremors: list[float] = []
        if len(self._angle_history) >= 5:
            for joint in list(self._angle_history[-1].keys()):
                vals = [f[joint] for f in self._angle_history if joint in f]
                if len(vals) >= 5:
                    tremors.append(statistics.stdev(vals))
        joint_tremor = sum(tremors) / len(tremors) if tremors else 0.0

        sway_contrib   = min(sway        / 0.005, 0.5)
        tremor_contrib = min(joint_tremor / 3.0,  0.5)
        static_effort  = 0.5 + sway_contrib + tremor_contrib
        return static_effort, True

    # ------------------------------------------------------------------
    # General activity (P1-I4)
    # ------------------------------------------------------------------

    def _general_activity_met(
        self, positions: dict[int, tuple[float, float, float]],
        prev: _LandmarkSnapshot, dt: float
    ) -> float:
        all_vels: list[float] = []
        for lm_id, (cx, cy, _) in positions.items():
            if lm_id in prev.positions:
                px, py = prev.positions[lm_id][0], prev.positions[lm_id][1]
                all_vels.append(math.sqrt((cx - px) ** 2 + (cy - py) ** 2) / dt)
        total_motion = sum(all_vels) / len(all_vels) if all_vels else 0.0
        for threshold, met in _GENERAL_ACTIVITY_TIERS:
            if total_motion < threshold:
                return met
        return _GENERAL_ACTIVITY_TIERS[-1][1]

    # ------------------------------------------------------------------
    # Confidence score (P1-I6)
    # ------------------------------------------------------------------

    def _compute_confidence(
        self, landmark_count: int, classifier_confidence: float
    ) -> tuple[float, float]:
        landmark_completeness = min(landmark_count / 20.0, 1.0)
        if len(self._multiplier_history) >= 5:
            m_std  = statistics.stdev(self._multiplier_history)
            m_mean = statistics.mean(self._multiplier_history)
            stability     = 1.0 - min(m_std / 0.5, 1.0)
            relative_err  = min(m_std / (m_mean + 1e-6), 0.50)
        else:
            stability    = 0.5
            relative_err = 0.30
        confidence = (0.35 * landmark_completeness +
                      0.40 * classifier_confidence +
                      0.25 * stability)
        return confidence, relative_err

    # ------------------------------------------------------------------
    # Fatigue (P2-I8)
    # ------------------------------------------------------------------

    def _update_fatigue(
        self, mean_velocity: float, rom_fraction: float
    ) -> tuple[float, float]:
        """
        Proxy for fatigue-related metabolic cost increase.

        As velocity and ROM decline relative to session baseline, muscles
        require greater neural activation per unit mechanical output (Enoka 2012).
        This is a heuristic approximation — it does not measure metabolic rate.
        """
        self._recent_vel_buf.append(mean_velocity)
        self._recent_rom_buf.append(rom_fraction)

        if not self._baseline_established:
            self._baseline_frame_count += 1
            self._baseline_vel_acc += mean_velocity
            self._baseline_rom_acc += rom_fraction
            if self._baseline_frame_count >= _FATIGUE_BASELINE_N:
                n = self._baseline_frame_count
                self._baseline_velocity = self._baseline_vel_acc / n
                self._baseline_rom      = self._baseline_rom_acc / n
                self._baseline_established = True
            return 1.0, 0.0

        recent_vel = (sum(self._recent_vel_buf) / len(self._recent_vel_buf)
                      if self._recent_vel_buf else self._baseline_velocity)
        recent_rom = (sum(self._recent_rom_buf) / len(self._recent_rom_buf)
                      if self._recent_rom_buf else self._baseline_rom)

        vel_ratio = recent_vel / (self._baseline_velocity + 1e-6)
        rom_ratio = recent_rom / (self._baseline_rom + 1e-6)
        fatigue_idx = max(0.0, min(1.0, 1.0 - 0.5 * vel_ratio - 0.5 * rom_ratio))
        fatigue_mult = 1.0 + 0.15 * fatigue_idx
        return fatigue_mult, fatigue_idx

    # ------------------------------------------------------------------
    # Symmetry (P2-I9)
    # ------------------------------------------------------------------

    def _symmetry_score(
        self, prev: _LandmarkSnapshot, curr: _LandmarkSnapshot, dt: float
    ) -> float:
        """
        Left/right velocity asymmetry index.

        Informational only — not fed into the multiplier calculation.
        Its relationship to calorie expenditure is not well-established
        from pose landmarks alone.
        """
        def side_vel(ids: list[int]) -> float:
            vels = []
            for lm_id in ids:
                if lm_id in prev.positions and lm_id in curr.positions:
                    dx = curr.positions[lm_id][0] - prev.positions[lm_id][0]
                    dy = curr.positions[lm_id][1] - prev.positions[lm_id][1]
                    vels.append(math.sqrt(dx * dx + dy * dy) / dt)
            return sum(vels) / len(vels) if vels else 0.0

        lv = side_vel(_LEFT_JOINTS)
        rv = side_vel(_RIGHT_JOINTS)
        return 1.0 - abs(lv - rv) / (lv + rv + 1e-6)

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------

    def _rest_result(self) -> IntensityResult:
        return IntensityResult(
            multiplier=_MIN_MULTIPLIER, raw_multiplier=_MIN_MULTIPLIER,
            joint_velocity_score=0.0, com_displacement_score=0.0,
            angular_velocity_score=0.0, rom_score=0.0, energy_proxy_score=0.0,
            is_resting=True, is_static_hold=False, static_effort_score=0.0,
            static_hold_duration_s=0.0, motion_power_estimate=0.0,
            general_activity_met=1.3, calorie_confidence=0.0,
            calorie_ci_relative_error=0.5, fatigue_multiplier=1.0,
            fatigue_index=0.0, symmetry_index=1.0,
        )
