# Test Suite Maintenance Guide

The test suite is intentionally small. Its job is to be a **safety net, not a straitjacket** —
catch crashes and broken invariants, not enforce exact output shapes.

---

## File Layout

| File | Purpose |
|---|---|
| `conftest.py` | Shared fixtures (price series, DataFrames, articles, signal dicts, mocks) |
| `test_core.py` | 8 sanity / invariant tests for pure functions |
| `test_pipeline.py` | 6 smoke tests for end-to-end pipelines |

**Total: 14 tests.** Keep it close to this number. If a new test enforces an exact value or
a specific dict key, it probably does not belong here.

---

## What each test file covers

### `test_core.py`
Pure functions only. Each test checks either:
- The function runs without crashing, or
- A hard mathematical invariant (RSI ∈ [0, 100], compound ∈ [-1, 1], score ∈ [-10, 10])

These tests survive weight tuning, threshold changes, and key renames as long as the
invariant itself holds. Do not add tests here that assert exact float values.

### `test_pipeline.py`
Smoke tests for `analyse_asset()` and `run_full_scan()`. All network calls are mocked
via conftest fixtures. Each test checks only:
- The pipeline completes without raising, and
- The result contains a `signal` key with a score in range

Do not add key-structure assertions here. If `analyse_asset` gains new return keys,
the existing tests should keep passing without modification.

---

## Import paths

All test files use the new package-based imports:

| Import | Module |
|---|---|
| `from app.analysis import X` | Re-export shim in `app/analysis.py` |
| `from storage.storage import X` | Storage module in `storage/storage.py` |
| `from src.price import X` | Price logic in `src/price.py` |
| `from src.signals import X` | Signal logic in `src/signals.py` |
| `from src.sentiment import X` | Sentiment logic in `src/sentiment.py` |
| `from src.news import X` | News logic in `src/news.py` |
| `from src.engine import X` | Engine orchestration in `src/engine.py` |

`conftest.py` imports `storage.storage as storage` so that `monkeypatch.setattr` targets the correct module object.

Network calls are mocked at the point of use in `src/engine.py`:
- `"src.engine.fetch_price_history"`
- `"src.engine.fetch_news_articles"`
- `"src.engine.analyse_market_context"`

---

## When to update tests

| Change | Action required |
|---|---|
| New key added to `analyse_asset()` result | Nothing — tests use `.get()` and check presence only |
| `analyse_asset()` top-level keys renamed | Update `test_pipeline.py::test_analyse_asset_has_signal_in_range` |
| RSI/ROC formula replaced | `test_core.py` invariant tests will catch a broken range; direction tests catch sign flip |
| Signal score clamping removed | `test_signal_score_in_range` will fail — intentional |
| Functions moved between `src/` modules | Update the `"src.engine.*"` patch strings in `conftest.py` if the moved function is imported by `src/engine.py` |
| New asset class added to `config/settings.py` | No test changes needed — pipeline tests cover all categories via `run_full_scan` |

---

## Adding a new test

Before adding a test, ask:
- **Does it test a crash?** Good.
- **Does it test a range or type invariant?** Good.
- **Does it assert an exact key name or float value?** Probably bad — it will break on the next refactor.
- **Would deleting it make refactoring easier?** Then it should not exist.

---

## Running the tests

```bash
# Standard run
pytest

# Single file
pytest tests/test_core.py -v

# With full traceback
pytest --tb=long
```
