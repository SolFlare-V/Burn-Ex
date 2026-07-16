# Burn-Ex — Implementation Tasks

> **Spec stage:** Tasks  
> **Depends on:** `requirements.md`, `design.md`, `.kiro/steering/burn-ex-project.md`  
> Each task cites the REQ-IDs it satisfies and the `design.md` section it implements.  
> Tasks are ordered so every task depends only on previously completed tasks.  
> Tasks tagged **[Antigravity hand-off]** define props/state contracts only — visual styling is owned by Antigravity using UI/UX Pro Max and 21st.dev MCP.

---

## Phase 1 — Project Scaffolding

- [x] **TASK-1.1** — Create the top-level directory structure:
  `backend/`, `frontend/`, `models/`, `data/`, `docs/contracts/`, `config/`.
  Add a root `README.md` with setup instructions placeholder.
  **Design ref:** §1.1 (system diagram), §6 (deployment).
  **Verify:** Directory tree matches the scaffold; `README.md` exists.

- [x] **TASK-1.2** — Initialise the FastAPI application entry point (`backend/main.py`).
  Configure `hofst="0.0.0.0"` and a `PORT` environment variable (default 8000).
  Add a `/health` GET endpoint returning `{"status": "ok"}`.
  **Design ref:** §6.1. **REQs:** REQ-8.1.
  **Verify:** `uvicorn backend.main:app --host 0.0.0.0 --port 8000` starts; `curl http://localhost:8000/health` returns 200.

- [x] **TASK-1.3** — Configure CORS middleware on the FastAPI app to allow all origins (`*`).
  **Design ref:** §6.2. **REQs:** REQ-8.2.
  **Verify:** Browser fetch from a different local-network origin returns no CORS error.

- [x] **TASK-1.4** — Set up SQLAlchemy with a SQLite engine pointing to `data/burnex.db`.
  Create `backend/database.py` with engine, `SessionLocal` factory, and `Base` declarative base.
  **Design ref:** §4.1. **REQs:** REQ-6.2, REQ-6.6.
  **Verify:** `python -c "from backend.database import engine; print(engine)"` prints engine without error.

- [x] **TASK-1.5** — Initialise the React + Tailwind frontend scaffold inside `frontend/`.
  Use Vite + React + TypeScript. Install and configure Tailwind CSS.
  Confirm no CDN links appear in built output (`npm run build` produces self-contained assets).
  **Design ref:** §5, §6.3. **REQs:** REQ-10.2.
  **Verify:** `npm run build` succeeds; `dist/` contains no `https://` CDN references (`grep -r "https://" dist/` returns nothing relevant).


---

## Phase 2 — Database Layer

- [x] **TASK-2.1** — Implement the `users` SQLAlchemy model with fields: `id`, `name`, `weight_kg` (CHECK 20–300), `created_at`.
  **Design ref:** §4.1. **REQs:** REQ-9.1, REQ-9.2.
  **Verify:** `Base.metadata.create_all(engine)` creates the `users` table; `CHECK` constraint rejects weight 10.

- [x] **TASK-2.2** — Implement the `sessions` SQLAlchemy model with fields: `id` (UUID TEXT PK), `user_id` (FK), `started_at`, `ended_at`, `status` (CHECK active/completed/interrupted), `total_reps`, `total_calories`, `avg_form_score`, `duration_seconds`.
  Add index on `(user_id, started_at DESC)`.
  **Design ref:** §4.1. **REQs:** REQ-6.1, REQ-6.2, REQ-6.3, REQ-7.1.
  **Verify:** Table and index created; insert a row and query by `user_id` ordered by `started_at DESC`.

- [x] **TASK-2.3** — Implement the `sets` SQLAlchemy model with fields: `id`, `session_id` (FK), `set_number`, `exercise`, `reps`, `hold_seconds`, `avg_form_score`, `closed_at`.
  Add index on `(session_id, set_number)`.
  **Design ref:** §4.1. **REQs:** REQ-4.6, REQ-4.7, REQ-7.2.
  **Verify:** Table and index created; insert a plank set row with `hold_seconds` populated.

- [x] **TASK-2.4** — Implement the `form_score_samples` SQLAlchemy model with fields: `id`, `set_id` (FK), `score` (CHECK 0–100), `sampled_at`.
  Add index on `(set_id)`.
  **Design ref:** §4.1, §4.3. **REQs:** REQ-3.5, REQ-7.4.
  **Verify:** Table created; CHECK constraint rejects score 101.

- [x] **TASK-2.5** — Implement the `calorie_segments` SQLAlchemy model with fields: `id`, `session_id` (FK), `exercise`, `weight_kg`, `started_at`, `ended_at`, `calories`, `duration_seconds`.
  Add index on `(session_id)`.
  **Design ref:** §4.1, §4.2. **REQs:** REQ-5.3, REQ-5.4.
  **Verify:** Table and index created; insert two segments for one session and verify they are retrievable.

- [x] **TASK-2.6** — Implement the `goals` SQLAlchemy model with fields: `id`, `user_id` (FK), `type` (CHECK daily/weekly), `target_calories`, `created_at`, `active`.
  **Design ref:** §4.1. **REQs:** REQ-7.7.
  **Verify:** Table created; CHECK constraint rejects type "monthly".

- [x] **TASK-2.7** — Implement the `streaks` SQLAlchemy model with fields: `id`, `user_id` (FK UNIQUE), `current`, `best`, `last_active`.
  **Design ref:** §4.1. **REQs:** REQ-7.5, REQ-7.6.
  **Verify:** Table created; UNIQUE constraint on `user_id` prevents duplicate streak rows per user.

- [x] **TASK-2.8** — Write a `backend/db_init.py` script that calls `Base.metadata.create_all(engine)` and can be run standalone to initialise the database.
  **Design ref:** §4.1.
  **Verify:** Running `python backend/db_init.py` on a fresh environment creates all 7 tables in `data/burnex.db`.


---

## Phase 3 — CV Module

- [x] **TASK-3.1** — Install and validate MediaPipe in the backend Python environment.
  Confirm `import mediapipe as mp; mp.solutions.pose.Pose()` succeeds with no network requests.
  **Design ref:** §2.1, §7.1. **REQs:** REQ-10.3.
  **Verify:** Import succeeds offline (disconnect network, re-run import).

- [x] **TASK-3.2** — Implement a lightweight person-detection pass in `backend/cv/person_detector.py`.
  Use MediaPipe Tasks' `ObjectDetector` with the `efficientdet_lite0` model (bundled locally in `models/efficientdet_lite0.tflite`, downloaded once during setup — no runtime network calls).
  Accept a decoded frame (numpy array), filter detections to category `"person"`, return a list of bounding boxes `[(x1,y1,x2,y2)]` for all detected persons.
  **Design ref:** §2.1 (nearest-person selection). **REQs:** REQ-1.7.
  **Verify:** Given a test image with 2 people, detector returns 2 bounding boxes with category `"person"`.

- [x] **TASK-3.3** — Implement nearest-person selection in `backend/cv/person_selector.py`.
  Accept a list of bounding boxes, compute area of each (`(x2-x1)*(y2-y1)` in normalised coords), return the box with the largest area as the active ROI.
  When only one box is present, return it unchanged (no-op path).
  **Design ref:** §2.1. **REQs:** REQ-1.7.
  **Verify:** Unit test: given boxes `[(0,0,0.3,0.3), (0,0,0.8,0.8)]`, returns the second box; given single box, returns it as-is.

- [x] **TASK-3.4** — Implement frame cropping with padding in `backend/cv/frame_utils.py`.
  Accept a frame and ROI bounding box, return a cropped numpy array with 10% padding on all sides (clamped to frame boundaries).
  **Design ref:** §2.1. **REQs:** REQ-1.7.
  **Verify:** Unit test: crop of a 640×480 frame with box `(0.1,0.1,0.9,0.9)` returns an array close to full frame size.

- [x] **TASK-3.5** — Implement the MediaPipe Pose inference wrapper in `backend/cv/pose_estimator.py`.
  Accept a cropped JPEG bytes or numpy array, run MediaPipe `Pose`, return a list of 33 `Landmark` objects with fields `id`, `x`, `y`, `z`, `visibility`.
  Initialise the `Pose` object once at module load (not per-frame).
  **Design ref:** §2.1, §7.1. **REQs:** REQ-1.1, REQ-1.2, REQ-10.3.
  **Verify:** Feed a test JPEG with a person; confirm 33 landmarks returned with visibility values in [0,1].

- [x] **TASK-3.6** — Implement the confidence filter in `backend/cv/confidence_filter.py`.
  Accept a `LandmarkSet` and exercise type string, mark each landmark `valid=False` if `visibility < 0.5`.
  Compute the proportion of invalid landmarks from the exercise's required landmark list.
  Return a `FilterResult` with `landmark_set` and `occluded: bool` (True if > 30% invalid).
  **Design ref:** §2.1. **REQs:** REQ-1.3, REQ-1.4.
  **Verify:** Unit test: set 12/33 landmarks to visibility 0.1 for a squat (which needs ~10 landmarks); confirm `occluded=True` when required proportion exceeded.

- [x] **TASK-3.7** — Implement `calculate_angle(a, vertex, b) → float` and `calculate_angle_map(landmark_set, exercise_type) → dict[str, float]` in `backend/cv/angle_utils.py`.
  Use dot-product formula on 2D (x,y) coordinates. `calculate_angle_map` uses a per-exercise triplet config to determine which angles to compute.
  **Design ref:** §2.1. **REQs:** REQ-3.1, REQ-4.1.
  **Verify:** Unit test: `calculate_angle((0,1), (0,0), (1,0))` returns 90.0 ± 0.1.

- [x] **TASK-3.8** — Assemble the full `process_frame(jpeg_bytes, exercise_type) → ProcessedFrame` pipeline in `backend/cv/pipeline.py`.

> **Phase 3 follow-up notes (non-blocking, track in later phases):**
> - **Knee angle visibility (Phase 4/6/7):** Real-image test produced 3/7 squat angles; knee/ankle landmarks were not visible in the test photo. During TASK-4.2 dataset collection, ensure full-body visibility (knees and ankles in frame) — knee angles are required for squat form scoring (Phase 6) and rep counting (Phase 7).
> - **WebSocket latency re-check (Phase 10):** The 114ms figure was measured on a static JPEG called in a loop, not a live WebSocket stream. Re-measure true end-to-end latency after TASK-10.2 (WebSocket per-frame loop) to confirm the 200ms budget holds under real streaming conditions.
  Order: decode → person detect → nearest-person select → crop → MediaPipe Pose → confidence filter → angle map.
  Return a `ProcessedFrame` dataclass with `landmarks`, `angle_map`, `occluded`, `warning`.
  **Design ref:** §2.1 (pipeline order diagram). **REQs:** REQ-1.1–REQ-1.7.
  **Verify:** Feed a JPEG with one person performing a squat; confirm `ProcessedFrame` has populated `angle_map` and `occluded=False`.


---

## Phase 4 — Dataset Collection & Training Pipeline

- [x] **TASK-4.1** — Write `data/collect_landmarks.py`, a script that opens the webcam, runs the CV pipeline (TASK-3.8), and writes one CSV row per frame: `[exercise_label, angle_0, angle_1, ..., angle_9]` to `data/raw/landmarks.csv`.
  Accept `--exercise <name>` and `--output <path>` CLI args. Record until the user presses `q`.
  **Design ref:** §2.2 (training pipeline). **REQs:** REQ-2.1.
  **Verify:** Run with `--exercise squat`; confirm CSV rows are appended with 10 angle columns and the label "squat".

- [x] **TASK-4.2** — Collect a minimum labelled dataset: at least 200 frames per supported exercise type (squat, push-up, lunge, bicep_curl, shoulder_press, plank) using `collect_landmarks.py`.
  Store raw files in `data/raw/` organised by exercise label.
  **Design ref:** §2.2. **REQs:** REQ-2.1.
  **Verify:** `data/raw/` contains ≥ 6 CSV files; each has ≥ 200 rows; label column is consistent.

- [x] **TASK-4.3** — Write `data/train_classifier.py` that:
  - Loads and concatenates all CSVs from `data/raw/`
  - Splits into train/test (80/20 stratified by label)
  - Trains a `sklearn.ensemble.RandomForestClassifier`
  - Prints classification report (precision, recall, F1 per class)
  - Serialises the trained model to `models/exercise_classifier.pkl` using `joblib`
  **Design ref:** §2.2. **REQs:** REQ-2.1, REQ-10.3.
  **Verify:** Script runs without error; `models/exercise_classifier.pkl` is created; test-set accuracy ≥ 0.85.

- [x] **TASK-4.4** — Write `data/validate_classifier.py` that loads `models/exercise_classifier.pkl`, runs inference on a held-out sample of each exercise class, and prints per-class confidence distributions.
  This is used to verify the 0.6 confidence threshold is meaningful (REQ-2.2).
  **Design ref:** §2.2. **REQs:** REQ-2.2.
  **Verify:** Script runs; all 6 exercise classes show median confidence > 0.6 on correctly labelled samples.

---

## Phase 5 — ML Module

- [x] **TASK-5.1** — Implement `backend/ml/feature_extractor.py`.
  Accept an `angle_map: dict[str, float]` and return a fixed-length numpy array of the 10 features defined in design.md §2.2 (left/right knee, hip, elbow, shoulder angles, trunk inclination, hip-to-ankle ratio).
  Return `None` if any required angle is missing from the map.
  **Design ref:** §2.2. **REQs:** REQ-2.1.
  **Verify:** Unit test: given a complete angle map, returns a numpy array of shape `(10,)`; given incomplete map, returns `None`.

- [x] **TASK-5.2** — Implement `backend/ml/classifier.py`.
  Load `models/exercise_classifier.pkl` at module initialisation using `joblib`.
  Expose `predict(feature_vector) → (exercise_type: str | None, confidence: float)`.
  Return `(None, 0.0)` if `feature_vector` is `None`.
  Return `(None, max_prob)` if `max_prob < 0.6` (UNKNOWN case).
  **Design ref:** §2.2. **REQs:** REQ-2.1, REQ-2.2, REQ-10.3.
  **Verify:** Feed a squat feature vector; confirm returns `("squat", p)` where `p ≥ 0.6`; feed zeros vector; confirm returns `(None, <low>)`.

- [x] **TASK-5.3** — Implement `backend/ml/confirmation_window.py`.
  Maintain a sliding deque of the last 10 classification results.
  Expose `update(exercise_type: str | None) → confirmed_type: str | None`.
  Return a confirmed type only when all 10 slots are the same non-None class; otherwise return `None`.
  **Design ref:** §2.2. **REQs:** REQ-2.4.
  **Verify:** Unit test: push "squat" 10 times → returns "squat"; push 9× "squat" + 1× "lunge" → returns `None`.

- [x] **TASK-5.4** — Implement `backend/ml/unrecognised_timer.py`.
  Track consecutive seconds with no confirmed exercise type.
  Expose `tick(confirmed_type: str | None, elapsed_seconds: float) → emit_warning: bool`.
  Emit `True` once when the unrecognised duration exceeds 3 seconds; reset when a type is confirmed.
  **Design ref:** §2.2. **REQs:** REQ-2.3.
  **Verify:** Unit test: call `tick(None, 1.0)` four times → fourth call returns `True`; call `tick("squat", 0.1)` → resets, next `tick(None, ...)` sequence starts fresh.

- [x] **TASK-5.5** — Assemble `backend/ml/pipeline.py` with `classify_frame(angle_map) → ClassificationResult`.
  Chains feature extractor → classifier → confirmation window → unrecognised timer.
  Returns `ClassificationResult(confirmed_type, confidence, unrecognised_warning)`.
  **Design ref:** §2.2. **REQs:** REQ-2.1–REQ-2.5.
  **Verify:** Feed 10 consecutive squat angle maps; confirm `confirmed_type="squat"` on 10th call.

---

## Phase 6 — Form / Posture Scoring Engine

- [x] **TASK-6.1** — Write the joint angle threshold config file `config/form_thresholds.yaml`.
  Define threshold entries for squat, push-up, lunge, bicep_curl, shoulder_press, and plank.
  Each entry must include: `required_landmarks`, `thresholds` (min, max, cue_low, cue_high, severity_weight, penalty) and plank-specific static-hold checks.
  **Design ref:** §2.3. **REQs:** REQ-3.1, REQ-3.2, REQ-3.7.
  **Verify:** Load the YAML; confirm all 6 exercises are present; confirm each threshold entry has `severity_weight` and `penalty` fields.

- [x] **TASK-6.2** — Implement `backend/scoring/cue_generator.py`.
  Accept an `angle_map` and exercise type, load the threshold config, identify all violated thresholds, sort by `severity_weight` descending, return the top 2 cue strings.
  Return an empty list when no violations exist.
  **Design ref:** §2.3. **REQs:** REQ-3.2, REQ-3.3.
  **Verify:** Unit test: inject angle values violating 3 squat thresholds; confirm exactly 2 cues returned, highest-severity first.

- [x] **TASK-6.3** — Implement `backend/scoring/form_score.py`.
  Accept an `angle_map` and exercise type, compute `frame_score = max(0, 100 - sum(penalty for each violation))`.
  **Design ref:** §2.3. **REQs:** REQ-3.4, REQ-3.5.
  **Verify:** Unit test: no violations → score 100; inject a knee-cave violation (penalty 25) → score 75.

- [x] **TASK-6.4** — Implement `backend/scoring/set_form_tracker.py`.
  Maintain a running mean of per-frame form scores for the current set.
  Expose `add_sample(score: int)` and `average() → float`.
  Reset on `reset()`.
  **Design ref:** §2.3, §4.3. **REQs:** REQ-3.5.
  **Verify:** Unit test: add scores [100, 80, 60]; `average()` returns 80.0.

- [x] **TASK-6.5** — Implement the plank scoring path in `backend/scoring/plank_scorer.py`.
  Accept landmark set, check hip-shoulder-ankle alignment and core proxy angles against plank thresholds from config.
  Return `(cues: list[str], score: int)` using the same penalty framework.
  **Design ref:** §2.3. **REQs:** REQ-3.7.
  **Verify:** Unit test: feed landmarks with hips too high → cue "Drop hips slightly" returned; aligned landmarks → score 100.

- [x] **TASK-6.6** — Implement `backend/scoring/engine.py` with `score_frame(processed_frame, confirmed_type) → ScoringResult`.
  Route to plank scorer when `confirmed_type == "plank"`, otherwise use cue_generator + form_score.
  Return `ScoringResult(cues=[], score=0, warning="Move into frame")` when `processed_frame.occluded` is True (occlusion guard).
  **Design ref:** §2.3. **REQs:** REQ-3.1–REQ-3.7.
  **Verify:** Unit test: occluded frame → cues empty, warning set; plank type → routed to plank scorer.


---

## Phase 7 — Rep Counter

- [x] **TASK-7.1** — Write the rep phase config file `config/rep_phases.yaml`.
  For each exercise (except plank) define: `primary_angle`, `eccentric_threshold` (angle at which eccentric phase begins), `depth_threshold` (angle at which full depth is reached), `return_threshold` (angle at which return-to-neutral completes).
  **Design ref:** §2.4. **REQs:** REQ-4.1, REQ-4.2.
  **Verify:** Load YAML; confirm all 5 non-plank exercises have all three threshold keys.

- [x] **TASK-7.2** — Implement the per-exercise phase state machine in `backend/reps/state_machine.py`.
  States: `NEUTRAL → ECCENTRIC → CONCENTRIC → NEUTRAL` (rep counted on final transition).
  Reject partial reps: transition from ECCENTRIC back to NEUTRAL without reaching depth threshold does not increment count.
  Expose `update(angle: float) → rep_counted: bool`.
  **Design ref:** §2.4. **REQs:** REQ-4.1, REQ-4.2, REQ-4.3.
  **Verify:** Unit test: feed squat angle sequence through full ROM → `rep_counted=True` once; feed partial squat (no depth) → `rep_counted` never True.

- [x] **TASK-7.3** — Implement `backend/reps/pause_timer.py`.
  Track time since last angle movement above a threshold.
  Expose `tick(angle: float, elapsed_seconds: float) → close_set: bool`.
  Return `True` once when stationary duration exceeds 8 seconds.
  Reset when movement is detected.
  **Design ref:** §2.4. **REQs:** REQ-4.4.
  **Verify:** Unit test: feed same angle for 9 seconds → returns `True` on the tick that crosses 8 s; feed movement → resets.

- [x] **TASK-7.4** — Implement `backend/reps/set_tracker.py`.
  Maintain current set number, per-set rep count, and list of closed sets.
  Expose `count_rep()`, `close_set(avg_form_score: float) → ClosedSet`, `exercise_changed()` (force-closes set immediately).
  **Design ref:** §2.4. **REQs:** REQ-4.4, REQ-4.5, REQ-4.6.
  **Verify:** Unit test: count 5 reps, close set → `ClosedSet.reps == 5`; call `exercise_changed()` mid-set → set closed immediately with current rep count.

- [x] **TASK-7.5** — Implement `backend/reps/plank_timer.py`.
  Start timing when exercise confirmed as plank; stop on exercise change, session pause, or end.
  Expose `start()`, `stop() → hold_seconds: int`, `elapsed() → int`.
  **Design ref:** §2.4. **REQs:** REQ-4.7.
  **Verify:** Unit test: `start()`, sleep 2 s, `stop()` → returns value ≥ 2.

- [x] **TASK-7.6** — Assemble `backend/reps/counter.py` with `update_rep_state(angle_map, confirmed_type, elapsed_seconds) → RepState`.
  Routes to plank timer when `confirmed_type == "plank"`; otherwise drives state machine + pause timer + set tracker.
  Returns `RepState(rep_count, set_number, sets_closed, hold_seconds)`.
  **Design ref:** §2.4. **REQs:** REQ-4.1–REQ-4.7.
  **Verify:** Integration test: feed full squat sequence; confirm `rep_count` increments; confirm set closes after 8 s of inactivity.

---

## Phase 8 — Calorie Engine

- [x] **TASK-8.1** — Write the MET value config file `config/met_values.yaml` with entries for squat (5.0), push-up (8.0), lunge (4.5), bicep_curl (3.5), shoulder_press (4.0), plank (4.0).
  **Design ref:** §2.5. **REQs:** REQ-5.1.
  **Verify:** Load YAML; confirm all 6 exercise keys present with correct float values.

- [x] **TASK-8.2** — Implement `backend/calories/engine.py` with `CalorieEngine` class.
  Constructor accepts `weight_kg: float`. Raises `ValueError` if `weight_kg <= 0`.
  Maintains a list of `CalorieSegment` objects.
  Expose `start_segment(exercise_type, timestamp)`, `close_segment(timestamp)`, `running_total() → float`.
  On `close_segment`, compute `calories = MET[exercise] × weight_kg × duration_hours` and store on the segment.
  **Design ref:** §2.5. **REQs:** REQ-5.1, REQ-5.2, REQ-5.3.
  **Verify:** Unit test: start squat segment, advance 30 min, close → calories ≈ `5.0 × weight × 0.5`; zero weight → `ValueError`.

- [x] **TASK-8.3** — Implement `running_estimate(current_timestamp) → float` on `CalorieEngine`.
  Sum all closed segment calories plus provisional calories for the open segment (using elapsed time up to `current_timestamp`).
  **Design ref:** §2.5. **REQs:** REQ-5.5.
  **Verify:** Unit test: after 1 min of squats with no closed segments, `running_estimate()` returns a small positive float.

- [x] **TASK-8.4** — Implement exercise-change handling on `CalorieEngine`.
  Expose `change_exercise(new_exercise_type, timestamp)` which calls `close_segment` then `start_segment` atomically.
  **Design ref:** §2.5. **REQs:** REQ-5.3.
  **Verify:** Unit test: start squat segment, call `change_exercise("push-up", ...)`, confirm two segments exist, first is closed, second is open with exercise "push-up".


---

## Phase 9 — Session Manager

- [~] **TASK-9.1** — Implement `backend/session/manager.py` with `SessionManager` class and lifecycle state machine.
  States: `IDLE → ACTIVE → ENDED / INTERRUPTED`.
  Expose `start_session(user_id, weight_kg) → session_id` (checks weight > 0, checks no concurrent session, writes `sessions` row with `status="active"`).
  Raise `WeightRequiredError` if weight ≤ 0; raise `SessionAlreadyActiveError` if another session is active.
  **Design ref:** §2.6, §7.3. **REQs:** REQ-6.1, REQ-6.5, REQ-5.2.
  **Verify:** Unit test: start session with valid weight → returns UUID; start second session without ending first → raises `SessionAlreadyActiveError`.

- [~] **TASK-9.2** — Implement `end_session(session_id, rep_state, calorie_engine, form_tracker)` on `SessionManager`.
  Finalises all calorie segments, computes `total_calories` and `avg_form_score`, writes final session record, closes all open sets, persists `calorie_segments` rows, sets `status="completed"`.
  **Design ref:** §2.6. **REQs:** REQ-6.2, REQ-5.4.
  **Verify:** Integration test: start session, simulate 3 reps + 60 s of squats, call `end_session` → `sessions` row has `status="completed"` and `total_calories > 0`.

- [~] **TASK-9.3** — Implement the incremental persistence background task in `backend/session/persistence.py`.
  Use `asyncio` periodic task running every 30 seconds while session is ACTIVE.
  Writes current `total_reps`, `total_calories`, open set rep counts, and latest `avg_form_score` to the `sessions` row.
  **Design ref:** §2.6. **REQs:** REQ-6.6.
  **Verify:** Start session, wait 35 s without ending → `sessions` row in DB has updated `total_reps` mid-session.

- [~] **TASK-9.4** — Implement interruption detection and partial write in `backend/session/manager.py`.
  Expose `interrupt_session(session_id)` that flushes current state to DB and sets `status="interrupted"`.
  Called by WebSocket disconnect handler (implemented in TASK-10).
  **Design ref:** §2.6, §7.2. **REQs:** REQ-6.3.
  **Verify:** Unit test: call `interrupt_session` with an active session → row status becomes "interrupted" with partial rep/calorie data.

- [~] **TASK-9.5** — Implement streak update logic in `backend/session/streaks.py`.
  On session completion, read the `streaks` row for the user, apply the streak rule:
  - `date(now) - date(last_active) == 1 day` → increment `current`
  - `> 1 day` → reset `current` to 1
  - `== 0 days` (same day) → no change to `current`
  - Update `best` if `current > best`. Write back to `streaks` table.
  **Design ref:** §4.1. **REQs:** REQ-7.5, REQ-7.6.
  **Verify:** Unit test: simulate sessions on consecutive days → streak increments correctly; gap of 2 days → streak resets to 1.

---

## Phase 10 — WebSocket Endpoint

- [~] **TASK-10.1** — Implement the `/ws/pose` WebSocket endpoint in `backend/routers/ws_pose.py`.
  On connect: validate `session_id` query param exists and maps to an active session; reject with close code 4001 otherwise.
  Set up heartbeat ping every 5 seconds; on 3 missed pongs call `interrupt_session`.
  **Design ref:** §3.1, §2.6. **REQs:** REQ-6.3, REQ-1.5.
  **Verify:** Connect without valid session_id → connection closed with code 4001; connect with valid session_id → connection stays open.

- [~] **TASK-10.2** — Implement the per-frame processing loop inside the WebSocket handler.
  For each received message: decode base64 JPEG → `process_frame` (CV) → `classify_frame` (ML) → `score_frame` (Form Engine) → `update_rep_state` (Rep Counter) → `running_estimate` (Calorie Engine) → aggregate into response message → send.
  **Design ref:** §3.1, §1.2 (data flow). **REQs:** REQ-1.1, REQ-1.5, REQ-2.1, REQ-3.2, REQ-4.3, REQ-5.5.
  **Verify:** Send a test JPEG frame over WebSocket; confirm JSON response contains `exercise`, `rep_count`, `form_score`, `corrections`, `calories_running`, `landmarks`.

- [~] **TASK-10.3** — Handle exercise-change events within the WebSocket loop.
  When `ClassificationResult.confirmed_type` differs from the session's last confirmed type: call `calorie_engine.change_exercise(...)`, call `set_tracker.exercise_changed()`, update session state.
  **Design ref:** §1.2 (Stage 4), §2.5, §2.4. **REQs:** REQ-2.4, REQ-4.5, REQ-5.3.
  **Verify:** Simulate frame sequence switching from squat to push-up after 10 confirmed frames → calorie segment closes and new one opens; set closes.

- [~] **TASK-10.4** — Emit `FRAME_OCCLUDED` and `EXERCISE_UNRECOGNISED` warning strings in the WebSocket response.
  Set `response.warning = "Move into frame"` when `processed_frame.occluded`; set `response.warning = "Exercise not recognized — adjust position"` when `unrecognised_warning` is True.
  **Design ref:** §3.1, §2.1, §2.2. **REQs:** REQ-1.4, REQ-2.3.
  **Verify:** Send an occluded frame → response has `warning: "Move into frame"` and empty `corrections`; feed 3+ seconds of unrecognised frames → `warning: "Exercise not recognized — adjust position"`.

---

## Phase 11 — REST Endpoints

- [~] **TASK-11.1** — Implement `POST /api/v1/sessions/start` in `backend/routers/sessions.py`.
  Request: `{ "user_id": int }`. Calls `SessionManager.start_session`. Returns `{ "session_id", "started_at" }`.
  Return 422 `WEIGHT_REQUIRED` if weight not set; 409 `SESSION_ALREADY_ACTIVE` if concurrent session exists.
  **Design ref:** §3.1, §3.3. **REQs:** REQ-6.1, REQ-6.5, REQ-5.2.
  **Verify:** POST with valid user → 200 + session_id; POST again without ending → 409.

- [~] **TASK-11.2** — Implement `POST /api/v1/sessions/{id}/end`.
  Calls `SessionManager.end_session`. Returns `SessionSummary` schema.
  **Design ref:** §3.1. **REQs:** REQ-6.2.
  **Verify:** End active session → 200 with `total_reps`, `total_calories`, `status="completed"`.

- [~] **TASK-11.3** — Implement `GET /api/v1/sessions` with `limit`/`offset` query params.
  Returns `[SessionSummary]` ordered by `started_at DESC`.
  **Design ref:** §3.1. **REQs:** REQ-7.1.
  **Verify:** Create 3 sessions, GET with `limit=2` → returns 2 most recent sessions.

- [~] **TASK-11.4** — Implement `GET /api/v1/sessions/{id}`.
  Returns `SessionDetail` (extends `SessionSummary` with `sets`, `form_score_trend`, `calorie_segments`).
  **Design ref:** §3.1. **REQs:** REQ-7.2.
  **Verify:** GET a completed session with 2 sets → response includes `sets` array with 2 entries and `form_score_trend`.

- [~] **TASK-11.5** — Implement `GET /api/v1/progress/calories`.
  Returns last 30 sessions as `[{ "date": date, "calories": float }]`.
  **Design ref:** §3.1. **REQs:** REQ-7.3.
  **Verify:** Seed 35 sessions; GET → returns exactly 30 entries, most recent first.

- [~] **TASK-11.6** — Implement `GET /api/v1/progress/form`.
  Returns `[{ "exercise": str, "trend": [float] }]` for each exercise type with ≥ 2 sessions, using last 10 sessions per exercise.
  **Design ref:** §3.1. **REQs:** REQ-7.4.
  **Verify:** Seed 5 squat sessions with varying form scores; GET → squat trend array has 5 values in chronological order.

- [~] **TASK-11.7** — Implement `GET /api/v1/streaks`.
  Returns `{ "current": int, "best": int }` from the `streaks` table.
  **Design ref:** §3.1. **REQs:** REQ-7.5, REQ-7.6.
  **Verify:** Seed a streak of 3 with best of 5 → GET returns `{"current": 3, "best": 5}`.

- [~] **TASK-11.8** — Implement `GET /api/v1/goals`, `POST /api/v1/goals`, and `GET /api/v1/goals/progress`.
  POST accepts `{ "type": "daily"|"weekly", "target_calories": float }`.
  GET `/progress` returns achieved vs target for today (daily) and this week (weekly) by summing completed session calories.
  **Design ref:** §3.1. **REQs:** REQ-7.7, REQ-7.8.
  **Verify:** Create daily goal of 200 kcal; complete a session with 250 kcal; GET `/progress` shows `achieved >= target`.

- [~] **TASK-11.9** — Implement `GET /api/v1/user` and `PUT /api/v1/user`.
  GET returns `UserProfile`. PUT updates `name` and/or `weight_kg`.
  Return 409 `WEIGHT_LOCKED_DURING_SESSION` if weight update attempted while session is active.
  Return 422 `INVALID_WEIGHT` if weight outside 20–300 range.
  **Design ref:** §3.1, §3.3. **REQs:** REQ-9.1–REQ-9.5.
  **Verify:** PUT with weight 15 → 422; PUT weight during active session → 409; PUT weight between sessions → 200 and new weight persisted.

- [ ] **TASK-11.10** — Implement `POST /api/v1/user`.
  Accepts `{ "name": str | null, "weight_kg": float }`.
  Validate weight per REQ-9.2 (20-300 range), create a new user row, and return the created `UserProfile` schema.
  **Design ref:** §3.1, §3.3. **REQs:** REQ-9.1.
  **Verify:** POST with valid name/weight when table is empty → 200 + UserProfile with ID 1; POST with weight 15 → 422.


---

## Phase 12 — Privacy & Offline Enforcement

- [~] **TASK-12.1** — Implement CSP header middleware in `backend/middleware/csp.py`.
  Inject `Content-Security-Policy` header on all HTML responses restricting `default-src`, `connect-src` (self + ws LAN), `script-src`, `img-src`, `style-src` per design.md §6.4.
  Register middleware on the FastAPI app.
  **Design ref:** §6.4. **REQs:** REQ-8.4.
  **Verify:** `curl -I http://localhost:8000` shows `Content-Security-Policy` header; browser DevTools confirms blocked external request attempt.

- [~] **TASK-12.2** — Implement the runtime Python network-request guard in `backend/privacy/network_guard.py`.
  Patch `socket.connect` at startup to log and raise `PrivacyViolationError` for any connection attempt to a non-loopback, non-RFC-1918 address.
  Log the violation with module name, target address, and timestamp.
  **Design ref:** §6.4. **REQs:** REQ-8.5.
  **Verify:** Unit test: attempt `socket.connect` to `8.8.8.8` → `PrivacyViolationError` raised and logged.

- [~] **TASK-12.3** — Implement startup model-loading validation in `backend/startup.py`.
  Load MediaPipe `Pose` and `joblib.load("models/exercise_classifier.pkl")` during FastAPI startup event.
  If either fails, log a fatal error and call `sys.exit(1)`.
  **Design ref:** §7.1. **REQs:** REQ-10.3.
  **Verify:** Delete `models/exercise_classifier.pkl` and start server → server exits with non-zero code and prints fatal error message.

- [~] **TASK-12.4** — Add a dependency audit script `scripts/audit_dependencies.py` that checks all installed Python packages and npm packages for known telemetry or auto-update network calls (via a curated deny-list in `config/dependency_deny_list.yaml`).
  Print a warning for any flagged package.
  **Design ref:** §6.4. **REQs:** REQ-10.4.
  **Verify:** Script runs to completion; output is human-readable; seeding a fake deny-list entry triggers a warning.

---

## Phase 13 — Frontend Data Layer

- [~] **TASK-13.1** — Implement the `usePoseSession` React hook in `frontend/src/hooks/usePoseSession.ts`.
  Manages the WebSocket connection lifecycle (open on session start, close on end/interrupt).
  Parses incoming messages and updates state matching the `PoseSessionState` interface from design.md §5.2.
  Exposes `sendFrame(jpegBlob: Blob)` for the camera canvas to call per frame.
  **Design ref:** §5.2. **REQs:** REQ-1.1, REQ-3.2, REQ-4.3, REQ-5.5.
  **Verify:** Connect to a running backend WS; confirm hook state updates on each received message (log in browser console).

- [~] **TASK-13.2** — Implement the `useSessionLifecycle` React hook in `frontend/src/hooks/useSessionLifecycle.ts`.
  Calls `POST /api/v1/sessions/start` on start, `POST /api/v1/sessions/{id}/end` on end.
  Coordinates with `usePoseSession` to open/close the WebSocket at the right lifecycle moments.
  Exposes `status: "idle" | "active" | "ended" | "interrupted"`.
  **Design ref:** §5.2. **REQs:** REQ-6.1, REQ-6.2, REQ-6.4.
  **Verify:** Click start → hook status becomes "active" and WS connects; click end → status becomes "ended" and WS closes.

- [~] **TASK-13.3** — Set up React Query (or TanStack Query) in `frontend/src/lib/queryClient.ts`.
  Configure a `QueryClient` with sensible defaults (stale time 30 s, no automatic background refetch during active session).
  Create typed query hooks for: `useSessionHistory`, `useSessionDetail`, `useProgressCalories`, `useProgressForm`, `useStreaks`, `useGoals`, `useGoalsProgress`, `useUserProfile`.
  Each hook maps to its corresponding REST endpoint from design.md §3.1.
  **Design ref:** §5.2. **REQs:** REQ-7.1–REQ-7.8, REQ-9.1.
  **Verify:** `useSessionHistory()` returns an array when sessions exist; `useUserProfile()` returns profile object.

---

## Phase 14 — Frontend Components (Antigravity Hand-off)

> All tasks in this phase define **props/state contracts and data wiring only**. Visual styling, layout polish, colour, typography, and animation are owned by Antigravity using the UI/UX Pro Max skill and 21st.dev MCP.

- [~] **TASK-14.1 [Antigravity hand-off]** — Scaffold `ProfileSetupScreen` component.
  Props: `onProfileSaved: () => void`.
  Contains a weight input (kg) and optional name input. On submit calls `PUT /api/v1/user`; on success calls `onProfileSaved`.
  Show validation error from `INVALID_WEIGHT` response.
  **Design ref:** §5.1. **REQs:** REQ-9.1, REQ-9.2.

- [~] **TASK-14.2 [Antigravity hand-off]** — Scaffold `CompatibilityWarningScreen` component.
  Displayed when `navigator.mediaDevices?.getUserMedia` or `WebSocket` is undefined.
  Shows a message listing required browser features and recommending a supported browser.
  **Design ref:** §5.1. **REQs:** REQ-8.3.

- [~] **TASK-14.3 [Antigravity hand-off]** — Scaffold `CameraCanvas` component.
  Props contract per design.md §5.3: `landmarks: Landmark[]`, `videoRef: RefObject<HTMLVideoElement>`, `width: number`, `height: number`.
  Draws landmark points and skeleton lines on a `<canvas>` overlay sized to the video element. No form logic in this component.
  **Design ref:** §5.3. **REQs:** REQ-1.2.

- [~] **TASK-14.4 [Antigravity hand-off]** — Scaffold `FeedbackPanel` and its subcomponents:
  - `ExerciseLabel`: props `exercise: string | null, confidence: number`
  - `RepCounter`: props `repCount: number, setNumber: number`
  - `CalorieDisplay`: props `caloriesRunning: number` (updates ≤ 5 s per REQ-5.5)
  - `FormScoreGauge`: props `formScore: number` (0–100)
  - `CorrectionCues`: props `corrections: string[]` (max 2 items)
  All consume values from `usePoseSession` hook.
  **Design ref:** §5.1. **REQs:** REQ-3.3, REQ-3.5, REQ-4.3, REQ-5.5.

- [~] **TASK-14.5 [Antigravity hand-off]** — Scaffold `WarningBanner` component.
  Props: `warning: string | null`. Displayed when `warning` is non-null.
  **Design ref:** §5.1. **REQs:** REQ-1.4, REQ-2.3.

- [~] **TASK-14.6 [Antigravity hand-off]** — Scaffold `SessionView` composing TASK-14.3, TASK-14.4, TASK-14.5.
  Manages camera stream via `getUserMedia`. Sends frames to `usePoseSession.sendFrame` at ~15 FPS via `requestAnimationFrame`.
  Shows `SessionControls` (Start / End buttons) wired to `useSessionLifecycle`.
  **Design ref:** §5.1. **REQs:** REQ-1.1, REQ-6.1, REQ-6.2.

- [~] **TASK-14.7 [Antigravity hand-off]** — Scaffold `SessionSummaryView` component.
  Props: `sessionId: string`. Fetches `SessionDetail` via `useSessionDetail(sessionId)`.
  Renders: `SummaryStats` (total reps, calories, duration, avg form score), `SetBreakdownTable` (per-set data), `CalorieSegmentChart` (per-exercise calorie bars).
  **Design ref:** §5.1. **REQs:** REQ-6.2, REQ-7.2.

- [~] **TASK-14.8 [Antigravity hand-off]** — Scaffold `HistoryView` with `SessionList` and `SessionDetailDrawer`.
  `SessionList` fetches from `useSessionHistory()`; on row click opens `SessionDetailDrawer` with the selected `sessionId`.
  Show interrupted sessions with a distinct status badge.
  **Design ref:** §5.1. **REQs:** REQ-7.1, REQ-7.2, REQ-6.4.

- [~] **TASK-14.9 [Antigravity hand-off]** — Scaffold `ProgressDashboard` composing:
  - `CalorieTimelineChart`: data from `useProgressCalories()`
  - `FormTrendChart`: data from `useProgressForm()`
  - `StreakWidget`: data from `useStreaks()`
  - `GoalsWidget`: data from `useGoals()` + `useGoalsProgress()`; includes goal-achieved indicator (REQ-7.8)
  **Design ref:** §5.1. **REQs:** REQ-7.3, REQ-7.4, REQ-7.5–REQ-7.8.

- [~] **TASK-14.10 [Antigravity hand-off]** — Scaffold `ProfileView` component.
  Fetches current profile via `useUserProfile()`.
  Name field: immediate save on change via `PUT /api/v1/user`.
  Weight field: disabled with tooltip "Cannot change weight during an active session" when session is active; otherwise editable with validation.
  **Design ref:** §5.1. **REQs:** REQ-9.3, REQ-9.4, REQ-9.5, REQ-9.6.

- [ ] **TASK-14.11** — Wire all Phase 14 components and global navigation inside `App.tsx`.
  Verify browser support (render CompatibilityWarningScreen if missing) and fetch user profile (render ProfileSetupScreen if 404). Render active SessionView, SessionSummaryView, or the main application tabbed viewport based on session lifecycle state.
  **Design ref:** §5.1. **REQs:** REQ-6.4, REQ-8.3, REQ-9.1.


---

## Phase 15 — Static Asset Serving & Deployment

- [~] **TASK-15.1** — Mount the React build output in FastAPI using `StaticFiles`.
  In `backend/main.py`, mount `frontend/dist` at `/` after all API routes.
  Serve `index.html` as the fallback for unknown paths (SPA routing).
  **Design ref:** §6.3. **REQs:** REQ-10.2.
  **Verify:** `npm run build` then start FastAPI; navigate to `http://localhost:8000` → React app loads with no 404 errors on assets.

- [~] **TASK-15.2** — Add a startup log message that prints the host machine's LAN IP and access URL.
  Use `socket.getsockname()` or scan network interfaces to find the primary LAN IP.
  Print: `Burn-Ex running at http://<LAN_IP>:8000 — open this on your mobile browser`.
  **Design ref:** §6.1. **REQs:** REQ-8.1, REQ-8.2.
  **Verify:** Start server; terminal shows correct LAN IP; navigate to that URL on a phone on same Wi-Fi → app loads.

---

## Phase 16 — Testing

- [~] **TASK-16.1** — Write unit tests for `calculate_angle` and `calculate_angle_map` in `tests/test_angle_utils.py`.
  Test: right angle returns 90°; straight line returns 180°; known squat angle map produces expected keys.
  **Design ref:** §2.1. **REQs:** REQ-3.1, REQ-4.1.
  **Verify:** `pytest tests/test_angle_utils.py` passes.

- [~] **TASK-16.2** — Write unit tests for the calorie engine in `tests/test_calorie_engine.py`.
  Test: correct MET calculation for each exercise; segmented accumulation across exercise change; weight gate raises on zero weight; `running_estimate` returns sum of closed + open segment.
  **Design ref:** §2.5. **REQs:** REQ-5.1–REQ-5.3, REQ-5.5.
  **Verify:** `pytest tests/test_calorie_engine.py` passes.

- [~] **TASK-16.3** — Write unit tests for the rep state machine in `tests/test_rep_state_machine.py`.
  Test: full ROM squat counts one rep; partial squat (no depth) counts zero; set closes after 8 s pause; exercise change closes set immediately; plank timer tracks duration.
  **Design ref:** §2.4. **REQs:** REQ-4.1, REQ-4.2, REQ-4.4, REQ-4.5, REQ-4.7.
  **Verify:** `pytest tests/test_rep_state_machine.py` passes.

- [~] **TASK-16.4** — Write unit tests for the form scoring engine in `tests/test_form_scoring.py`.
  Test: no violations → score 100; single violation → correct penalty applied; two violations → top-2 cues returned by severity; occluded frame → empty cues + warning; plank → routed to plank scorer.
  **Design ref:** §2.3. **REQs:** REQ-3.2–REQ-3.7.
  **Verify:** `pytest tests/test_form_scoring.py` passes.

- [~] **TASK-16.5** — Write an integration test for the full WebSocket pipeline in `tests/test_ws_pipeline.py`.
  Spin up the FastAPI app with `TestClient` + `starlette.testclient` WebSocket support.
  Seed a user and session; connect to `/ws/pose`; send 15 synthetic squat frames; assert response messages contain `exercise="squat"`, non-zero `form_score`, incrementing `rep_count` after full ROM frames.
  **Design ref:** §3.1, §1.2. **REQs:** REQ-1.1, REQ-1.5, REQ-2.1, REQ-3.5, REQ-4.3, REQ-5.5.
  **Verify:** `pytest tests/test_ws_pipeline.py` passes with no flaky failures.

- [~] **TASK-16.6** — Write an integration test for interrupted session recovery in `tests/test_session_recovery.py`.
  Start a session, simulate incremental persistence write, call `interrupt_session`, assert DB row has `status="interrupted"` and non-zero rep/calorie data.
  Then seed this row and call `GET /api/v1/sessions?status=interrupted` → assert the interrupted session is returned.
  **Design ref:** §7.2. **REQs:** REQ-6.3, REQ-6.4, REQ-6.6.
  **Verify:** `pytest tests/test_session_recovery.py` passes.

---

*End of tasks. All phases are complete when every checkbox is ticked and all verification steps pass. Proceed to implementation by working through tasks in order — each phase depends on all previous phases being complete.*
