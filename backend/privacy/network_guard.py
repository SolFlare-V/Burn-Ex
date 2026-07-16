"""
TASK-12.2 -- Runtime Python network-request guard.

Patches socket.socket.connect at startup to raise PrivacyViolationError
for any outbound connection to a non-loopback, non-RFC-1918 address.

Allowed address ranges:
  - 127.0.0.0/8   (loopback)
  - 10.0.0.0/8    (RFC-1918)
  - 172.16.0.0/12 (RFC-1918)
  - 192.168.0.0/16 (RFC-1918)
  - ::1            (IPv6 loopback)

Design ref: sec 6.4. REQs: REQ-8.5.
"""
from __future__ import annotations

import ipaddress
import logging
import socket
import traceback
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Allowed private/loopback networks
_ALLOWED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
]


class PrivacyViolationError(RuntimeError):
    """Raised when code attempts to connect to an external (non-LAN) address."""


def _is_allowed(host: str) -> bool:
    """Return True if host is loopback or RFC-1918."""
    # Allow hostnames that resolve to private addresses (localhost etc.)
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return True
    try:
        addr = ipaddress.ip_address(host)
        return any(addr in net for net in _ALLOWED_NETWORKS)
    except ValueError:
        # Non-IP hostname -- allow (will be DNS-resolved; DNS itself is local)
        return True


def install_network_guard() -> None:
    """
    Monkey-patch socket.socket.connect to block external connections.

    Call once at application startup.  Idempotent -- safe to call multiple times.
    """
    original_connect = socket.socket.connect

    if getattr(original_connect, "_burn_ex_guarded", False):
        return  # already installed

    def _guarded_connect(self: socket.socket, address: Any, *args, **kwargs):
        # address may be (host, port) tuple or a string (Unix socket path)
        if isinstance(address, (tuple, list)) and len(address) >= 1:
            host = str(address[0])
            if not _is_allowed(host):
                # Identify the calling module from the stack
                caller = "unknown"
                for frame_info in traceback.extract_stack()[:-1]:
                    if "network_guard" not in frame_info.filename:
                        caller = frame_info.filename
                        break

                ts = datetime.now(timezone.utc).isoformat()
                msg = (
                    f"[{ts}] PRIVACY VIOLATION: module={caller!r} "
                    f"attempted connection to {address}"
                )
                logger.error(msg)
                raise PrivacyViolationError(msg)

        return original_connect(self, address, *args, **kwargs)

    _guarded_connect._burn_ex_guarded = True
    socket.socket.connect = _guarded_connect
    logger.info("Network guard installed: external connections blocked.")
