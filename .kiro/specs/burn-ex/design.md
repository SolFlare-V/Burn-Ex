# Design Document — Burn-Ex Cloud

> **Spec stage:** Design
> **Depends on:** `requirements.md`, `.kiro/steering/burn-ex-project.md`
> **REQ references** are cited inline using REQ-N.N notation.

---

## 1. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  User's Browser (Firebase Hosting CDN)                      │
│                                                             │
│  ┌──────────────┐   landmarks   ┌──────────────────────┐   │
│  │  MediaPipe   │──────────────▶│  WebSocket Client    │   │
│  │  WASM        │               │  (authenticated)     │   │
│  │  (CV engine) │               └──────────┬───────────┘   │
│  └──────────────┘                          │ WSS            │
│  ┌──────────────┐                          │                │
│  │  React UI    │◀─── analysis results ────┘                │
│  │  + Auth SDK  │                                           │
│  └──────┬───────┘                                           │
└─────────┼───────────────────────────────────────────────────┘
          │ HTTPS (REST + Firebase Auth)
          ▼
┌─────────────────────┐        ┌────────────────────────┐
│  Firebase Auth      │        │  Render — FastAPI       │
│  (token issuance,   │        │                         │
│   Google Sign-In,   │        │  ┌─────────────────┐   │
│   onAuthStateChange)│        │  │ Auth Middleware  │   │
└─────────────────────┘        │  ├─────────────────┤   │
          ▲                    │  │ ML Pipeline     │   │
          │ token verify       │  ├─────────────────┤   │
          └────────────────────│  │ Calorie Engine  │   │
                               │  ├─────────────────┤   │
                               │  │ Session Manager │   │
                               │  ├─────────────────┤   │
                               │  │ WebSocket Server│   │
                               │  └────────┬────────┘   │
                               └───────────┼────────────┘
                                           │ async SQLAlchemy
                                           ▼
                               ┌────────────────────────┐
                               │  Supabase — PostgreSQL  │
                               │  (per-user data store)  │
                               └────────────────────────┘
```

**Key invariants:**
- Video frames never leave the browser (REQ-3.2)
- Every backend request carries a verified Firebase ID token (REQ-1.3, REQ-1.4)
- Every DB write carries `user_id = firebase_uid` from the verified token (REQ-2.5)
- CORS allows only the Firebase Hosting origin (REQ-10.3)

---

## 2. Authentication Flow

### 2.1 Sign-In

```
Browser                    Firebase Auth           Backend
  │                              │                    │
  │── onAuthStateChanged ────────▶                    │
  │   (listener registered)      │                    │
  │                              │                    │
  │── signInWithPopup ──────────▶│                    │
  │                    Google OAuth flow              │
  │◀── UserCredential ──────────│                    │
  │    (includes ID token)       │                    │
  │                              │                    │
  │   store token in memory      │                    │
  │   (never localStorage)       │                    │
  │                              │                    │
  │── GET /api/v1/user ─────────────────────────────▶│
  │   Authorization: Bearer <token>                   │
  │                         verify token (Admin SDK)  │
  │                         extract firebase_uid      │
  │◀── 200 profile / 404 (new user) ────────────────│
```

### 2.2 Token Refresh (mid-session)

Firebase Auth SDK calls `getIdToken(forceRefresh=true)` automatically before expiry.
The frontend sends a `{type: "token_refresh", token: "<new_token>"}` message over the existing WebSocket.
The backend verifies the new token; on success, replaces the stored `firebase_uid` for the connection (must match original — no identity switching).
On failure: persist session as interrupted → close `4001` → frontend redirects to sign-in (REQ-1.7).

### 2.3 Sign-Out & External State Change

```
onAuthStateChanged fires (user = null)
  │
  ├── close WebSocket (triggers interrupted-session persistence, REQ-8.3)
  ├── clear in-memory token
  └── navigate to /sign-in
```

Both explicit sign-out (`signOut()`) and externally triggered state changes use the same `onAuthStateChanged` handler path (REQ-1.8, REQ-1.9).

### 2.4 REST Auth Middleware

All routes except `GET /health` pass through `verify_firebase_token` dependency:

```python
async def verify_firebase_token(
    authorization: str = Header(...),
) -> str:  # returns firebase_uid
    token = authorization.removeprefix("Bearer ")
    decoded = firebase_admin.auth.verify_id_token(token)
    return decoded["uid"]
```

Returns `401` if token is missing, expired, or invalid (REQ-1.4).

---

## 3. Browser-Side CV Module

### 3.1 Initialization

```typescript
// cv/PoseDetector.ts
import { PoseLandmarker, FilesetResolver } from "@mediapipe/tasks-vision";

const filesetResolver = await FilesetResolver.forVisionTasks(
  "/mediapipe/wasm"  // served from Firebase Hosting; no external CDN (REQ-10.5)
);
const poseLandmarker = await PoseLandmarker.createFromOptions(filesetResolver, {
  baseOptions: { modelAssetPath: "/mediapipe/pose_landmarker.task" },
  runningMode: "VIDEO",
  numPoses: 1,  // nearest-person selection done via largest-bbox filter (REQ-3.7)
  minPoseDetectionConfidence: 0.5,
  minTrackingConfidence: 0.5,
});
```

All model files (`pose_landmarker.task`, WASM binaries) are deployed to Firebase Hosting under `/mediapipe/`. No runtime fetch to `cdn.jsdelivr.net` or any external origin (REQ-3.1, REQ-10.5).

### 3.2 Frame Loop

```typescript
// Runs on requestAnimationFrame inside a Web Worker where supported,
// falls back to main thread with yielding via scheduler.postTask / setTimeout(0)
function detectFrame(videoElement: HTMLVideoElement, timestampMs: number) {
  const results = poseLandmarker.detectForVideo(videoElement, timestampMs);
  if (results.landmarks.length === 0) return;

  const landmarks = selectNearestPerson(results);  // largest bounding box (REQ-3.7)
  const confidenceFlags = landmarks.map(lm => lm.visibility >= 0.5);  // REQ-3.4
  const lowConfCount = confidenceFlags.filter(f => !f).length;

  if (lowConfCount / landmarks.length > 0.30) {
    emitWarning("Move into frame");  // REQ-3.5
    return;
  }

  wsClient.sendLandmarkFrame({ timestamp: timestampMs / 1000, landmarks });
}
```

### 3.3 Nearest-Person Selection (REQ-3.7)

When `results.landmarks` contains more than one pose set, the set with the largest axis-aligned bounding box (max span of x-coordinates × max span of y-coordinates) is selected. All others are discarded before transmission.

### 3.4 Latency Budget (REQ-3.3)

| Stage | Budget |
|---|---|
| MediaPipe inference (browser, mid-range device) | ≤ 80 ms |
| WS frame serialisation + network (landmark JSON ~2 KB) | ≤ 80 ms |
| Backend inference + response | ≤ 140 ms |
| **Total end-to-end** | **≤ 300 ms** |

The 15 FPS minimum (REQ-3.1) means a frame is available every ~67 ms; the 300 ms budget spans ~4.5 frames, which is acceptable for correction cue display latency.

---

## 4. WebSocket Protocol

### 4.1 Connection Lifecycle

```
Client                                    Server (/ws/pose)
  │                                            │
  │── WS Upgrade ──────────────────────────▶  │
  │── {type:"auth", token:"<ID_token>"} ────▶  │
  │                              verify token  │
  │                    OK: store firebase_uid  │
  │◀── {type:"auth_ok"} ──────────────────── │
  │                                            │
  │── {type:"landmark_frame", ...} ─────────▶ │  (REQ-3.3)
  │◀── {type:"analysis_result", ...} ──────── │
  │   ... (continuous during session) ...      │
  │                                            │
  │── {type:"token_refresh", token:"..."} ──▶ │  (REQ-1.7)
  │◀── {type:"auth_ok"} ──────────────────── │
  │                                            │
  │── {type:"session_end"} ─────────────────▶ │
  │◀── {type:"session_summary", ...} ──────── │
  │── WS Close (1000 Normal) ───────────────▶ │
```

**Auth failure at any point** → server sends close code `4001` (REQ-1.6, REQ-1.7).

### 4.2 Message Schemas

**Client → Server: `landmark_frame`**
```json
{
  "type": "landmark_frame",
  "timestamp": 1720000000.123,
  "landmarks": [
    { "id": 0, "x": 0.52, "y": 0.31, "z": -0.04, "visibility": 0.99 }
  ]
}
```
33 landmarks always present; low-confidence ones have `visibility < 0.5` (REQ-3.4).

**Server → Client: `analysis_result`**
```json
{
  "type": "analysis_result",
  "timestamp": 1720000000.123,
  "exercise": "squat",
  "confidence": 0.87,
  "rep_count": 5,
  "set_number": 2,
  "form_score": 83,
  "corrections": ["Keep chest up"],
  "calories_so_far": 47.2,
  "hold_duration_s": null
}
```
`hold_duration_s` is non-null only during plank (REQ-6.7). `corrections` is empty array when form is good (REQ-5.4).

**Client → Server: `token_refresh`**
```json
{ "type": "token_refresh", "token": "<new_firebase_id_token>" }
```

**Client → Server: `session_end`**
```json
{ "type": "session_end" }
```

**Server → Client: `warning`**
```json
{ "type": "warning", "code": "low_confidence", "message": "Move into frame" }
```

**Server → Client: `session_summary`** — same shape as REST `GET /api/v1/sessions/{id}` response.

### 4.3 WebSocket Close Codes

| Code | Meaning |
|---|---|
| `1000` | Normal closure (session ended cleanly) |
| `4001` | Auth failure (missing/invalid/expired token, failed refresh) |
| `4002` | Session conflict (duplicate active session; should not normally occur via WS) |
| `1011` | Unexpected server error |

---

## 5. Backend Module Structure

```
backend/
├── main.py                  # FastAPI app, CORS config, router registration
├── database.py              # Async SQLAlchemy engine + SessionLocal factory
├── db_init.py               # Table creation on startup
├── startup.py               # Firebase Admin SDK init, model load
│
├── auth/
│   └── firebase.py          # verify_firebase_token dependency (REQ-1.4)
│
├── cv/                      # CV utilities — angle calculation only (no inference)
│   ├── angle_utils.py       # Joint angle computation from landmark coords
│   ├── confidence_filter.py # Low-confidence landmark detection (REQ-3.4, REQ-3.5)
│   └── person_selector.py   # Nearest-person selection (kept for reference; used browser-side)
│
├── ml/
│   ├── classifier.py        # Random Forest load + predict (static model, REQ-4.1)
│   ├── feature_extractor.py # Landmark → feature vector for RF input
│   ├── confirmation_window.py # 10-frame sustained confidence (REQ-4.4)
│   └── unrecognised_timer.py  # 3-second unrecognised exercise timer (REQ-4.3)
│
├── scoring/
│   ├── engine.py            # Joint angle evaluation, form score 0-100 (REQ-5.1–5.5)
│   ├── form_score.py        # Per-frame score + per-set rolling average
│   ├── cue_generator.py     # Exercise-specific corrective cue selection (REQ-5.2, REQ-5.3)
│   └── plank_scorer.py      # Static hold evaluation (REQ-5.7)
│
├── reps/
│   ├── counter.py           # Concentric–eccentric cycle detection (REQ-6.1, REQ-6.2)
│   ├── state_machine.py     # Per-exercise rep state machine
│   ├── set_tracker.py       # Set open/close, 8-second pause detection (REQ-6.4)
│   ├── pause_timer.py       # Movement pause timer
│   └── plank_timer.py       # Hold duration tracker (REQ-6.7)
│
├── calories/
│   └── engine.py            # MET × weight × duration calculation (REQ-7.1, REQ-7.3)
│
├── session/
│   ├── manager.py           # Session state machine (REQ-8.1–8.7)
│   └── persistence.py       # Incremental DB writes, interrupted-session save (REQ-8.3, REQ-8.6)
│
├── routers/
│   ├── user.py              # GET/PUT /api/v1/user (REQ-11.*)
│   ├── sessions.py          # GET /api/v1/sessions, GET /api/v1/sessions/{id}
│   ├── goals.py             # GET/POST/PUT /api/v1/goals
│   ├── streaks.py           # GET /api/v1/streaks
│   ├── progress.py          # GET /api/v1/progress (dashboard aggregates)
│   └── ws_pose.py           # WebSocket /ws/pose handler
│
└── models/                  # SQLAlchemy ORM models (one file per table)
    ├── users.py
    ├── sessions.py
    ├── sets.py
    ├── form_score_samples.py
    ├── calorie_segments.py
    ├── goals.py
    └── streaks.py
```

### 5.1 WebSocket Handler (`ws_pose.py`) Flow

```python
@app.websocket("/ws/pose")
async def ws_pose(websocket: WebSocket, db: AsyncSession):
    await websocket.accept()
    uid = await authenticate_handshake(websocket)   # closes 4001 on failure
    session = await session_manager.get_or_create(uid, db)
    try:
        async for message in websocket.iter_json():
            match message["type"]:
                case "landmark_frame":
                    result = await process_frame(uid, message, session)
                    await websocket.send_json(result)
                case "token_refresh":
                    uid = await re_authenticate(websocket, message["token"], uid)
                case "session_end":
                    summary = await session_manager.end(session, db)
                    await websocket.send_json(summary)
                    await websocket.close(1000)
                    return
    except WebSocketDisconnect:
        await session_manager.mark_interrupted(session, db)  # REQ-8.3
```

### 5.2 ML Pipeline — Landmark-Visibility Gate

A knee-visibility gate was added to `ml/pipeline.py` (between the classifier prediction and the confirmation window) to prevent misclassification when required knee landmarks are absent. The gate is scoped per predicted class: `plank`, `squat`, `lunge`, and `push_up` require at least one knee angle to be present in the `angle_map`; `shoulder_press` and `bicep_curl` are exempt because their exercise triplet sets legitimately never compute knees. This fixed a self-reinforcing feedback loop: once `plank` was wrongly confirmed, `angle_utils` would switch to the plank-specific triplet set which excludes knees entirely — causing imputed knee medians to perpetually match the plank training distribution and lock the classifier into plank regardless of actual movement. With the gate active, any plank prediction without knee data is suppressed to `None`, the confirmation window loses its majority within 2–3 frames, and the pipeline resets cleanly.

---

## 6. Database Schema

All tables use `user_id VARCHAR NOT NULL` as a foreign key referencing `users.firebase_uid`. Row-level security is enforced in application code (REQ-2.1); Supabase RLS policies are an additional defence-in-depth layer but are not relied upon as the sole control.

### `users`
| Column | Type | Constraints |
|---|---|---|
| `firebase_uid` | `VARCHAR(128)` | PK |
| `display_name` | `VARCHAR(100)` | nullable |
| `weight_kg` | `NUMERIC(5,2)` | nullable; required before session start (REQ-7.2) |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default now() |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default now() |

### `sessions`
| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | PK, default gen_random_uuid() |
| `user_id` | `VARCHAR(128)` | FK → users.firebase_uid, NOT NULL |
| `status` | `VARCHAR(16)` | NOT NULL; `active` / `completed` / `interrupted` |
| `started_at` | `TIMESTAMPTZ` | NOT NULL |
| `ended_at` | `TIMESTAMPTZ` | nullable |
| `exercise` | `VARCHAR(32)` | nullable (set on first confirmed classification) |
| `total_reps` | `INTEGER` | NOT NULL, default 0 |
| `total_sets` | `INTEGER` | NOT NULL, default 0 |
| `calories_burned` | `NUMERIC(8,2)` | NOT NULL, default 0 |
| `avg_form_score` | `NUMERIC(5,2)` | nullable |
| `last_updated` | `TIMESTAMPTZ` | NOT NULL, default now(); updated on each incremental persist |
| `weight_kg_at_start` | `NUMERIC(5,2)` | NOT NULL; snapshot of weight at session start (REQ-7.6) |

**Indexes:** `(user_id, status)` for interrupted-session lookup; `(user_id, started_at DESC)` for history queries.

### `sets`
| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | PK |
| `user_id` | `VARCHAR(128)` | FK → users.firebase_uid, NOT NULL |
| `session_id` | `UUID` | FK → sessions.id, NOT NULL |
| `set_number` | `INTEGER` | NOT NULL |
| `exercise` | `VARCHAR(32)` | NOT NULL |
| `rep_count` | `INTEGER` | NOT NULL, default 0 |
| `hold_duration_s` | `INTEGER` | nullable (plank only) |
| `avg_form_score` | `NUMERIC(5,2)` | nullable |
| `started_at` | `TIMESTAMPTZ` | NOT NULL |
| `ended_at` | `TIMESTAMPTZ` | nullable |

### `form_score_samples`
| Column | Type | Constraints |
|---|---|---|
| `id` | `BIGSERIAL` | PK |
| `user_id` | `VARCHAR(128)` | FK → users.firebase_uid, NOT NULL |
| `session_id` | `UUID` | FK → sessions.id, NOT NULL |
| `set_id` | `UUID` | FK → sets.id, NOT NULL |
| `sampled_at` | `TIMESTAMPTZ` | NOT NULL |
| `score` | `NUMERIC(5,2)` | NOT NULL |

Sampled at ~1 Hz during active sets. Used for per-set trend calculation (REQ-9.2, REQ-9.4).

### `calorie_segments`
| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | PK |
| `user_id` | `VARCHAR(128)` | FK → users.firebase_uid, NOT NULL |
| `session_id` | `UUID` | FK → sessions.id, NOT NULL |
| `exercise` | `VARCHAR(32)` | NOT NULL |
| `met_value` | `NUMERIC(4,2)` | NOT NULL |
| `duration_s` | `INTEGER` | NOT NULL |
| `calories` | `NUMERIC(8,2)` | NOT NULL |

One row per exercise-type segment within a session (REQ-7.3, REQ-7.4).

### `goals`
| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | PK |
| `user_id` | `VARCHAR(128)` | FK → users.firebase_uid, NOT NULL |
| `period` | `VARCHAR(8)` | NOT NULL; `daily` / `weekly` |
| `target_calories` | `NUMERIC(8,2)` | NOT NULL |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `active` | `BOOLEAN` | NOT NULL, default true |

### `streaks`
| Column | Type | Constraints |
|---|---|---|
| `user_id` | `VARCHAR(128)` | PK, FK → users.firebase_uid |
| `current_streak` | `INTEGER` | NOT NULL, default 0 |
| `best_streak` | `INTEGER` | NOT NULL, default 0 |
| `last_session_date` | `DATE` | nullable; UTC date of most recent completed session |

---

## 7. REST API Endpoints

All endpoints except `GET /health` require `Authorization: Bearer <firebase_id_token>`. The `firebase_uid` is extracted from the verified token and used to scope all queries.

### Health

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | None | Render health check; returns `{"status":"ok"}` |

### User Profile (REQ-11.*)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/user` | Required | Returns profile for `firebase_uid`. 404 if not yet created. |
| POST | `/api/v1/user` | Required | Creates profile on first sign-in (REQ-11.1). Body: `{display_name?, weight_kg}` |
| PUT | `/api/v1/user` | Required | Updates `display_name` or `weight_kg`. Returns 403 if session is active (REQ-11.5). |

### Sessions (REQ-8.*, REQ-9.*)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/sessions` | Required | Starts a new session. Returns 409 if one is already active (REQ-2.4). Returns `{session_id}`. |
| GET | `/api/v1/sessions` | Required | Lists sessions for `firebase_uid`, ordered by `started_at DESC`. Query params: `limit` (default 30), `status` filter. |
| GET | `/api/v1/sessions/{id}` | Required | Returns full session detail. 404 if not found or owned by different user (REQ-2.2). |
| POST | `/api/v1/sessions/{id}/end` | Required | Ends an active session. Returns session summary. 403 if session is not active. |
| POST | `/api/v1/sessions/{id}/resume` | Required | Resumes an interrupted session. Returns 409 if another session is active. |
| DELETE | `/api/v1/sessions/{id}` | Required | Discards an interrupted session (sets status to `discarded`). 403 if session is active. |

### Goals (REQ-9.7, REQ-9.8)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/goals` | Required | Returns active goals for `firebase_uid`. |
| POST | `/api/v1/goals` | Required | Creates a new goal. Body: `{period: "daily"|"weekly", target_calories}`. |
| PUT | `/api/v1/goals/{id}` | Required | Updates target. 403 if goal not owned by user. |
| DELETE | `/api/v1/goals/{id}` | Required | Deactivates goal. |

### Streaks (REQ-9.5, REQ-9.6)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/streaks` | Required | Returns `{current_streak, best_streak, last_session_date}` for `firebase_uid`. |

### Progress Dashboard (REQ-9.3, REQ-9.4)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/progress/calories` | Required | Last 30 sessions: `[{date, calories_burned}]`. |
| GET | `/api/v1/progress/form` | Required | Form score trends per exercise type (min 2 sessions, last 10 per type). |

---

## 8. Session Lifecycle State Machine

```
          ┌──────────┐
          │   IDLE   │  (no session or previous session ended/discarded)
          └────┬─────┘
               │ POST /api/v1/sessions  (weight set, no active session)
               ▼
          ┌──────────┐
          │  ACTIVE  │◀──────────────────────────────────┐
          └────┬─────┘                                    │
     ┌─────────┼─────────┐                 POST /sessions/{id}/resume
     │         │         │                    (interrupted session)
     │    WS   │   POST  │                               │
     │  drop   │  /end   │               ┌───────────────┴──┐
     ▼         ▼         │               │   INTERRUPTED    │
┌──────────┐  ┌────────┐ │               └──────────────────┘
│INTERRUPTED│  │COMPLETE│ │
└──────────┘  └────────┘ │
     │                   │ (user chooses discard)
     │ DELETE /sessions/{id}
     ▼
┌──────────┐
│ DISCARDED│
└──────────┘
```

**Transitions:**

| From | Event | To | Action |
|---|---|---|---|
| IDLE | POST /sessions | ACTIVE | Create session row, snapshot weight |
| ACTIVE | POST /sessions/{id}/end | COMPLETED | Finalize calorie segments, set totals, close sets |
| ACTIVE | WS disconnect / Render restart | INTERRUPTED | Persist partial state, set last_updated |
| ACTIVE | POST /sessions (duplicate) | — | 409, no state change |
| INTERRUPTED | POST /sessions/{id}/resume | ACTIVE | Restore state to client |
| INTERRUPTED | DELETE /sessions/{id} | DISCARDED | Soft-delete (status change only) |
| COMPLETED / DISCARDED | — | IDLE | No action needed |

**Incremental persistence** (REQ-8.6): A background task within the WebSocket handler calls `session_persistence.checkpoint()` every 30 seconds, writing current `total_reps`, `calories_burned`, and `last_updated` to the `sessions` row.

---

## 9. Frontend Component Structure & State Management

### 9.1 Route Structure

```
/                   → AuthGuard → redirects to /sign-in or /dashboard
/sign-in            → SignInPage
/dashboard          → DashboardPage (history, progress, goals)
/session            → SessionPage (live workout)
/session/recover    → RecoverSessionPage (interrupted session prompt)
/profile            → ProfilePage
```

`AuthGuard` wraps all protected routes: reads Firebase Auth state; if `user === null`, redirects to `/sign-in`.

### 9.2 Global State (React Context + useReducer)

```typescript
type AuthState = {
  user: FirebaseUser | null;
  idToken: string | null;     // in-memory only (REQ-1.2)
  status: "loading" | "authenticated" | "unauthenticated";
};

type SessionState = {
  sessionId: string | null;
  status: "idle" | "active" | "interrupted" | "ending";
  repCount: number;
  setNumber: number;
  caloriesSoFar: number;
  currentFormScore: number;
  corrections: string[];
  exercise: string | null;
  wsStatus: "connecting" | "connected" | "reconnecting" | "closed";
  coldStartDetected: boolean;  // triggers "Waking up…" UI (REQ-10.1)
};
```

`AuthContext` listens to `onAuthStateChanged`; dispatches `SIGNED_IN` / `SIGNED_OUT`. On `SIGNED_OUT`, SessionContext dispatches `FORCE_END` which closes the WebSocket and persists interrupted state.

### 9.3 WebSocket Client (`hooks/useWorkoutSocket.ts`)

- Establishes connection to `wss://<render-domain>/ws/pose` on session start
- Sends auth handshake immediately on open
- Registers a `setTimeout(10_000)` for cold-start detection (REQ-10.1): if `auth_ok` not received within 10s, sets `coldStartDetected = true`
- On `auth_ok`, clears cold-start timer, sets `wsStatus = "connected"`
- Schedules token refresh: calls `user.getIdToken(true)` when token is <5 min from expiry, sends `token_refresh` message
- On close code `4001`: dispatches `AUTH_FAILED` → triggers sign-out flow
- On unexpected close (code ≠ 1000, ≠ 4001): dispatches `SESSION_INTERRUPTED`

### 9.4 Key Components

| Component | Responsibility |
|---|---|
| `SignInPage` | Firebase `signInWithPopup` trigger, error display |
| `SessionPage` | Orchestrates `PoseDetector`, `useWorkoutSocket`, live metrics display |
| `PoseDetector` | Wraps MediaPipe, emits landmark frames to WebSocket client |
| `MetricsBar` | Rep count, set number, calorie counter, form score badge |
| `CorrectionOverlay` | Displays up to 2 correction cues (REQ-5.3) |
| `ColdStartBanner` | Shows "Waking up server…" when `coldStartDetected = true` (REQ-10.1) |
| `RecoverSessionPage` | Shows interrupted session info; Resume / Discard actions (REQ-8.4, REQ-8.5) |
| `ProgressDashboard` | Calorie time-series chart, form score trends (REQ-9.3, REQ-9.4) |
| `ProfileForm` | Weight / display name input; disables weight field when session active |
