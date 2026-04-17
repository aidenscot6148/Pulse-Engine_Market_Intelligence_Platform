"""
src/explanation.py — Backward-compatible re-export shim.

All logic now lives in pulseengine.core.explanation.
New code should import directly from pulseengine.core.
"""

from __future__ import annotations

from pulseengine.core.explanation import *  # noqa: F401, F403
