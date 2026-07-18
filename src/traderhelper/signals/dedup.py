from __future__ import annotations


class DedupState:
    def __init__(self) -> None:
        self._fingerprints: dict[str, str] = {}
        self._armed: dict[str, bool] = {}

    def should_emit(self, key: str, fingerprint: str) -> bool:
        previous = self._fingerprints.get(key)
        if previous == fingerprint:
            return False
        self._fingerprints[key] = fingerprint
        return True

    def is_armed(self, key: str, *, default: bool = True) -> bool:
        return self._armed.get(key, default)

    def set_armed(self, key: str, armed: bool) -> None:
        self._armed[key] = armed

    def clear(self, key: str) -> None:
        self._fingerprints.pop(key, None)
        self._armed.pop(key, None)
