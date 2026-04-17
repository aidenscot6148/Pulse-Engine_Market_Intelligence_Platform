"""
storage/storage.py — Backward-compatible re-export shim.

All storage logic now lives in pulseengine.core/storage.py.
New code should import directly from pulseengine.core.
"""

from __future__ import annotations

import sys

import pulseengine.core.storage as _core_storage

# Alias legacy module path to the core module object so monkeypatching and
# private helper imports keep working exactly as before.
sys.modules[__name__] = _core_storage
