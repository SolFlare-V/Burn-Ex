"""
TASK-12.1 -- CSP header middleware.

Injects Content-Security-Policy on every response.
Matches the policy defined in design.md sec 6.4:

  default-src 'self';
  connect-src 'self' ws://localhost:* ws://192.168.*;
  script-src  'self';
  img-src     'self' data:;
  style-src   'self' 'unsafe-inline';

Design ref: sec 6.4. REQs: REQ-8.4.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

CSP_POLICY = (
    "default-src 'self'; "
    "connect-src 'self' ws://localhost:* wss://localhost:* ws://192.168.* wss://192.168.* wss://10.*; "
    "script-src 'self'; "
    "img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline';"
)


class CSPMiddleware(BaseHTTPMiddleware):
    """Inject Content-Security-Policy header on every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        response.headers["Content-Security-Policy"] = CSP_POLICY
        return response
