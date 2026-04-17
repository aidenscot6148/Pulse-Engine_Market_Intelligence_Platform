"""
storage/storage.py — Backward-compatible re-export shim.

All storage logic now lives in pulseengine.core/storage.py.
New code should import directly from pulseengine.core.
"""

from __future__ import annotations

from pulseengine.core.storage import *  # noqa: F401, F403
