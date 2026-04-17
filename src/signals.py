"""
src/signals.py — Backward-compatible re-export shim.

All logic now lives in pulseengine.core.signals.
New code should import directly from pulseengine.core.
"""

from __future__ import annotations

import sys

import pulseengine.core.signals as _core_signals

# Alias legacy module path to the core module object so monkeypatching and
# private helper imports keep working exactly as before.
sys.modules[__name__] = _core_signals
