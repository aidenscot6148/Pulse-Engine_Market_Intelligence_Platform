"""
src/signals.py — Backward-compatible re-export shim.

All logic now lives in pulseengine.core.signals.
New code should import directly from pulseengine.core.
"""

from __future__ import annotations

from pulseengine.core.signals import *  # noqa: F401, F403
