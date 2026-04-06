"""
src/ — PulseEngine core modules.

Module map:
  price       — Yahoo Finance fetching, price metrics, momentum indicators
  sentiment   — VADER + financial-lexicon sentiment scoring
  news        — RSS fetching, deduplication, clustering
  signals     — news-asset correlation, event detection, composite signal score
  context     — sector peer and market benchmark comparison
  explanation — human-readable narrative generation
  engine      — orchestration: analyse_asset, run_full_scan, fetch_all_metrics_parallel
"""
