from __future__ import annotations

from traderhelper.signals.dedup import DedupState


def test_should_emit_deduplicates_fingerprint() -> None:
    state = DedupState()
    assert state.should_emit("macd", "bullish:1") is True
    assert state.should_emit("macd", "bullish:1") is False
    assert state.should_emit("macd", "bearish:2") is True


def test_armed_flags() -> None:
    state = DedupState()
    assert state.is_armed("price") is True
    state.set_armed("price", False)
    assert state.is_armed("price") is False
    state.clear("price")
    assert state.is_armed("price") is True
