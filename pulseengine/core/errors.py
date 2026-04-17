"""src/errors.py — Shared exception types for the data pipeline."""

from __future__ import annotations


class PipelineError(Exception):
    """Base class for pipeline-related failures."""


class DataFetchError(PipelineError):
    """Raised when an external market/news fetch fails after retries."""


class StorageError(PipelineError):
    """Raised when stored snapshot data cannot be read safely."""


class SignalComputationError(PipelineError):
    """Raised when signal derivation cannot be completed."""
