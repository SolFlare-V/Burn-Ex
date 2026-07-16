#!/usr/bin/env python3
"""
TASK-12.4 -- Dependency audit script.

Checks all installed Python packages and frontend npm packages against a
curated deny-list in config/dependency_deny_list.yaml. Prints a warning
for any flagged package found.

Usage:
    python scripts/audit_dependencies.py

Design ref: sec 6.4. REQs: REQ-10.4.
"""
from __future__ import annotations

import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DENY_LIST_PATH = ROOT / "config" / "dependency_deny_list.yaml"
FRONTEND_DIR = ROOT / "frontend"
PACKAGE_JSON = FRONTEND_DIR / "package.json"


def load_deny_list() -> dict:
    with open(DENY_LIST_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_installed_python_packages() -> set[str]:
    """Return set of installed Python package names (normalised to lowercase)."""
    return {dist.metadata["Name"].lower() for dist in importlib.metadata.distributions()}


def get_installed_npm_packages() -> set[str]:
    """Return set of npm package names from package.json dependencies."""
    if not PACKAGE_JSON.exists():
        return set()
    with open(PACKAGE_JSON, "r", encoding="utf-8") as f:
        pkg = json.load(f)
    deps = {}
    deps.update(pkg.get("dependencies", {}))
    deps.update(pkg.get("devDependencies", {}))
    return set(deps.keys())


def audit() -> int:
    """Run the audit. Returns number of violations found."""
    print("Burn-Ex Dependency Audit")
    print("=" * 50)

    try:
        deny_list = load_deny_list()
    except FileNotFoundError:
        print(f"ERROR: Deny-list not found at {DENY_LIST_PATH}")
        return 1

    warnings = []

    # --- Python packages ---
    print("\nChecking Python packages...")
    installed_py = get_installed_python_packages()
    py_entries = deny_list.get("python") or []
    for entry in py_entries:
        name = entry["name"].lower()
        reason = entry.get("reason", "")
        if name in installed_py:
            msg = f"  WARNING [Python] '{entry['name']}' -- {reason}"
            print(msg)
            warnings.append(msg)
    print(f"  {len(installed_py)} packages checked, {sum(1 for e in py_entries if e['name'].lower() in installed_py)} flagged.")

    # --- npm packages ---
    print("\nChecking npm packages...")
    installed_npm = get_installed_npm_packages()
    if not installed_npm:
        print("  (No package.json found or no dependencies listed)")
    npm_entries = deny_list.get("npm") or []
    for entry in npm_entries:
        name = entry["name"]
        reason = entry.get("reason", "")
        if name in installed_npm:
            msg = f"  WARNING [npm] '{name}' -- {reason}"
            print(msg)
            warnings.append(msg)
    if installed_npm:
        print(f"  {len(installed_npm)} packages checked, {sum(1 for e in npm_entries if e['name'] in installed_npm)} flagged.")

    # --- Summary ---
    print("\n" + "=" * 50)
    if warnings:
        print(f"AUDIT RESULT: {len(warnings)} violation(s) found:")
        for w in warnings:
            print(w)
        return len(warnings)
    else:
        print("AUDIT RESULT: No flagged dependencies found. All clear.")
        return 0


if __name__ == "__main__":
    violations = audit()
    # Exit 0 regardless -- violations are warnings, not hard failures.
    # The script is informational; CI can choose to fail on non-zero if desired.
    sys.exit(0)
