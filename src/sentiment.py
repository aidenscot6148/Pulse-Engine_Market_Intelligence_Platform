"""
src/sentiment.py — Backward-compatible re-export shim.

All logic now lives in pulseengine.core.sentiment.
New code should import directly from pulseengine.core.
"""

from __future__ import annotations

from pulseengine.core.sentiment import *  # noqa: F401, F403
