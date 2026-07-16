"""
TASK-4.4 — Validate exercise classifier confidence distributions.

Loads models/exercise_classifier.pkl and data/raw/ CSVs.
For each exercise class, holds out a sample and prints per-class
confidence distributions to verify the 0.6 threshold is meaningful.

Usage:
    & "d:\burn-ex 1\burn-ex final\backend\venv\Scripts\python.exe" ^
        data/validate_classifier.py
"""

import os
import sys
import glob

import numpy as np
import pandas as pd
import joblib

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
_RAW_DIR = os.path.join(_HERE, "raw")
_MODEL_PATH = os.path.join(_PROJECT_ROOT, "models", "exercise_classifier.pkl")

FEATURE_ANGLES = [
    "left_knee",
    "right_knee",
    "left_hip",
    "right_hip",
    "left_elbow",
    "right_elbow",
    "left_shoulder",
    "right_shoulder",
    "trunk",
    "left_ankle",
]

CONFIDENCE_THRESHOLD = 0.6
HELD_OUT_FRACTION = 0.20


def load_model(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Model not found at {path}. Run data/train_classifier.py first."
        )
    return joblib.load(path)


def load_raw_data(raw_dir: str) -> pd.DataFrame:
    csv_files = glob.glob(os.path.join(raw_dir, "*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSVs in {raw_dir}")
    frames = []
    for path in sorted(csv_files):
        df = pd.read_csv(path)
        if "label" in df.columns:
            frames.append(df)
    if not frames:
        raise ValueError("No valid data loaded.")
    return pd.concat(frames, ignore_index=True)


def prepare_features(df: pd.DataFrame) -> np.ndarray:
    for col in FEATURE_ANGLES:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            df[col] = df[col].fillna(df[col].median())
        else:
            df[col] = 0.0
    return df[FEATURE_ANGLES].values.astype(np.float32)


def print_bar(value: float, width: int = 30) -> str:
    filled = int(value * width)
    return "█" * filled + "░" * (width - filled)


def main() -> None:
    print("=" * 65)
    print("Burn-Ex Classifier Confidence Validation")
    print("=" * 65)

    # Load model
    try:
        clf = load_model(_MODEL_PATH)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    classes = clf.classes_.tolist()
    print(f"Model classes: {classes}\n")

    # Load data
    try:
        data = load_raw_data(_RAW_DIR)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    all_pass = True
    results = {}

    for cls in sorted(data["label"].unique()):
        cls_data = data[data["label"] == cls].copy()
        n_total = len(cls_data)

        # Hold out last HELD_OUT_FRACTION rows (different from training split)
        n_held = max(1, int(n_total * HELD_OUT_FRACTION))
        held = cls_data.tail(n_held).copy()

        X_held = prepare_features(held)

        # Get class probabilities
        proba = clf.predict_proba(X_held)  # shape (n, n_classes)
        cls_idx = classes.index(cls) if cls in classes else -1

        if cls_idx == -1:
            print(f"  {cls}: NOT IN MODEL CLASSES — skipping")
            continue

        cls_confidences = proba[:, cls_idx]
        median_conf = float(np.median(cls_confidences))
        mean_conf = float(np.mean(cls_confidences))
        p25 = float(np.percentile(cls_confidences, 25))
        p75 = float(np.percentile(cls_confidences, 75))
        above_threshold = float(np.mean(cls_confidences >= CONFIDENCE_THRESHOLD))

        passed = median_conf >= CONFIDENCE_THRESHOLD
        all_pass = all_pass and passed
        results[cls] = {
            "n_held_out": n_held,
            "median": median_conf,
            "mean": mean_conf,
            "p25": p25,
            "p75": p75,
            "pct_above_threshold": above_threshold,
            "passed": passed,
        }

        status = "PASS ✓" if passed else "FAIL ✗"
        print(f"  {cls:<20} n={n_held:>3}  median={median_conf:.3f}  "
              f"mean={mean_conf:.3f}  [{p25:.2f}–{p75:.2f}]  "
              f"{int(above_threshold*100):>3}% ≥ {CONFIDENCE_THRESHOLD}  "
              f"{status}")
        print(f"  {'':20} {print_bar(median_conf)}")
        print()

    print("=" * 65)
    print(f"Confidence threshold: {CONFIDENCE_THRESHOLD}")
    print(f"Requirement: median confidence > {CONFIDENCE_THRESHOLD} for all classes")
    print(f"Result: {'ALL CLASSES PASS ✓' if all_pass else 'SOME CLASSES FAILED ✗'}")
    print("=" * 65)

    if not all_pass:
        failed = [k for k, v in results.items() if not v["passed"]]
        print(f"\nFailing classes: {failed}")
        print("Recommendations:")
        print("  - Collect more diverse samples for failing classes")
        print("  - Ensure full-body visibility during collection")
        print("  - Check for class imbalance and re-train")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
