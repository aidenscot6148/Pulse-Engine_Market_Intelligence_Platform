"""
src/engine.py — Backward-compatible re-export shim.

All logic now lives in pulseengine.core.app.
New code should import directly from pulseengine.core.
"""

from __future__ import annotations

import sys

import pulseengine.core.app as _core_app

# Alias legacy module path to the core module object so monkeypatching and
# private helper imports keep working exactly as before.
sys.modules[__name__] = _core_app
