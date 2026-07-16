"""
Shared pytest fixtures for the Burn-Ex test suite.
"""
import sys
import os

# Ensure the project root is on sys.path so all backend imports resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# person_detector now uses POSIX-style paths (forward slashes) which MediaPipe
# handles correctly on Windows regardless of the process's working directory.
# No patching needed — the real detector loads cleanly from any cwd.
from backend.main import app  # noqa: E402 — triggers detector init at import time
