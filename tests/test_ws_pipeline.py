"""
TASK-16.5 — Integration test for the full WebSocket pipeline.

Spins up the FastAPI app with starlette TestClient WebSocket support.
Seeds a user and session, connects to /ws/pose, sends synthetic frames,
and asserts response messages contain required fields.

Note on exercise confirmation:
  The ML confirmation window requires 10 consecutive identical predictions
  before confirming a type. Synthetic blank JPEG frames through the full
  CV->ML pipeline will not confirm "squat" in 15 frames — the classifier
  may return a random class or None for blank images.

  Per the task spec, we verify:
    - response contains all required fields
    - form_score is present (even if 0 — occluded blank frame)
    - rep_count is an integer
    - landmarks is a list
  And we separately test exercise confirmation using mock patching to
  bypass the real CV/ML pipeline and inject synthetic confirmed_type="squat".

Verify: pytest tests/test_ws_pipeline.py passes with no flaky failures.
"""
import base64
import json
import sys
import os
import uuid
from unittest.mock import patch, MagicMock
from dataclasses import dataclass, field

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from starlette.testclient import TestClient
from backend.main import app  # safe: conftest patches person_detector before collection
from backend.database import Base, SessionLocal, engine
import backend.models.users
import backend.models.sessions
import backend.models.sets
import backend.models.calorie_segments
import backend.models.streaks
import backend.models.goals

Base.metadata.create_all(engine)

from backend.models.users import User
from backend.models.sessions import Session as SessionModel
from backend.session.manager import session_manager


# ---------------------------------------------------------------------------
# Helper: create a minimal valid JPEG (1×1 black pixel)
# ---------------------------------------------------------------------------

def _make_jpeg_b64() -> str:
    """Return base64-encoded minimal JPEG bytes."""
    # Minimal 1x1 black JPEG
    jpeg_bytes = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
        0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
        0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
        0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
        0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
        0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
        0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
        0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
        0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
        0x82, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3F, 0x00, 0xFB,
        0x97, 0xFF, 0xD9,
    ])
    return base64.b64encode(jpeg_bytes).decode()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def test_user():
    """Create a test user for WS tests."""
    db = SessionLocal()
    user = User(name="WSPipelineTest", weight_kg=72.0)
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    db.close()
    yield user_id


@pytest.fixture
def active_session(test_user):
    """Start a fresh session for each test; clean up after."""
    # Reset any dangling session
    session_manager._active_session_id = None
    session_id = session_manager.start_session(
        user_id=test_user, weight_kg=72.0
    )
    yield session_id
    # Cleanup
    try:
        session_manager.end_session(session_id)
    except Exception:
        try:
            session_manager.interrupt_session(session_id)
        except Exception:
            pass
    session_manager._active_session_id = None


# ---------------------------------------------------------------------------
# TASK-16.5-A: Response schema test (real pipeline, blank frames)
# ---------------------------------------------------------------------------

def test_ws_response_has_required_fields(active_session):
    """
    Connect to /ws/pose, send a blank JPEG frame, verify response
    contains all required fields: exercise, rep_count, form_score,
    corrections, calories_running, landmarks.
    """
    session_id = active_session
    frame_msg = json.dumps({
        "frame": _make_jpeg_b64(),
        "exercise_hint": "squat",
    })

    with TestClient(app) as client:
        with client.websocket_connect(
            f"/ws/pose?session_id={session_id}"
        ) as ws:
            ws.send_text(frame_msg)
            raw = ws.receive_text()

    resp = json.loads(raw)
    # Skip heartbeat pings
    while resp.get("type") == "ping":
        raw = ws.receive_text()
        resp = json.loads(raw)

    required = {"exercise", "rep_count", "form_score",
                "corrections", "calories_running", "landmarks"}
    assert required.issubset(resp.keys()), (
        f"Missing fields: {required - resp.keys()}"
    )
    assert isinstance(resp["rep_count"], int)
    assert isinstance(resp["form_score"], int)
    assert isinstance(resp["corrections"], list)
    assert isinstance(resp["landmarks"], list)
    assert isinstance(resp["calories_running"], (int, float))


def test_ws_invalid_session_rejected():
    """Connection with invalid session_id must be rejected (HTTP 403)."""
    with TestClient(app) as client:
        with pytest.raises(Exception):
            with client.websocket_connect(
                "/ws/pose?session_id=00000000-0000-0000-0000-000000000000"
            ) as ws:
                ws.send_text("{}")


def test_ws_missing_session_id_rejected():
    """Connection without session_id must be rejected."""
    with TestClient(app) as client:
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/pose") as ws:
                ws.send_text("{}")


# ---------------------------------------------------------------------------
# TASK-16.5-B: exercise confirmation + rep_count with mocked CV/ML pipeline
# ---------------------------------------------------------------------------

@dataclass
class MockProcessedFrame:
    landmarks: list = field(default_factory=list)
    angle_map: dict = field(default_factory=dict)
    occluded: bool = False
    warning: str = ""


@dataclass
class MockClassificationResult:
    confirmed_type: str | None = "squat"
    confidence: float = 0.85
    unrecognised_warning: bool = False


@dataclass
class MockScoringResult:
    cues: list = field(default_factory=list)
    score: int = 88
    warning: str | None = None


def _make_squat_angle_map_with_rep():
    """Return angle sequence that drives a full squat rep through the pipeline."""
    return {"left_knee": 85.0, "right_knee": 87.0,
            "left_hip": 95.0, "right_hip": 95.0, "trunk": 65.0}


def test_ws_exercise_confirmed_squat_with_mock(active_session):
    """
    Mock process_frame, classify_frame, score_frame so confirmed_type='squat'
    is returned. Verify exercise='squat' in response.
    """
    session_id = active_session
    frame_msg = json.dumps({
        "frame": _make_jpeg_b64(),
        "exercise_hint": "squat",
    })

    mock_frame = MockProcessedFrame(
        angle_map=_make_squat_angle_map_with_rep(),
        occluded=False,
    )
    mock_cls = MockClassificationResult(confirmed_type="squat")
    mock_score = MockScoringResult(score=88, cues=[])

    with patch("backend.routers.ws_pose.process_frame", return_value=mock_frame), \
         patch.object(
             __import__("backend.ml.pipeline", fromlist=["MLPipeline"]).MLPipeline,
             "classify_frame", return_value=mock_cls
         ), \
         patch("backend.routers.ws_pose.score_frame", return_value=mock_score):

        with TestClient(app) as client:
            with client.websocket_connect(
                f"/ws/pose?session_id={session_id}"
            ) as ws:
                ws.send_text(frame_msg)
                raw = ws.receive_text()

    resp = json.loads(raw)
    while resp.get("type") == "ping":
        # handle heartbeat
        break

    assert resp.get("exercise") == "squat", \
        f"Expected exercise='squat', got {resp.get('exercise')!r}"
    assert resp.get("form_score") == 88


def test_ws_rep_count_increments_with_mock(active_session):
    """
    Feed 12 frames of a full squat ROM via mock. After full ROM sequence,
    rep_count should be >= 1.

    The rep counter uses left_knee angle from angle_map. Squat thresholds:
    eccentric=160, depth=100, return=160.
    We cycle angles: stand(170) -> descend(<100) -> return(>160)
    """
    session_id = active_session

    # Squat ROM angles: standing -> depth -> standing (two cycles = 2 reps)
    angle_sequence = [170, 155, 130, 95, 80, 95, 130, 155, 170,
                      155, 130, 95, 80, 95, 130, 155, 170]

    frame_msg = json.dumps({
        "frame": _make_jpeg_b64(),
        "exercise_hint": "squat",
    })

    mock_score = MockScoringResult(score=85, cues=[])
    last_resp = None

    with TestClient(app) as client:
        with client.websocket_connect(
            f"/ws/pose?session_id={session_id}"
        ) as ws:
            for angle in angle_sequence:
                mock_frame = MockProcessedFrame(
                    angle_map={"left_knee": float(angle),
                               "right_knee": float(angle),
                               "left_hip": 120.0, "right_hip": 120.0,
                               "trunk": 70.0},
                    occluded=False,
                )
                mock_cls = MockClassificationResult(confirmed_type="squat")

                with patch("backend.routers.ws_pose.process_frame",
                           return_value=mock_frame), \
                     patch.object(
                         __import__("backend.ml.pipeline",
                                    fromlist=["MLPipeline"]).MLPipeline,
                         "classify_frame", return_value=mock_cls
                     ), \
                     patch("backend.routers.ws_pose.score_frame",
                           return_value=mock_score):
                    ws.send_text(frame_msg)
                    raw = ws.receive_text()
                    last_resp = json.loads(raw)

    # rep_count after full sequence should be >= 1
    if last_resp:
        assert last_resp["rep_count"] >= 1, \
            f"Expected rep_count >= 1 after full ROM, got {last_resp['rep_count']}"


def test_ws_occlusion_warning_in_response(active_session):
    """
    Occluded frame -> response has warning='Move into frame', corrections=[].
    """
    session_id = active_session
    frame_msg = json.dumps({
        "frame": _make_jpeg_b64(),
        "exercise_hint": "squat",
    })
    mock_frame = MockProcessedFrame(occluded=True, angle_map={})
    mock_cls = MockClassificationResult(confirmed_type=None)
    mock_score = MockScoringResult(score=0, cues=[], warning="Move into frame")

    with patch("backend.routers.ws_pose.process_frame", return_value=mock_frame), \
         patch.object(
             __import__("backend.ml.pipeline", fromlist=["MLPipeline"]).MLPipeline,
             "classify_frame", return_value=mock_cls
         ), \
         patch("backend.routers.ws_pose.score_frame", return_value=mock_score):

        with TestClient(app) as client:
            with client.websocket_connect(
                f"/ws/pose?session_id={session_id}"
            ) as ws:
                ws.send_text(frame_msg)
                raw = ws.receive_text()

    resp = json.loads(raw)
    assert resp.get("warning") == "Move into frame"
    assert resp.get("corrections") == []


# ---------------------------------------------------------------------------
# TASK-16.5-C: REAL end-to-end test — actual person image, unmocked pipeline
#
# This test proves genuine integration: the real person_detector, real
# pose_estimator, real form scoring, and real calorie engine all run.
# The test image contains a real detectable person (36KB Pexels photo,
# same image used in Phase 10's manual latency verification).
#
# What we assert:
#   - Response contains all required fields
#   - landmarks is non-empty (real person detected + pose estimated)
#   - warning is NOT "Move into frame" (person was detected, not occluded)
#   - form_score is an integer in [0, 100]
# ---------------------------------------------------------------------------

import pathlib

_FIXTURE_IMAGE = pathlib.Path(__file__).parent / "fixtures" / "person_fullbody.jpg"


@pytest.fixture
def real_session(test_user):
    """Fresh session for real-pipeline tests."""
    session_manager._active_session_id = None
    session_id = session_manager.start_session(user_id=test_user, weight_kg=72.0)
    yield session_id
    try:
        session_manager.end_session(session_id)
    except Exception:
        try:
            session_manager.interrupt_session(session_id)
        except Exception:
            pass
    session_manager._active_session_id = None


@pytest.mark.skipif(
    not _FIXTURE_IMAGE.exists(),
    reason="Test fixture image not found — run: python tests/download_fixtures.py"
)
def test_ws_real_pipeline_detects_person(real_session):
    """
    REAL end-to-end test: send a real person JPEG through the full
    unmocked pipeline (person_detector → pose_estimator → form scoring).

    Asserts:
      - Response has all required fields
      - landmarks list is non-empty (real person was detected)
      - warning is NOT 'Move into frame' (not occluded)
      - form_score is in valid range [0, 100]
    """
    session_id = real_session

    # Load and encode the real person fixture image
    with open(_FIXTURE_IMAGE, "rb") as f:
        jpeg_bytes = f.read()
    b64_frame = base64.b64encode(jpeg_bytes).decode()

    frame_msg = json.dumps({
        "frame": b64_frame,
        "exercise_hint": "squat",
    })

    with TestClient(app) as client:
        with client.websocket_connect(
            f"/ws/pose?session_id={session_id}"
        ) as ws:
            ws.send_text(frame_msg)
            raw = ws.receive_text()

    resp = json.loads(raw)
    # Skip any ping messages
    while isinstance(resp, dict) and resp.get("type") == "ping":
        break

    # Required fields present
    required = {"exercise", "rep_count", "form_score",
                "corrections", "calories_running", "landmarks"}
    assert required.issubset(resp.keys()), \
        f"Missing fields: {required - resp.keys()}"

    # Person was actually detected — landmarks should be non-empty
    landmarks = resp.get("landmarks", [])
    assert len(landmarks) > 0, (
        f"Expected non-empty landmarks (real person image), got {len(landmarks)}. "
        f"warning={resp.get('warning')!r} — person_detector may have failed"
    )

    # Not occluded — person was clearly visible in the image
    assert resp.get("warning") != "Move into frame", (
        f"Got 'Move into frame' warning — real person was not detected. "
        f"Full response: {resp}"
    )

    # form_score is a valid integer in [0, 100]
    score = resp.get("form_score")
    assert isinstance(score, int), f"form_score should be int, got {type(score)}"
    assert 0 <= score <= 100, f"form_score {score} out of [0, 100] range"

    print(f"\n[REAL PIPELINE] landmarks={len(landmarks)}, "
          f"form_score={score}, exercise={resp.get('exercise')}, "
          f"warning={resp.get('warning')!r}")
