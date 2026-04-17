"""
src/news.py — Backward-compatible re-export shim.

All logic now lives in pulseengine.core.news.
New code should import directly from pulseengine.core.
"""

from __future__ import annotations

from pulseengine.core.news import *  # noqa: F401, F403
