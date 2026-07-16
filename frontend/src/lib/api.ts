/**
 * API base URL helpers.
 *
 * Production (Phase 15+): FastAPI serves the React build on the same
 * host:port (8443 HTTPS), so all requests use relative URLs — no port
 * mismatch, no cross-origin issue, single cert to trust.
 *
 * Dev (Vite on :5173): proxy to FastAPI on :8443 via the same hostname.
 * Both servers use the same self-signed cert so the phone only needs to
 * accept one warning (for :8443) — Vite proxies API calls through itself.
 *
 * For the phone test, use https://<LAN-IP>:8443 directly (FastAPI serves
 * the built frontend). One URL, one cert, no cross-origin issues.
 */

const isDev = import.meta.env.DEV

// In dev: point directly at the FastAPI HTTPS server on 8443
// In prod: use relative URLs — same origin as the serving FastAPI instance
export const API_BASE = isDev
  ? `https://${window.location.hostname}:8443`
  : ''

// WebSocket: wss:// in all cases (backend is always on HTTPS/WSS)
// In dev:  wss://<hostname>:8443  (FastAPI backend)
// In prod: wss://<hostname>       (same port as the page, served by FastAPI)
export const WS_BASE = isDev
  ? `wss://${window.location.hostname}:8443`
  : `wss://${window.location.host}`
