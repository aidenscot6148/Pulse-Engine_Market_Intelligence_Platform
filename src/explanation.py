"""
src/explanation.py — Backward-compatible re-export shim.

All logic now lives in pulseengine.core.explanation.
New code should import directly from pulseengine.core.
"""

from __future__ import annotations

import sys

import pulseengine.core.explanation as _core_explanation

# Alias legacy module path to the core module object so monkeypatching and
# private helper imports keep working exactly as before.
sys.modules[__name__] = _core_explanation
