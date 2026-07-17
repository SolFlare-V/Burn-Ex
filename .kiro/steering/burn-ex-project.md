# Burn-Ex — Project Steering Document

## 1. Project Overview

Burn-Ex is a cloud-hosted, AI-powered fitness analytics application that provides real-time posture correction, rep counting, calorie estimation, and progress tracking. Users sign in with their Google account, access the app from any browser, point their camera at themselves during a workout, and receive immediate feedback on exercise form, rep counts, and estimated calories burned.

Pose detection runs entirely in the browser via MediaPipe's JavaScript/WASM build — no video frames ever leave the device. Only lightweight landmark coordinates are transmitted to the backend over WebSocket for inference, calorie calculation, and persistence. Session history, form score trends, streaks, and goals are stored per-user in PostgreSQL (Supabase), scoped to the authenticated user's Firebase UID.

The system is designed for users who want accurate, personalized fitness analytics from any device, with their data isolated securely behind authentication and never shared with other users.

---

## 2. Core Principles

### Auth-Scoped Data Privacy
- Every piece of user data (sessions, workouts, profile, goals, streaks) is scoped to the authenticated user's Firebase UID. No user can access another user's data.
- Video frames are processed entirely in the browser by MediaPipe's JS/WASM runtime and **never transmitted** — only normalized landmark coordinates (x, y, z, visibility) are sent to the backend.
- No data is sold or shared with third parties beyond Firebase Auth's own authentication practices.
- All data in transit is protected by TLS (HTTPS/WSS) on both the Firebase Hosting and Render-hosted backend.

### Accuracy Over Simplicity
- Calorie estimation uses MET (Metabolic Equivalent of Task) equations with exercise-specific coefficients. Simple heuristics are not acceptable substitutes.
- Posture correction feedback must be exercise-specific (squat form feedback ≠ push-up form feedback). Generic "bad form" alerts are insufficient.
- Rep counting must be robust to partial reps and camera angle variation.

### Static, Proven Algorithms
- The trained Random Forest classifier and MET/form-threshold configs are used as-is, unchanged from the validated local version. No retraining, no model versioning, no continuous learning pipeline is in scope for this version.
- The CV approach (MediaPipe Pose, 33 keypoints) and ML approach (scikit-learn Random Forest) are locked in as the algorithmic foundation.

### Structured, Spec-Driven Development
- All features begin as Kiro specs (requirements → design → tasks) before any code is written.
- Data contracts (API schemas, DB schema, WebSocket message formats) are defined before implementation starts.
- Frontend visual polish is handled separately; backend and CV modules must expose clean, stable interfaces.

### Known Infrastructure Limitations
- The Render free tier spins down after ~15 minutes of inactivity. Cold-start latency (~30–60s) is a known limitation. The frontend must display a "Waking up the server…" loading state on first connection after a dormancy period rather than showing a generic error.

---

## 3. Tech Stack & Conventions

### Computer Vision (Browser-Side)
- **Library:** MediaPipe Tasks Vision — `@mediapipe/tasks-vision` (JS/WASM build)
- **Execution:** Runs entirely in the user's browser; no server-side CV processing
- **Input:** Webcam stream via browser `getUserMedia`
- **Output:** Normalized landmark coordinates (x, y, z, visibility) for 33 pose keypoints, sent to backend over WebSocket

### Machine Learning (Backend-Side)
- **Framework:** scikit-learn
- **Model:** Pre-trained Random Forest classifier for exercise type classification — static, no retraining
- **Inference:** Runs on the Render-hosted FastAPI backend, receives landmarks from browser
- **Config:** MET values and form-score thresholds are static config files, not derived from user data

### Calorie Estimation
- **Method:** MET equations — `Calories = MET × weight_kg × duration_hours`
- **MET values:** Curated per exercise type from published exercise science literature
- **Inputs:** User-provided weight (from profile), detected exercise type, session duration, rep count

### Authentication
- **Provider:** Firebase Auth with Google Sign-In
- **Token verification:** Backend verifies Firebase ID tokens on every request using the Firebase Admin SDK
- **User identity:** All backend operations are scoped to the `firebase_uid` extracted from the verified token
- **Session management:** Stateless JWT-based — no server-side session store

### Backend
- **Framework:** FastAPI (Python)
- **Hosting:** Render (free tier — see cold-start limitation above)
- **Responsibilities:** Firebase token verification, ML inference, calorie calculation, session management, REST + WebSocket APIs
- **CORS:** Explicitly allows the Firebase Hosting domain(s) only — no wildcard `"*"`. Since the frontend and backend are different origins and requests carry real authenticated tokens, wildcard CORS is prohibited.

### Database
- **Engine:** PostgreSQL via Supabase (free tier)
- **ORM:** SQLAlchemy (async)
- **Schema ownership:** Kiro — all migrations and schema changes go through Kiro specs
- **Multi-tenancy:** Every user-owned table (`sessions`, `sets`, `form_score_samples`, `calorie_segments`, `goals`, `streaks`) carries a `user_id` foreign key referencing the authenticated user's `firebase_uid`

### Frontend
- **Framework:** React + Vite
- **Styling:** Tailwind CSS
- **Component source:** 21st.dev MCP (via Antigravity)
- **Design system:** UI/UX Pro Max skill (via Antigravity)
- **Hosting:** Firebase Hosting (free tier) — same Firebase project as Auth
- **Data layer:** Consumes REST and WebSocket endpoints defined by Kiro
- **Auth flow:** Firebase Auth SDK handles Google Sign-In; ID token attached to all API requests as `Authorization: Bearer <token>`

### Naming & Code Conventions
- Python: `snake_case` for variables and functions, `PascalCase` for classes
- React components: `PascalCase` filenames and exports
- API routes: `/api/v1/{resource}` prefix for all REST endpoints
- WebSocket endpoint: `/ws/pose` for real-time landmark streaming (requires valid Firebase ID token on connect)
- All API request/response shapes documented as Pydantic models (Python) and TypeScript interfaces (frontend)
- No `any` types in TypeScript

---

## 4. Team & Tool Responsibilities

### Kiro (this agent)
- Writes all Kiro specs: requirements, design documents, implementation task lists
- Owns architecture decisions and data contracts
- Implements: FastAPI backend, Firebase Admin SDK integration, PostgreSQL schema (Supabase), ML inference pipeline, calorie logic, WebSocket server, CORS configuration
- For frontend work: defines component structure, props/state contracts, API integration logic, Firebase Auth integration — does NOT own visual polish, color choices, or animation
- Reviews and validates all specs before implementation begins

### Antigravity
- Owns React dashboard UI implementation
- Uses **UI/UX Pro Max skill** for design system generation and style decisions
- Uses **21st.dev MCP** for component sourcing and generation
- Consumes data contracts and API schemas provided by Kiro
- Does NOT modify backend, CV, or ML modules
- Does NOT define new API endpoints — requests changes through the spec process

### VS Code Copilot
- Owns debugging and bug fixes across all modules (CV, ML, backend, frontend)
- Does NOT introduce new features or architectural changes
- Works from existing specs and code — does not write new specs

### Handoff Protocol
- Kiro publishes API schemas and WebSocket message formats to `docs/contracts/` before Antigravity begins any integration work
- Breaking API changes require a spec update and notification to Antigravity before merge
- Bug reports from Copilot that require design changes are escalated to Kiro for spec revision

---

## 5. Feature Scope

### In Scope
- Firebase Auth with Google Sign-In — required for all access
- Real-time pose landmark detection via MediaPipe JS/WASM (browser-side)
- Exercise classification (squats, push-ups, lunges, etc.) via pre-trained Random Forest (backend-side)
- Exercise-specific posture correction feedback (joint angles, alignment cues)
- Rep counting per set with set tracking
- Calorie estimation per session using MET equations
- Session history: calories over time, form score trends, exercise breakdown
- Streaks and daily/weekly goals (light gamification)
- Browser-based access from any device (laptop, mobile, tablet) on any network
- User profile: weight input (required for calorie calculation), optional display name, linked to Firebase UID
- Multi-user support: concurrent sessions from different authenticated users, all data isolated by UID
- "Waking up" loading state for Render cold-start latency

### Out of Scope
The following are explicitly excluded from this version of Burn-Ex:

| Excluded Feature | Reason |
|---|---|
| External AI APIs (OpenAI, Google Vision, etc.) | No external ML dependencies; static local model only |
| Native mobile app (iOS/Android) | Browser-based access is sufficient |
| Social features (sharing, leaderboards) | Out of scope for this version |
| Video recording or playback | Frames processed in-browser only; never transmitted |
| Paid tiers or licensing | Open, self-hosted tool |
| Wearable device integration | No hardware dependencies beyond webcam |
| Nutrition tracking or diet planning | Out of scope; calorie burn only |
| Model retraining / continuous learning from user data | Static pre-trained model only; no ML pipeline, no data retention for training purposes |
| User authentication / accounts (local-only bypass) | Firebase Auth is required; there is no unauthenticated access mode |

---

## 6. Key Data Contracts (Seed Definitions)

These are the foundational shapes all modules must agree on. Full Pydantic/TypeScript definitions live in `docs/contracts/`.

### WebSocket Connection
- Client connects to `/ws/pose` with a valid Firebase ID token (e.g., as a query parameter or initial handshake message)
- Backend verifies the token before accepting the connection; unauthenticated connections are rejected with `4001 Unauthorized`

### Pose Frame (WebSocket, client → server)
```json
{
  "timestamp": 1720000000.123,
  "landmarks": [
    { "id": 0, "x": 0.52, "y": 0.31, "z": -0.04, "visibility": 0.99 }
  ]
}
```

### Pose Analysis Result (WebSocket, server → client)
```json
{
  "timestamp": 1720000000.123,
  "exercise": "squat",
  "rep_count": 5,
  "form_score": 87,
  "corrections": ["Keep chest up", "Drive knees out"]
}
```

### Session Summary (REST, GET /api/v1/sessions/{id})
```json
{
  "session_id": "uuid",
  "user_id": "firebase_uid_string",
  "started_at": "2025-07-10T10:00:00",
  "ended_at": "2025-07-10T10:30:00",
  "exercise": "squat",
  "total_reps": 45,
  "sets": 3,
  "calories_burned": 142.5,
  "avg_form_score": 83,
  "form_score_trend": [78, 82, 89]
}
```

### User Profile (REST, GET/PUT /api/v1/user)
```json
{
  "firebase_uid": "uid_string",
  "display_name": "Alex",
  "weight_kg": 72.0,
  "created_at": "2025-07-01T00:00:00"
}
```

---

*This document is the single source of truth for project scope, conventions, and team boundaries. All spec work begins here.*
