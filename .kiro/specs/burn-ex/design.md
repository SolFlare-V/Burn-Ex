# Burn-Ex — Design Document

> **Spec stage:** Design  
> **Depends on:** `requirements.md`, `.kiro/steering/burn-ex-project.md`  
> **REQ-IDs** are cited inline to trace every design decision back to a requirement.  
> **No implementation code appears here.** Code lives in tasks and source files.

---

## 1. Architecture Overview

### 1.1 System Diagram (described)

```
Browser (laptop or mobile on LAN)
│
│  getUserMedia → video frames
│  WebSocket (ws://[local-ip]:8000/ws/pose)
│  HTTP REST  (http://[local-ip]:8000/api/v1/...)
│
└─► FastAPI Backend (0.0.0.0:8000)
      │
      ├─► CV Module
      │     MediaPipe Pose → 33 landmarks (x,y,z,visibility)
      │     Confidence filter → validated landmark set
      │     Joint angle utilities → angle map per frame
      │
      ├─► ML Module
      │     Random Forest classifier
      │     Feature vector from angle map
      │     Sustained-confirmation logic → confirmed exercise type
      │
      ├─► Form/Posture Scoring Engine
      │     Per-exercise threshold tables
      │     Corrective cue generator (≤2 cues, prioritised)
      │     Rolling form score (0–100)
      │
      ├─► Rep Counter
      │     Per-exercise phase state machine
      │     Set tracker + auto-close logic
      │
      ├─► Calorie Engine
      │     MET table lookup
      │     Segmented accumulator
      │
      ├─► Session Manager
      │     Lifecycle state machine
      │     Incremental SQLite writes
      │
      └─► SQLite (single local file)
            users, sessions, sets, calorie_segments,
            form_scores, goals, streaks
```

### 1.2 Data Flow Narrative

**Stage 1 — Frame Capture (REQ-1.1, REQ-1.6)**  
The browser captures video frames via `getUserMedia`. If camera access is denied the frontend displays an error and prevents session start. Frames are encoded (JPEG at reduced resolution) and streamed to the backend over a WebSocket connection at the `/ws/pose` endpoint.

**Stage 2 — Landmark Extraction (REQ-1.1, REQ-1.2, REQ-1.5)**  
The CV Module feeds each received frame to MediaPipe Pose, which returns 33 landmarks. The round-trip from frame capture to landmark output must complete within the 200 ms latency budget. The confidence filter marks any landmark with `visibility < 0.5` as low-confidence (REQ-1.3). If more than 30% of an exercise's required landmarks are simultaneously low-confidence, the pipeline suspends scoring and emits a "Move into frame" warning (REQ-1.4).

**Stage 3 — Feature Extraction & Classification (REQ-2.1–REQ-2.5)**  
Valid landmarks are passed to the joint angle utilities, which compute the angle map for the current frame. The ML Module feeds this angle map as a feature vector to the Random Forest classifier. If confidence < 0.6, the frame is discarded for classification (REQ-2.2). Confirmed exercise type requires ≥ 10 consecutive high-confidence frames (REQ-2.4).

**Stage 4 — Form Scoring, Rep Counting, Calorie Update (REQ-3.x, REQ-4.x, REQ-5.x)**  
With a confirmed exercise type, three engines run in parallel on each frame's angle map: the Form Scoring Engine (joint threshold evaluation → cues + score), the Rep Counter (phase state machine → rep event), and the Calorie Engine (MET accumulation update). Results are aggregated into a single WebSocket response message.

**Stage 5 — WebSocket Response to Frontend (REQ-1.5)**  
The aggregated feedback message is sent back to the browser over the same WebSocket. The frontend updates the pose overlay canvas, corrective cue panel, rep counter, and calorie display.

**Stage 6 — Persistence (REQ-6.6, REQ-6.2)**  
The Session Manager writes incremental state to SQLite every ≤ 30 seconds during an active session. On session end, a final write records the complete session summary.

### 1.3 Offline & Privacy Confirmation

- The backend binds to `0.0.0.0` — no external address is involved (REQ-8.1).
- All ML models load from local filesystem at startup (REQ-10.3).
- No external AI APIs are called at any stage — MediaPipe and scikit-learn run entirely in-process (REQ-10.1).
- All frontend assets are served by FastAPI's static file handler with no CDN dependency (REQ-10.2).

---

## 2. Component Design

### 2.1 CV Module

**Responsibilities:** Frame ingestion, MediaPipe Pose inference, nearest-person selection, landmark confidence filtering, joint angle computation.

**MediaPipe Integration**  
MediaPipe Pose runs in the backend Python process (not in-browser) to keep all model execution server-side and simplify the offline bundle. The module exposes a single `process_frame(jpeg_bytes) → LandmarkSet` function.

**MediaPipe Single-Pose vs Multi-Pose Configuration**  
MediaPipe Pose's default `Pose` solution is a single-person detector — it internally picks one person per frame and returns 33 landmarks for that person only. It does not expose ranked candidates or bounding boxes for multiple detected people. The `Holistic` and `BlazePose` multi-person variants exist but add significant latency overhead that is incompatible with the 200 ms budget (REQ-1.5).

**Nearest-Person Selection Strategy (REQ-1.7)**  
Rather than switching to a heavier multi-pose model, the nearest-person selection is implemented as a **pre-processing filter** using MediaPipe's `SelfieSegmentation` or object detection pass before the main `Pose` inference:

1. A lightweight person-detection pass (MediaPipe Tasks `ObjectDetector` using the `efficientdet_lite0` model, bundled locally as a `.tflite` file — no runtime downloads) runs on each frame and returns bounding boxes for all detected persons.
2. For each bounding box, a **proximity score** is computed as the bounding-box area (width × height in normalised image coordinates). Larger area = person is physically closer to the camera.
3. The bounding box with the largest area is selected as the active user's region of interest (ROI).
4. The frame is cropped to a padded region around this ROI before being passed to MediaPipe `Pose` for landmark inference.
5. This crop step means MediaPipe `Pose` only ever sees one person's body region, and its output landmarks therefore correspond exclusively to the selected nearest person.

This approach satisfies REQ-1.7 without requiring a multi-pose model: the nearest-person selection is geometric and deterministic, runs before the main pose inference step, and adds negligible latency (bounding-box area comparison is O(N) where N is the number of detected persons, typically ≤ 3 in a home setting).

**When only one person is detected**, the bounding-box selection step is a no-op — the full frame is passed to MediaPipe Pose as normal. The nearest-person filter introduces no regression for the single-user case.

**The `process_frame` pipeline order** is therefore:
```
jpeg_bytes
  → person detection → bounding boxes ranked by area
  → crop to largest-area ROI
  → MediaPipe Pose inference on cropped frame
  → 33 landmarks (for nearest person only)
  → confidence filter
  → joint angle computation
  → downstream modules (classification, form scoring, rep counting)
```

All downstream modules (ML classifier, Form Scoring Engine, Rep Counter) receive only the nearest person's `LandmarkSet`. They have no visibility into whether other persons were present in the original frame. (REQ-1.7)

**Confidence Filter (REQ-1.3, REQ-1.4)**  
Each landmark in the returned `LandmarkSet` carries a `valid: bool` flag set to `False` when `visibility < 0.5`. Before any downstream module consumes the landmark set, a guard checks the proportion of invalid landmarks against the required set for the current exercise. If > 30% are invalid, the module emits a `FRAME_OCCLUDED` event instead of proceeding.

**Joint Angle Utilities**  
A shared utility module calculates angles between landmark triplets (proximal joint, vertex joint, distal joint) using the dot-product formula on 2D projected coordinates. This module is stateless and is called by both the Form Scoring Engine and the Rep Counter. It exposes:

- `calculate_angle(a, vertex, b) → float (degrees)`
- `calculate_angle_map(landmark_set, exercise_type) → dict[str, float]`

The `exercise_type` parameter determines which triplets are computed, keeping irrelevant angle computations out of the critical path.

---

### 2.2 ML Module

**Responsibilities:** Exercise classification from joint angle feature vectors, sustained-confirmation logic, confidence thresholding.

**Feature Vector Design**  
The feature vector fed to the Random Forest is composed of joint angles rather than raw landmark coordinates. This makes the classifier invariant to camera position and user body scale. The feature set includes:

| Feature | Landmarks used |
|---|---|
| Left knee angle | hip-knee-ankle |
| Right knee angle | hip-knee-ankle |
| Left hip angle | shoulder-hip-knee |
| Right hip angle | shoulder-hip-knee |
| Left elbow angle | shoulder-elbow-wrist |
| Right elbow angle | shoulder-elbow-wrist |
| Left shoulder angle | elbow-shoulder-hip |
| Right shoulder angle | elbow-shoulder-hip |
| Trunk inclination | shoulder-hip vertical offset angle |
| Hip-to-ankle vertical ratio | derived from y-coordinates |

10 features total. This dimensionality is appropriate for a Random Forest with a small self-generated dataset and supports the 200 ms latency budget (REQ-1.5).

**Training Pipeline**  
Training is run offline as a one-time (or periodic) step using a self-generated dataset of landmark sequences labelled by exercise type. The trained model is serialised with `joblib` and stored in `models/exercise_classifier.pkl`. The module loads this file at startup (REQ-10.3).

**Confidence Thresholding (REQ-2.2)**  
The classifier returns a probability distribution across classes. If `max(probabilities) < 0.6`, the frame is classified as `UNKNOWN` and the confirmed exercise type is not updated.

**Sustained-Confirmation Logic (REQ-2.4)**  
A sliding window of the last 10 classification results is maintained. The exercise type is confirmed only when the same non-UNKNOWN class appears in all 10 slots. On confirmation, if the type differs from the current confirmed type, the Session Manager is notified of an exercise change event.

**Unrecognised Timeout (REQ-2.3)**  
A timer tracks consecutive seconds of UNKNOWN classification. If it exceeds 3 seconds, the module emits an `EXERCISE_UNRECOGNISED` event to the frontend.

---

### 2.3 Form / Posture Scoring Engine

**Responsibilities:** Per-exercise joint angle threshold evaluation, corrective cue generation, form score calculation, plank time-based path.

**Joint Angle Threshold Tables**  
Each supported exercise has a configuration entry defining:

```
Exercise: squat
  Required landmarks: [hip, knee, ankle, shoulder, spine]
  Thresholds:
    knee_angle:      { min: 70,  max: 110, cue_low: "Don't cave knees in", cue_high: "Squat deeper" }
    hip_angle:       { min: 60,  max: 120, cue_low: "Open hips more",      cue_high: "Don't lean too far forward" }
    trunk_angle:     { min: 0,   max: 45,  cue_low: null,                  cue_high: "Keep chest up" }
    knee_tracking:   { check: "knee over toe", cue_fail: "Drive knees out" }
```

Similar tables exist for push-up, lunge, bicep curl, shoulder press. Plank has a separate time-based configuration (see below). These tables are the single source of truth for what constitutes correct form — they must be maintained in a versioned config file, not hard-coded in engine logic, so thresholds can be tuned without code changes.

**Cue Prioritisation (REQ-3.2, REQ-3.3)**  
When multiple threshold violations occur in the same frame, violations are ranked by a `severity_weight` property in the threshold table (higher weight = more structurally important, e.g. knee cave > torso lean). The engine emits only the top 2 cues by severity weight.

**Rolling Form Score Algorithm (REQ-3.5)**  
For each frame, the score is computed as:

```
frame_score = 100 - sum(violation_penalty for each active violation)
```

Each threshold entry has a `penalty` value (e.g., knee cave = 25 pts, slight torso lean = 10 pts). The score is floored at 0. The per-set average form score is maintained as a running mean updated on each scored frame.

**Plank Time-Based Path (REQ-3.7)**  
When the confirmed exercise is `plank`, the engine switches to a hold-quality mode:
- Rep Counter is bypassed; a hold timer starts on confirmation.
- The engine checks hip height relative to shoulder-ankle line and core engagement proxy angles.
- Cues are plank-specific: "Drop hips slightly", "Engage core", "Keep neck neutral".
- Form score is computed on the same penalty framework but against plank-specific thresholds.

**Occlusion Guard (REQ-3.6)**  
If a `FRAME_OCCLUDED` event is active, the engine emits no form cues — only the "Move into frame" warning passes through.

---

### 2.4 Rep Counter

**Responsibilities:** Phase-based rep detection per exercise, partial rep rejection, set management, plank duration tracking.

**Phase State Machine (REQ-4.1, REQ-4.2)**  
Each exercise has a two-phase model: `ECCENTRIC` (loading phase, e.g. descending in a squat) and `CONCENTRIC` (exertion phase, e.g. rising). A rep is counted when the state machine completes the full `ECCENTRIC → CONCENTRIC` transition and both phases reached their respective angle range thresholds.

```
State: NEUTRAL
  → ECCENTRIC  when primary angle crosses eccentric threshold
  → NEUTRAL    if angle returns without reaching eccentric depth (partial rep — not counted, REQ-4.2)

State: ECCENTRIC
  → CONCENTRIC when angle reaches full depth threshold
  → NEUTRAL    if abandoned before depth (partial rep)

State: CONCENTRIC
  → NEUTRAL    when angle returns to start range → REP COUNTED (REQ-4.3)
```

**Auto Set-Closing on Pause (REQ-4.4)**  
A pause timer starts when the state machine is in `NEUTRAL` and no movement above threshold is detected. If the timer exceeds 8 seconds and at least one rep has been counted in the current set, the set is closed and a new set is opened.

**Auto Set-Closing on Exercise Change (REQ-4.5)**  
When the Session Manager emits an exercise change event, the Rep Counter closes the current set immediately, regardless of the pause timer.

**Plank Duration Tracking (REQ-4.7)**  
When exercise is `plank`, the Rep Counter is replaced by a hold timer that starts on exercise confirmation and stops on exercise change, session pause, or session end. Duration is recorded in seconds against the set record.

---

### 2.5 Calorie Engine

**Responsibilities:** MET-based calorie accumulation, segmented tracking across exercise changes, running estimate updates.

**MET Value Table**  
A static lookup table keyed by exercise type:

| Exercise | MET |
|---|---|
| squat | 5.0 |
| push-up | 8.0 |
| lunge | 4.5 |
| bicep_curl | 3.5 |
| shoulder_press | 4.0 |
| plank | 4.0 |

Values sourced from published exercise science compendiums (Ainsworth et al.). This table is versioned in a config file for auditability.

**Segmented Accumulation (REQ-5.3)**  
The engine maintains a list of `CalorieSegment` objects for the active session:

```
CalorieSegment:
  exercise_type: str
  start_time:    datetime
  end_time:      datetime | None
  weight_kg:     float
  calories:      float (computed on close)
```

When exercise type changes, the current segment is closed (end_time set, calories computed), and a new segment opens. This allows calories to be attributed correctly per exercise type across a session.

**Running Estimate (REQ-5.5)**  
The open segment's elapsed duration is used to compute a provisional calorie value on each backend tick (≤ 5 second intervals). This provisional value plus all closed segment totals forms the running estimate sent in each WebSocket message.

**Weight Gate (REQ-5.2)**  
The engine checks that `weight_kg > 0` before any session starts. This check is enforced in the Session Manager's start-session handler.

---

### 2.6 Session Manager

**Responsibilities:** Session lifecycle, incremental persistence, interruption detection and recovery.

**Lifecycle State Machine**

```
IDLE
  → ACTIVE      on start_session (weight check passes, no concurrent session, REQ-6.5)

ACTIVE
  → ENDED       on end_session (final write to DB, REQ-6.2)
  → INTERRUPTED on WebSocket disconnect / server shutdown (partial write, REQ-6.3)

INTERRUPTED
  → IDLE        on next app load (recovery notification shown, REQ-6.4)
```

**Incremental Persistence (REQ-6.6)**  
A background task runs every 30 seconds while a session is ACTIVE. It writes the current rep counts, form score averages, and calorie total to the session record in SQLite. On abnormal termination, at most 30 seconds of data is lost.

**Interruption Detection (REQ-6.3)**  
The WebSocket connection uses a heartbeat ping/pong every 5 seconds. If three consecutive pongs are missed, the session is transitioned to INTERRUPTED and a partial write is performed.

**Concurrent Session Guard (REQ-6.5)**  
A global `active_session_id` is maintained in application state. Any `start_session` request when this is non-null returns a `409 Conflict` error.

---

## 3. API Design

### 3.1 Endpoint List

#### WebSocket

| Endpoint | Direction | Purpose | REQs |
|---|---|---|---|
| `WS /ws/pose` | Bidirectional | Real-time frame upload (client→server) and feedback stream (server→client) | REQ-1.1, REQ-1.5, REQ-3.2, REQ-4.3, REQ-5.5 |

**Client → Server message (per frame):**
```
{
  "frame": "<base64-encoded JPEG>",
  "session_id": "uuid"
}
```

**Server → Client message (per processed frame):**
```
{
  "timestamp": float,
  "exercise": string | null,
  "confidence": float,
  "rep_count": int,
  "set_number": int,
  "form_score": int,
  "corrections": [string],          // max 2 items (REQ-3.3)
  "calories_running": float,
  "warning": string | null,         // "Move into frame", "Exercise not recognized", etc.
  "landmarks": [
    { "id": int, "x": float, "y": float, "z": float, "visibility": float, "valid": bool }
  ]
}
```

#### REST Endpoints

**Sessions**

| Method | Path | Request | Response | REQs |
|---|---|---|---|---|
| `POST` | `/api/v1/sessions/start` | `{ "user_id": int }` | `{ "session_id": uuid, "started_at": datetime }` | REQ-6.1, REQ-6.5 |
| `POST` | `/api/v1/sessions/{id}/end` | `{}` | `SessionSummary` | REQ-6.2 |
| `GET` | `/api/v1/sessions` | query: `limit`, `offset` | `[SessionSummary]` | REQ-7.1 |
| `GET` | `/api/v1/sessions/{id}` | — | `SessionDetail` | REQ-7.2 |

**SessionSummary schema:**
```
{
  "session_id": uuid,
  "started_at": datetime,
  "ended_at": datetime | null,
  "status": "completed" | "interrupted",
  "exercise_breakdown": [{ "exercise": str, "reps": int, "calories": float }],
  "total_reps": int,
  "total_calories": float,
  "duration_seconds": int,
  "avg_form_score": float
}
```

**SessionDetail** extends SessionSummary with:
```
  "sets": [{ "set_number": int, "exercise": str, "reps": int, "avg_form_score": float, "duration_seconds": int }],
  "form_score_trend": [float],     // per-set averages in order (REQ-7.2)
  "calorie_segments": [{ "exercise": str, "calories": float, "duration_seconds": int }]
```

**Progress & History**

| Method | Path | Response | REQs |
|---|---|---|---|
| `GET` | `/api/v1/progress/calories` | `[{ "date": date, "calories": float }]` (last 30 sessions) | REQ-7.3 |
| `GET` | `/api/v1/progress/form` | `[{ "exercise": str, "trend": [float] }]` (last 10 per exercise) | REQ-7.4 |
| `GET` | `/api/v1/streaks` | `{ "current": int, "best": int }` | REQ-7.5, REQ-7.6 |

**Goals**

| Method | Path | Request | Response | REQs |
|---|---|---|---|---|
| `GET` | `/api/v1/goals` | — | `[Goal]` | REQ-7.7 |
| `POST` | `/api/v1/goals` | `{ "type": "daily"\|"weekly", "target_calories": float }` | `Goal` | REQ-7.7 |
| `GET` | `/api/v1/goals/progress` | — | `{ "daily": { "target": float, "achieved": float }, "weekly": {...} }` | REQ-7.7, REQ-7.8 |

**User Profile**

| Method | Path | Request | Response | REQs |
|---|---|---|---|---|
| `GET` | `/api/v1/user` | — | `UserProfile` | REQ-9.1 |
| `POST` | `/api/v1/user` | `{ "name": str, "weight_kg": float }` | `UserProfile` | REQ-9.1 |
| `PUT` | `/api/v1/user` | `{ "name": str, "weight_kg": float }` | `UserProfile` | REQ-9.3, REQ-9.4, REQ-9.5 |

**UserProfile schema:**
```
{
  "user_id": int,
  "name": string | null,
  "weight_kg": float,
  "created_at": datetime
}
```

### 3.2 WebSocket vs REST Justification

**WebSocket for `/ws/pose`**: Real-time feedback requires sub-200 ms round trips (REQ-1.5). HTTP polling at the required frame rate (≥15 FPS) would produce 15+ requests/second, creating connection overhead and making latency guarantees impossible. A persistent WebSocket connection eliminates per-request handshake cost and enables the server to push feedback the moment a frame is processed.

**REST for everything else**: Sessions, history, profile, and goals are low-frequency, request-response interactions. REST is simpler to cache, easier to reason about for Antigravity's data-fetching layer, and aligns with standard React data patterns.

### 3.3 Error Response Shapes

All error responses follow a consistent envelope:
```
{
  "error_code": string,
  "message": string,
  "detail": object | null
}
```

| Scenario | HTTP Status | error_code | REQ |
|---|---|---|---|
| Camera denied | 400 | `CAMERA_UNAVAILABLE` | REQ-1.6 |
| Weight not set | 422 | `WEIGHT_REQUIRED` | REQ-5.2, REQ-9.1 |
| Concurrent session | 409 | `SESSION_ALREADY_ACTIVE` | REQ-6.5 |
| Invalid weight value | 422 | `INVALID_WEIGHT` | REQ-9.2 |
| Weight update during session | 409 | `WEIGHT_LOCKED_DURING_SESSION` | REQ-9.4 |
| Exercise unrecognised > 3s | WS event | `EXERCISE_UNRECOGNISED` | REQ-2.3 |
| Frame occluded | WS event | `FRAME_OCCLUDED` | REQ-1.4 |
| External network attempt | 500 | `PRIVACY_VIOLATION` | REQ-8.5 |

---

## 4. Data Model

### 4.1 SQLite Schema

**`users`**
```
id            INTEGER PRIMARY KEY
name          TEXT
weight_kg     REAL NOT NULL CHECK(weight_kg BETWEEN 20 AND 300)
created_at    TEXT NOT NULL  -- ISO8601
```

**`sessions`**
```
id              TEXT PRIMARY KEY  -- UUID
user_id         INTEGER NOT NULL REFERENCES users(id)
started_at      TEXT NOT NULL
ended_at        TEXT
status          TEXT NOT NULL CHECK(status IN ('active','completed','interrupted'))
total_reps      INTEGER NOT NULL DEFAULT 0
total_calories  REAL NOT NULL DEFAULT 0.0
avg_form_score  REAL
duration_seconds INTEGER
```
Index: `sessions(user_id, started_at DESC)` — supports history list queries (REQ-7.1).

**`sets`**
```
id               INTEGER PRIMARY KEY AUTOINCREMENT
session_id       TEXT NOT NULL REFERENCES sessions(id)
set_number       INTEGER NOT NULL
exercise         TEXT NOT NULL
reps             INTEGER NOT NULL DEFAULT 0
hold_seconds     INTEGER            -- plank only (REQ-4.7)
avg_form_score   REAL
closed_at        TEXT
```
Index: `sets(session_id, set_number)`.

**`form_score_samples`**
```
id          INTEGER PRIMARY KEY AUTOINCREMENT
set_id      INTEGER NOT NULL REFERENCES sets(id)
score       INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100)
sampled_at  TEXT NOT NULL
```
Sampled once per second during a set. Used to compute per-set `avg_form_score` and the trend array (REQ-7.4).  
Index: `form_score_samples(set_id)`.

**`calorie_segments`**  
Maps to the Calorie Engine's `CalorieSegment` objects (REQ-5.3, REQ-5.4):
```
id           INTEGER PRIMARY KEY AUTOINCREMENT
session_id   TEXT NOT NULL REFERENCES sessions(id)
exercise     TEXT NOT NULL
weight_kg    REAL NOT NULL    -- snapshot of weight at segment open (REQ-5.6)
started_at   TEXT NOT NULL
ended_at     TEXT
calories     REAL NOT NULL DEFAULT 0.0
duration_seconds INTEGER
```
Index: `calorie_segments(session_id)`.

**`goals`**
```
id               INTEGER PRIMARY KEY AUTOINCREMENT
user_id          INTEGER NOT NULL REFERENCES users(id)
type             TEXT NOT NULL CHECK(type IN ('daily','weekly'))
target_calories  REAL NOT NULL
created_at       TEXT NOT NULL
active           INTEGER NOT NULL DEFAULT 1  -- boolean
```

**`streaks`**
```
id           INTEGER PRIMARY KEY AUTOINCREMENT
user_id      INTEGER NOT NULL REFERENCES users(id) UNIQUE
current      INTEGER NOT NULL DEFAULT 0
best         INTEGER NOT NULL DEFAULT 0
last_active  TEXT    -- date of last completed session
```
Updated on session completion. Streak logic (REQ-7.5, REQ-7.6): if `date(now) - date(last_active) == 1 day`, increment current; if `> 1 day`, reset current to 1; update best if current > best.

### 4.2 Segmented Calorie → Table Mapping (REQ-5.3)

One session generates N `calorie_segments` rows (one per exercise type encountered). The session's `total_calories` is a materialised sum of all its segment `calories` values, written on session end. This avoids re-aggregating at query time while keeping the audit trail of per-exercise attribution.

### 4.3 Per-Set Form Average → Table Mapping

`form_score_samples` stores raw samples; `sets.avg_form_score` stores the computed average, written when the set is closed. The trend array returned by `GET /api/v1/progress/form` is assembled by querying `sets.avg_form_score` ordered by session date, grouped by exercise type (REQ-7.4).

---

## 5. Frontend Design

> **Scope note:** This section defines component boundaries, props/state contracts, and data integration points only. Visual styling, colour palette, typography, and animation are owned by Antigravity using UI/UX Pro Max and 21st.dev MCP.

### 5.1 Component Tree

```
App
├── ProfileSetupScreen          -- shown on first load if no profile (REQ-9.1)
├── CompatibilityWarningScreen  -- shown if getUserMedia/WebSocket unsupported (REQ-8.3)
└── MainLayout
    ├── NavBar
    ├── SessionView              -- active during a session
    │   ├── CameraCanvas         -- renders video feed + pose landmark overlay
    │   ├── FeedbackPanel
    │   │   ├── ExerciseLabel    -- confirmed exercise type + confidence
    │   │   ├── RepCounter       -- current set reps + set number
    │   │   ├── CalorieDisplay   -- running calorie estimate (REQ-5.5)
    │   │   ├── FormScoreGauge   -- rolling form score 0–100 (REQ-3.5)
    │   │   └── CorrectionCues  -- up to 2 cue strings (REQ-3.3)
    │   ├── WarningBanner        -- "Move into frame" / "Exercise not recognized"
    │   └── SessionControls      -- Start / End session buttons
    ├── SessionSummaryView       -- shown after session end (REQ-6.2)
    │   ├── SummaryStats         -- total reps, calories, duration, avg form score
    │   ├── SetBreakdownTable    -- per-set reps, exercise, form score
    │   └── CalorieSegmentChart  -- per-exercise calorie bars for this session
    ├── HistoryView              -- list of past sessions (REQ-7.1)
    │   ├── SessionList
    │   └── SessionDetailDrawer  -- on row select, shows SessionDetail (REQ-7.2)
    ├── ProgressDashboard        -- charts and trends (REQ-7.3, REQ-7.4)
    │   ├── CalorieTimelineChart -- last 30 sessions calories over time
    │   ├── FormTrendChart       -- per-exercise form score trend
    │   ├── StreakWidget         -- current streak + best (REQ-7.5, REQ-7.6)
    │   └── GoalsWidget          -- daily/weekly goal progress (REQ-7.7, REQ-7.8)
    └── ProfileView              -- name + weight edit (REQ-9.3, REQ-9.4)
```

### 5.2 State Management

**Real-time WebSocket state** is managed in a dedicated `usePoseSession` hook that owns the WebSocket connection lifecycle. It exposes:

```typescript
interface PoseSessionState {
  connected: boolean
  exercise: string | null
  repCount: number
  setNumber: number
  formScore: number
  corrections: string[]
  caloriesRunning: number
  warning: string | null
  landmarks: Landmark[]
}
```

This state is updated on every incoming WebSocket message. Components consuming real-time data subscribe to this hook. No global state library is needed for the WebSocket path — the hook provides the single source of truth.

**REST-fetched data** (history, progress, profile, goals) is managed with standard React Query (or equivalent) — cached, with stale-while-revalidate, invalidated on session end. This separates the high-frequency real-time path from the low-frequency historical data path.

**Session lifecycle state** (idle / active / ended / interrupted) is held in a `useSessionLifecycle` hook that coordinates `start_session` and `end_session` REST calls with the WebSocket connection open/close sequence.

### 5.3 CameraCanvas Contract

The `CameraCanvas` component receives the `landmarks` array from `usePoseSession` and renders them as an overlay on the live video element. Props contract:

```typescript
interface CameraCanvasProps {
  landmarks: Landmark[]           // from WebSocket state
  videoRef: RefObject<HTMLVideoElement>
  width: number
  height: number
}
```

The canvas is sized to match the video element and draws landmark points and connecting skeleton lines. No form logic runs in this component — it is purely a rendering layer.

---

## 6. Network & Deployment

### 6.1 Local IP Binding (REQ-8.1, REQ-8.2)

FastAPI is launched with `host="0.0.0.0"` and a configurable `port` (default 8443 over HTTPS). This makes the server reachable at the host machine's LAN IP. A startup log message prints the LAN IP so the user knows the address to enter on their mobile browser.

### 6.2 HTTPS / Secure Context Requirement (REQ-8.2)

**Problem:** Modern browsers (Chrome, Firefox, Safari) only allow `getUserMedia` (camera access) in a **secure context** — `https://` or `http://localhost`. A plain `http://10.x.x.x` LAN address is not a secure context, so the camera is blocked regardless of browser version.

**Solution:** The FastAPI backend serves over **HTTPS** using a self-signed TLS certificate. Both the REST API and WebSocket endpoint (`wss://`) use TLS. The React frontend is served over HTTPS by the Vite dev server in development and by FastAPI's `StaticFiles` in production.

**Certificate generation:**
```bash
python scripts/gen_cert.py
```
This generates `certs/local.crt` and `certs/local.key` with Subject Alternative Names for `localhost`, `127.0.0.1`, and all detected LAN IPs (e.g. `10.11.92.234`).

**First-access browser warning:** Because the certificate is self-signed, browsers will show a "Your connection is not private" warning on first access. Users must click "Advanced → Proceed" (Chrome) or "Accept the Risk" (Firefox) once. This is expected and documented in the README.

**Port:** Backend runs on `0.0.0.0:8443` (HTTPS). Frontend Vite dev server also uses HTTPS on `5173`.

**API base URLs in frontend:** `https://<hostname>:8443` for REST, `wss://<hostname>:8443` for WebSocket. The hostname is resolved dynamically from `window.location.hostname` so the same build works from both `localhost` and a LAN IP.

### 6.3 CORS Configuration

CORS is configured to allow all origins (`*`) on the REST and WebSocket endpoints. This is safe because:
- The server is only accessible on the local network (no public exposure).
- There is no authentication or session token to protect.
- The user deliberately navigates to the local IP.

### 6.4 Static Asset Serving (REQ-10.2)

FastAPI mounts the React build output directory at `/` using `StaticFiles`. The React build is produced ahead of time (`npm run build`) with all assets inlined or bundled. No CDN links are present in the built output. All fonts and icons required by the UI are included in the build bundle.

### 6.5 External Request Blocking (REQ-8.4, REQ-8.5, REQ-10.4)

**Content Security Policy (CSP):** The FastAPI backend injects a `Content-Security-Policy` header on every HTML response:

```
Content-Security-Policy:
  default-src 'self';
  connect-src 'self' ws://localhost:* wss://localhost:* ws://192.168.* wss://192.168.* wss://10.*;
  img-src 'self' data:;
  style-src 'self' 'unsafe-inline';
  script-src 'self'
```

This causes the browser to block any attempt by frontend code to contact external domains.

**Dependency Audit:** As part of the offline verification process, all Python and npm dependencies are checked at setup time to confirm they do not include telemetry or auto-update network calls. Any dependency found to make external calls is flagged and replaced (REQ-10.4).

**Runtime Python Guard:** A custom `urllib` / `httpx` / `requests` import hook is installed at application startup that logs and raises an error if any module attempts to open a connection to an address outside `127.0.0.1` or the RFC-1918 private address space (REQ-8.5).

---

## 7. Offline & Reliability Strategy

### 7.1 Local Model Loading (REQ-10.3)

At FastAPI startup, the application initialises two model objects:
1. `mediapipe.solutions.pose.Pose` — loaded from the MediaPipe package installed in the local Python environment.
2. `joblib.load("models/exercise_classifier.pkl")` — the trained Random Forest, loaded from the local filesystem.

If either fails to load, the server logs a fatal error and exits. No fallback to a remote model endpoint exists.

### 7.2 Interrupted Session Recovery (REQ-6.3, REQ-6.4)

**Detection:** WebSocket heartbeat failure (3 missed pongs) or OS signal triggers the INTERRUPTED transition in the Session Manager.

**Partial write:** The Session Manager flushes the current in-memory state (rep counts, calorie total, form scores, all open sets) to SQLite, setting `sessions.status = 'interrupted'`.

**Recovery on next load:** On frontend initialisation, the app calls `GET /api/v1/sessions?status=interrupted&limit=1`. If a result is returned, the frontend displays a dismissible banner: "Your last session was interrupted. View partial data?" linking to the SessionDetailDrawer for that session. The interrupted session is never automatically continued — a new session must be started explicitly.

### 7.3 Concurrent Session Enforcement (REQ-6.5)

The `active_session_id` application-state variable is set to the session UUID on `start_session` and cleared on `end_session` or INTERRUPTED transition. Any `start_session` request while the variable is non-null returns `409 SESSION_ALREADY_ACTIVE`. This is checked before any database write.

---

## 8. Design Decisions & Tradeoffs

### 8.1 Random Forest vs Deep Learning

**Decision:** scikit-learn Random Forest for exercise classification.

**Reasoning:**
- **Offline feasibility:** A trained Random Forest model serialised with `joblib` is typically 1–5 MB and loads in milliseconds. A CNN or LSTM would require PyTorch/TensorFlow runtime, adding hundreds of MB to the offline bundle.
- **Small dataset:** The self-generated training dataset is limited in size. Deep learning models underfit on small datasets; Random Forests generalise well with hundreds to low thousands of samples.
- **Latency:** Feature extraction (10 joint angles) + Random Forest inference completes in < 5 ms, well within the 200 ms latency budget (REQ-1.5). A neural network inference pass is faster in absolute terms but the runtime overhead of loading the framework into the process offsets this advantage.
- **Explainability:** Feature importances from the Random Forest can be inspected to verify the classifier is using meaningful joint angles, aiding future threshold tuning.

### 8.2 WebSocket vs HTTP Polling for Real-Time Feedback

**Decision:** WebSocket for the pose processing channel.

**Reasoning:**
- At 15 FPS, HTTP polling would require 15 new requests per second. Each request incurs TCP + HTTP handshake overhead, making it structurally incompatible with the 200 ms end-to-end latency requirement (REQ-1.5).
- WebSocket maintains a single persistent connection with negligible per-message overhead.
- The server-push model (server sends feedback immediately on frame completion) is a natural fit for WebSocket and cannot be replicated with polling without either high latency or excessive request frequency.

### 8.3 Rule-Based Joint Angle Thresholds vs Learned Form Scoring

**Decision:** Rule-based joint angle threshold tables for form evaluation.

**Reasoning:**
- **REQ-3.2 specificity:** A learned form-scoring model produces a score but cannot directly produce specific corrective cues ("Drive knees out") — it would require a secondary mapping. Rule-based thresholds directly encode the cue alongside the condition.
- **REQ-3.3 prioritisation:** Explicit `severity_weight` values in the threshold tables give transparent, tunable control over cue prioritisation. A learned model's internal rankings are opaque.
- **Transparency:** Fitness form rules are well-established in exercise science literature. Encoding them explicitly in versioned config tables is more auditable and maintainable than a learned model that may encode incorrect patterns from a biased training set.
- **No training data needed:** Collecting labelled "correct/incorrect form" video data at sufficient scale is impractical for a self-generated dataset. Threshold tables require only domain knowledge, not data.

### 8.4 Nearest-Person Selection: Geometric Rule vs Person Re-identification

**Decision:** Deterministic bounding-box-area selection (largest area = nearest person) rather than person re-identification or tracking-by-identity.

**Reasoning:**
- **Privacy-first principle:** Person re-identification requires either face recognition, body appearance embeddings, or persistent identity vectors — all of which constitute biometric processing. This directly conflicts with the privacy-first core principle in the steering document, which explicitly excludes identity recognition.
- **No persistent state needed:** The bounding-box area rule is stateless and frame-local — it requires no memory of who was in the previous frame. Tracking-by-identity maintains a persistent embedding per person across frames, which is both computationally heavier and stores implicitly identifying information.
- **Predictable behaviour in shared spaces:** A deterministic geometric rule ("nearest person wins, always") is easy for the user to understand and exploit — simply stand closer to the camera than anyone else in the room. There is no ambiguity about which person the system is tracking, and no risk of the tracker silently switching to a different person mid-set.
- **Sufficient for the use case:** Burn-Ex is designed for single-user home workouts. Multi-person presence in the camera frame is an edge case (family member walking past), not a primary scenario. The nearest-person rule handles this edge case predictably without overengineering the solution.
- **Latency compatibility (REQ-1.5):** Bounding-box area comparison is O(N) and completes in microseconds. Re-identification models (e.g., OSNet, torchreid) add 20–80 ms per frame, which would consume a significant fraction of the 200 ms latency budget.

---

*End of design document. Implementation task breakdown is specified in `tasks.md`.*
