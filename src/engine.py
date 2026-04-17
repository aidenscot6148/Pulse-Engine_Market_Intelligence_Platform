"""
src/engine.py — Backward-compatible re-export shim.

All logic now lives in pulseengine.core.app.
New code should import directly from pulseengine.core.
"""

from __future__ import annotations

from pulseengine.core.app import *  # noqa: F401, F403
