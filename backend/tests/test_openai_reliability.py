"""OpenAI reliability helpers: circuit breaker and failure recording."""

from __future__ import annotations

import time

from app.ai.reasoning import reasoning_provider as rp


def test_circuit_opens_after_threshold_failures() -> None:
    model = "unit-test-model-circuit"
    rp._CIRCUIT_STATE.pop(model, None)
    assert not rp._is_circuit_open(model)
    for _ in range(3):
        rp._record_circuit_failure(model, failure_threshold=3, reset_seconds=60)
    assert rp._is_circuit_open(model)
    rp._record_circuit_success(model)
    assert not rp._is_circuit_open(model)


def test_circuit_recovers_after_reset_window() -> None:
    model = "unit-test-model-reset"
    rp._CIRCUIT_STATE.pop(model, None)
    rp._record_circuit_failure(model, failure_threshold=1, reset_seconds=1)
    assert rp._is_circuit_open(model)
    # Force expiry without sleeping the full window.
    rp._CIRCUIT_STATE[model]["opened_until"] = time.time() - 1
    assert not rp._is_circuit_open(model)
