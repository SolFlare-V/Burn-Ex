# Burn-Ex — Project Steering Document

## 1. Project Overview

Burn-Ex is an offline, AI-powered fitness analytics system that provides real-time posture correction, rep counting, calorie estimation, and progress tracking — entirely on the local machine or local network. No cloud, no external APIs, no subscriptions.

Users access Burn-Ex through a browser (laptop or mobile on the same Wi-Fi), point their camera at themselves during a workout, and receive immediate feedback on exercise form, rep counts, and estimated calories burned. Session history, form score trends, streaks, and goals are persisted locally in SQLite.

The system is designed for privacy-conscious users who want accurate fitness analytics without sending any data outside their home network.

---

## 2. Core Principles

### Privacy-First
- All data stays on the user's device or local network. No telemetry, no analytics, no external requests.
- Camera frames are processed in-memory and never written to disk unless explicitly requested by the user.
- No user accounts, no cloud sync, no third-party authentication.

### Offline-First
- The system must function with zero internet connectivity after initial setup.
- All ML models (MediaPipe, scikit-learn Random Forest) are bundled locally.
- The frontend is served from the local FastAPI backend — no CDN dependencies at runtime.

### Accuracy Over Simplicity
- Calorie estimation uses MET (Metabolic Equivalent of Task) equations with exercise-specific coefficients derived from a self-generated dataset. Simple heuristics are not acceptable substitutes.
- Posture correction feedback must be exercise-specific (squat form feedback ≠ push-up form feedback). Generic "bad form" alerts are insufficient.
- Rep counting must be robust to partial reps and camera angle variation.

### Structured, Spec-Driven Development
- All features begin as Kiro specs (requirements → design → tasks) before any code is written.
- Data contracts (API schemas, DB schema, landmark formats) are defined before implementation starts.
- Frontend visual polish is handled separately; backend and CV modules must expose clean, stable interfaces.

---

## 3. Tech Stack & Conventions

### Computer Vision
- **Library:** MediaPipe Pose (landmark detection, 33 keypoints)
- **Input:** Webcam stream via browser `getUserMedia`, frames sent to backend over WebSocket or HTTP
- **Output:** Normalized landmark coordinates (x, y, z, visibility) per frame

### Machine Learning
- **Framework:** scikit-learn
- **Model:** Random Forest classifier for exercise type classification
- **Training data:** Self-generated dataset from MediaPipe landmark sequences
- **Inference:** Runs entirely on-device, no external model APIs

### Calorie Estimation
- **Method:** MET equations — `Calories = MET × weight_kg × duration_hours`
- **MET values:** Curated per exercise type from published exercise science literature
- **Inputs:** User-provided weight, detected exercise type, session duration, rep count

### Backend
- **Framework:** FastAPI (Python)
- **Responsibilities:** CV pipeline coordination, ML inference, calorie calculation, session management, REST + WebSocket APIs
- **Runs on:** Local machine, bound to `0.0.0.0` for local network access

### Database
- **Engine:** SQLite (single file, no server required)
- **ORM:** SQLAlchemy
- **Schema ownership:** Kiro — all migrations and schema changes go through Kiro specs

### Frontend
- **Framework:** React
- **Styling:** Tailwind CSS
- **Component source:** 21st.dev MCP (via Antigravity)
- **Design system:** UI/UX Pro Max skill (via Antigravity)
- **Data layer:** Consumes REST and WebSocket endpoints defined by Kiro
- **Served by:** FastAPI static file serving — no separate Node server in production

### Local Network Access
- FastAPI binds to `0.0.0.0:8000` (or configurable port)
- Mobile browsers on the same Wi-Fi connect via local IP (e.g., `192.168.x.x:8000`)
- No NAT traversal, no tunneling, no ngrok — strictly local

### Naming & Code Conventions
- Python: `snake_case` for variables and functions, `PascalCase` for classes
- React components: `PascalCase` filenames and exports
- API routes: `/api/v1/{resource}` prefix for all REST endpoints
- WebSocket endpoint: `/ws/pose` for real-time landmark streaming
- All API request/response shapes documented as Pydantic models (Python) and TypeScript interfaces (frontend)
- No `any` types in TypeScript

---

## 4. Team & Tool Responsibilities

### Kiro (this agent)
- Writes all Kiro specs: requirements, design documents, implementation task lists
- Owns architecture decisions and data contracts
- Implements: CV pipeline, ML training/inference, calorie logic, FastAPI backend, SQLite schema, WebSocket server
- For frontend work: defines component structure, props/state contracts, API integration logic — does NOT own visual polish, color choices, or animation
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
- Real-time pose landmark detection via MediaPipe
- Exercise classification (squats, push-ups, lunges, etc.) via Random Forest
- Exercise-specific posture correction feedback (joint angles, alignment cues)
- Rep counting per set with set tracking
- Calorie estimation per session using MET equations
- Session history: calories over time, form score trends, exercise breakdown
- Streaks and daily/weekly goals (light gamification)
- Browser-based access from laptop and mobile on same Wi-Fi
- User profile: weight input (required for calorie calculation), optional name

### Out of Scope
The following are explicitly excluded from Burn-Ex:

| Excluded Feature | Reason |
|---|---|
| Cloud sync or remote storage | Privacy-first; all data stays local |
| External AI APIs (OpenAI, Google Vision, etc.) | Offline-first; no external dependencies |
| Native mobile app (iOS/Android) | Browser-based local access is sufficient |
| User authentication / accounts | Single-user local system; no auth needed |
| Social features (sharing, leaderboards) | Out of scope for privacy-preserving design |
| Video recording or playback | Frames processed in-memory only |
| Paid tiers or licensing | Open, self-hosted tool |
| Wearable device integration | No hardware dependencies beyond webcam |
| Nutrition tracking or diet planning | Out of scope; calorie burn only |
| Multi-user simultaneous sessions | Single active session per server instance |

---

## 6. Key Data Contracts (Seed Definitions)

These are the foundational shapes all modules must agree on. Full Pydantic/TypeScript definitions live in `docs/contracts/`.

### Pose Frame (WebSocket, server → client)
```json
{
  "timestamp": 1720000000.123,
  "landmarks": [
    { "id": 0, "x": 0.52, "y": 0.31, "z": -0.04, "visibility": 0.99 }
  ],
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
  "name": "Alex",
  "weight_kg": 72.0,
  "created_at": "2025-07-01T00:00:00"
}
```

---

*This document is the single source of truth for project scope, conventions, and team boundaries. All spec work begins here.*
