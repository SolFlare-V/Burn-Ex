# Burn-Ex

An offline, AI-powered fitness analytics system providing real-time posture correction, rep counting, calorie estimation, and progress tracking — entirely on your local machine or local network. No cloud, no external APIs, no subscriptions.

---

## Project Overview

Burn-Ex runs as a local FastAPI server. You access it from any browser on the same Wi-Fi — laptop or mobile — point your camera at yourself during a workout, and get immediate feedback on exercise form, rep counts, and estimated calories burned.

**Supported exercises:** squat, push-up, lunge, bicep curl, shoulder press, plank

**Key features:**
- Real-time pose landmark detection via MediaPipe (33 keypoints)
- Exercise classification via a local Random Forest classifier
- Exercise-specific posture correction cues (joint-angle based)
- Rep counting with automatic set detection
- MET-based calorie estimation
- Session history, form score trends, streaks, and daily/weekly goals
- All data stored locally in SQLite — nothing leaves your network

---

## Project Structure

```
burn-ex/
├── backend/          # FastAPI application — CV pipeline, ML inference, REST + WebSocket APIs
├── frontend/         # React + Tailwind frontend (served by FastAPI in production)
├── models/           # Trained ML models and TFLite files (exercise_classifier.pkl, efficientdet_lite0.tflite)
├── data/             # SQLite database, raw landmark CSVs, training scripts
├── docs/
│   └── contracts/    # API schemas, WebSocket message formats, Pydantic/TypeScript contracts
├── config/           # YAML config files (form thresholds, rep phases, MET values)
└── README.md
```

---

## Prerequisites

- **Python 3.10+** — backend and ML pipeline
- **Node.js 18+** and **npm** — frontend build toolchain
- **pip** — Python package management
- A webcam (built-in or USB)
- A browser that supports `getUserMedia` and WebSockets (Chrome 90+, Firefox 88+, Safari 15+)

> **No internet connection required at runtime.** All models and assets are served locally.

---

## Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd burn-ex
```

### 2. Set up the Python environment

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -r backend/requirements.txt
```

### 3. Initialise the database

```bash
python backend/db_init.py
```

This creates `data/burnex.db` with all required tables.

### 4. Download bundled ML models

> The `models/` directory must contain `efficientdet_lite0.tflite` and `exercise_classifier.pkl` before the server starts. See `docs/contracts/model-setup.md` (coming in a later task) for download/training instructions.

### 5. Build the frontend

```bash
cd frontend
npm install
npm run build
cd ..
```

---

## Running the Server

```bash
# Generate cert first (one-time)
python scripts/gen_cert.py

# Start HTTPS server on port 8443
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8443 \
  --ssl-certfile certs/local.crt --ssl-keyfile certs/local.key
```

Or using `python backend/main.py` directly (reads cert paths automatically):
```bash
python backend/main.py
```

The server binds to `0.0.0.0:8443` over HTTPS, making it reachable from any device on the local network.

> **Why HTTPS?** `getUserMedia` (camera access) is blocked by modern browsers on plain HTTP over a LAN IP. HTTPS with a self-signed cert is the correct solution for offline-first local tools. See §6.2 of `docs/design.md` for full details.

---

## Accessing from Mobile

> **HTTPS is required for camera access on mobile browsers.** Modern browsers only allow `getUserMedia` (camera) in a secure context (`https://` or `http://localhost`). A plain `http://<LAN-IP>` address is blocked by browser policy — this is not a bug.

### One-time setup (takes 30 seconds)

**1. Generate the self-signed certificate** (only needed once):
```bash
python scripts/gen_cert.py
```
This creates `certs/local.crt` and `certs/local.key` with your LAN IP included as a Subject Alternative Name.

**2. Start the backend with HTTPS:**
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8443 \
  --ssl-certfile certs/local.crt --ssl-keyfile certs/local.key
```

**3. Open on your phone:**

Open `https://<LAN-IP>:8443` (e.g. `https://10.11.92.234:8443`) in your phone's browser.

**4. Accept the security warning (one-time):**

Because the certificate is self-signed, your browser will show **"Your connection is not private"** or **"Not Secure"**. This is expected. Click:
- **Chrome:** "Advanced" → "Proceed to 10.x.x.x (unsafe)"
- **Firefox:** "Advanced" → "Accept the Risk and Continue"
- **Safari:** "Show Details" → "visit this website"

You only need to do this once per device. After accepting, the browser remembers the exception.

**5. Grant camera permission** when prompted by the browser.

> **Why self-signed?** A proper CA-signed certificate requires a registered domain name — not possible for a local IP. The self-signed approach is standard practice for local development and offline-first tools.

### Finding your LAN IP

```bash
# Windows
ipconfig | findstr "IPv4"

# macOS / Linux
ifconfig | grep "inet "
```

Or check the startup log — the server prints the LAN URL on start.

---

## Configuration

Runtime behaviour is controlled by YAML files in `config/`:

| File | Purpose |
|---|---|
| `config/form_thresholds.yaml` | Joint angle thresholds and corrective cues per exercise |
| `config/rep_phases.yaml` | Eccentric/concentric phase thresholds for rep counting |
| `config/met_values.yaml` | MET coefficients for calorie estimation |

Environment variables:

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8443` | Port the server listens on (HTTPS) |
| `DATABASE_URL` | `sqlite:///data/burnex.db` | SQLite database path |

---

## Development

```bash
# Run backend in reload mode (HTTPS)
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8443 \
  --ssl-certfile certs/local.crt --ssl-keyfile certs/local.key --reload

# Run frontend dev server (HTTPS, reads certs/local.crt automatically)
cd frontend && npm run dev
# Opens https://localhost:5173
```

### Running tests

```bash
# Backend tests
pytest backend/tests/

# Frontend tests
cd frontend && npm test
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python) |
| Database | SQLite via SQLAlchemy |
| Computer Vision | MediaPipe Pose |
| ML Classification | scikit-learn Random Forest |
| Frontend | React + Vite + TypeScript |
| Styling | Tailwind CSS |
| Real-time | WebSocket (`/ws/pose`) |

---

## Privacy

- All processing happens on your machine — no frames, landmarks, or session data are ever sent outside the local network.
- No user accounts, no telemetry, no third-party analytics.
- Camera frames are processed in memory and never written to disk.
