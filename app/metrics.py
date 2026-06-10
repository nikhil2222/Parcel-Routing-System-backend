from collections import Counter
from threading import Lock


class MetricsStore:
    def __init__(self):
        self._lock = Lock()
        self._counters = Counter()

    def incr(self, key: str, amount: int = 1):
        with self._lock:
            self._counters[key] += amount

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counters)