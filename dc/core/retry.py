"""Small retry ladder with durable attempt records."""
from __future__ import annotations

import time
from typing import Any, Callable


def retry_ladder(operation: Callable[[int], Any], attempts: int = 2, *, retryable: Callable[[Exception], bool] | None = None, backoff_s: float = .05, on_attempt: Callable[[dict[str, Any]], None] | None = None) -> Any:
    attempts = max(1, int(attempts))
    retryable = retryable or (lambda exc: True)
    errors = []
    for attempt in range(1, attempts + 1):
        started = time.perf_counter()
        try:
            result = operation(attempt)
            row = {"attempt": attempt, "status": "passed", "elapsed_s": round(time.perf_counter() - started, 6)}
            if on_attempt:
                on_attempt(row)
            return result
        except Exception as exc:
            row = {"attempt": attempt, "status": "failed", "elapsed_s": round(time.perf_counter() - started, 6), "error": str(exc)}
            errors.append(row)
            if on_attempt:
                on_attempt(row)
            if attempt >= attempts or not retryable(exc):
                raise
            time.sleep(backoff_s * attempt)
    raise RuntimeError(errors)
