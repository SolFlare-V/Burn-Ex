"""
TASK-4.3 — Train exercise classifier from collected landmark CSVs.

Loads all CSVs from data/raw/, trains a RandomForestClassifier,
prints a classification report, and saves the model to
models/exercise_classifier.pkl.

Usage:
    & "d:\burn-ex 1\burn-ex final\backend\venv\Scripts\python.exe" ^
        data/train_classifier.py
"""

import os
import sys
import glob

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import classification_report, accuracy_score
from sklearn.preprocessing import LabelEncoder

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
_RAW_DIR = os.path.join(_HERE, "raw")
_MODEL_PATH = os.path.join(_PROJECT_ROOT, "models", "exercise_classifier.pkl")

# 10 feature angle names — must match collect_landmarks.py and feature_extractor.py
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


def load_dataset(raw_dir: str) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """
    Load and concatenate all CSVs from raw_dir.

    Returns:
        X: float array (N, 10)
        y: str array (N,)
        classes: sorted list of class names
    """
    csv_files = glob.glob(os.path.join(raw_dir, "*.csv"))
    if not csv_files:
        raise FileNotFoundError(
            f"No CSV files found in {raw_dir}. "
            "Run collect_landmarks.py first (TASK-4.2)."
        )

    frames = []
    for path in sorted(csv_files):
        df = pd.read_csv(path)
        if "label" not in df.columns:
            print(f"  WARNING: {path} has no 'label' column — skipping.")
            continue
        frames.append(df)
        print(f"  Loaded {path}: {len(df)} rows, label={df['label'].unique().tolist()}")

    if not frames:
        raise ValueError("No valid CSV files loaded.")

    data = pd.concat(frames, ignore_index=True)
    print(f"\n  Total rows: {len(data)}")
    print(f"  Class distribution:\n{data['label'].value_counts().to_string()}\n")

    # Fill missing angle values with column median (handles occluded angles)
    for col in FEATURE_ANGLES:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")
            data[col] = data[col].fillna(data[col].median())
        else:
            print(f"  WARNING: Feature column '{col}' not found — filling with 0.")
            data[col] = 0.0

    X = data[FEATURE_ANGLES].values.astype(np.float32)
    y = data["label"].values
    classes = sorted(data["label"].unique().tolist())

    return X, y, classes


def train(X: np.ndarray, y: np.ndarray, classes: list[str]) -> RandomForestClassifier:
    """Train and evaluate a RandomForestClassifier."""
    print("=" * 60)
    print("Training RandomForestClassifier")
    print("=" * 60)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    print(f"  Train: {len(X_train)} samples | Test: {len(X_test)} samples")

    clf = RandomForestClassifier(
        n_estimators=300,
        max_depth=None,
        min_samples_split=4,
        min_samples_leaf=2,
        class_weight="balanced",  # sklearn balances by inverse class frequency
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)

    # Test-set evaluation
    y_pred = clf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)

    print(f"\n  Test-set accuracy: {acc:.4f} ({acc*100:.1f}%)")
    if acc < 0.85:
        print(f"  WARNING: Accuracy {acc:.2f} is below the required 0.85 threshold.")
        print("  Consider collecting more data or balancing classes.")
    else:
        print(f"  Accuracy meets ≥ 0.85 requirement ✓")

    print("\nClassification Report (test set):")
    print(classification_report(y_test, y_pred, target_names=classes))

    # 5-fold cross-validation on full dataset for robustness estimate
    cv_scores = cross_val_score(clf, X, y, cv=5, scoring="accuracy", n_jobs=-1)
    print(f"5-fold CV accuracy: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

    # Feature importances
    print("\nFeature importances:")
    importances = sorted(
        zip(FEATURE_ANGLES, clf.feature_importances_),
        key=lambda x: x[1],
        reverse=True,
    )
    for name, imp in importances:
        bar = "█" * int(imp * 40)
        print(f"  {name:<20} {imp:.4f}  {bar}")

    return clf


def save_model(clf: RandomForestClassifier, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(clf, path)
    size_kb = os.path.getsize(path) / 1024
    print(f"\nModel saved to: {path} ({size_kb:.1f} KB)")


def main() -> None:
    print(f"Loading dataset from: {_RAW_DIR}\n")

    try:
        X, y, classes = load_dataset(_RAW_DIR)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    clf = train(X, y, classes)
    save_model(clf, _MODEL_PATH)

    print("\nDone. Run data/validate_classifier.py to check confidence distributions.")


if __name__ == "__main__":
    main()
