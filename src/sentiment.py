"""
src/sentiment.py — Backward-compatible re-export shim.

All logic now lives in pulseengine.core.sentiment.
New code should import directly from pulseengine.core.
"""

from __future__ import annotations

import sys

import pulseengine.core.sentiment as _core_sentiment

# Alias legacy module path to the core module object so monkeypatching and
# private helper imports keep working exactly as before.
sys.modules[__name__] = _core_sentiment
