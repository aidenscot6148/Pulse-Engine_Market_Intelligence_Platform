"""
src/price.py — Backward-compatible re-export shim.

All logic now lives in pulseengine.core.price.
New code should import directly from pulseengine.core.
"""

from __future__ import annotations

import sys

import pulseengine.core.price as _core_price

# Alias legacy module path to the core module object so monkeypatching and
# private helper imports keep working exactly as before.
sys.modules[__name__] = _core_price
