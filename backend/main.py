"""
Burn-Ex -- FastAPI application entry point.

Binds to host 0.0.0.0 and reads PORT from the environment (default 8000).
"""

import logging
import os
import socket
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.middleware.csp import CSPMiddleware
from backend.privacy.network_guard import install_network_guard
from backend.startup import validate_models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("burn_ex")

# Install network guard before anything else can open a socket
install_network_guard()

app = FastAPI(title="Burn-Ex")

# CORS -- allow all local-network origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

# CSP -- inject Content-Security-Policy on every response (TASK-12.1)
app.add_middleware(CSPMiddleware)


def _print_access_url() -> None:
    """
    TASK-15.2 — Print the host machine's LAN IP and HTTPS access URL.
    Called during the FastAPI startup event so it appears regardless of
    whether the server is launched via `python backend/main.py` or
    `uvicorn backend.main:app ...` directly.
    """
    port = int(os.environ.get("PORT", 8443))
    try:
        # Use UDP trick to find the outbound LAN interface without connecting
        import socket as _socket
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        try:
            lan_ip = _socket.gethostbyname(_socket.gethostname())
        except Exception:
            lan_ip = "YOUR-LAN-IP"

    border = "=" * 62
    logger.info(border)
    logger.info("  Burn-Ex is running!")
    logger.info("  Local:   https://localhost:%d", port)
    logger.info(
        "  Mobile:  https://%s:%d"
        "  <-- open this on your phone", lan_ip, port
    )
    logger.info(
        "  (Accept the certificate warning on first visit — self-signed cert)"
    )
    logger.info(border)


@app.on_event("startup")
def startup_event():
    """Validate models at startup; exit(1) if either fails (TASK-12.3)."""
    validate_models()
    _print_access_url()


# Routers
from backend.routers import ws_pose, sessions, progress, streaks, goals, user  # noqa: E402
app.include_router(ws_pose.router)
app.include_router(sessions.router)
app.include_router(progress.router)
app.include_router(streaks.router)
app.include_router(goals.router)
app.include_router(user.router)


@app.get("/health")
def health_check() -> dict:
    """Return a simple liveness response."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# TASK-15.1 — Serve the React build from FastAPI (single-port production mode)
# Must be mounted LAST so API routes take priority over the catch-all.
# ---------------------------------------------------------------------------
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    # Serve /assets/* and other static files
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="assets")

    # Catch-all: serve index.html for all non-API routes (React SPA routing)
    from fastapi.responses import FileResponse  # noqa: E402

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        """Serve index.html for all non-API paths (SPA client-side routing)."""
        index = _FRONTEND_DIST / "index.html"
        return FileResponse(str(index))
else:
    import warnings
    warnings.warn(
        f"Frontend dist not found at {_FRONTEND_DIST}. "
        "Run: cd frontend && npm run build",
        stacklevel=1,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8443))
    cert_dir = Path(__file__).resolve().parent.parent / "certs"
    cert_file = cert_dir / "local.crt"
    key_file  = cert_dir / "local.key"

    ssl_kwargs: dict = {}
    if cert_file.exists() and key_file.exists():
        ssl_kwargs = {
            "ssl_certfile": str(cert_file),
            "ssl_keyfile":  str(key_file),
        }
    else:
        print("[startup] WARNING: certs not found — running HTTP")
        print("[startup] Run: python scripts/gen_cert.py  to generate the cert")

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        **ssl_kwargs,
    )
