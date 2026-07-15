"""Structured logging and lightweight performance monitoring."""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Dict, Optional

LOG = logging.getLogger("memory_agent")


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )


def info(message: str, context: Optional[Dict[str, object]] = None) -> None:
    LOG.info(_format(message, context))


def warn(message: str, context: Optional[Dict[str, object]] = None) -> None:
    LOG.warning(_format(message, context))


def error(message: str, exc: Optional[Exception] = None,
          context: Optional[Dict[str, object]] = None) -> None:
    LOG.error(_format(message, context), exc_info=exc)


def debug(message: str, context: Optional[Dict[str, object]] = None) -> None:
    LOG.debug(_format(message, context))


def _format(message: str, context: Optional[Dict[str, object]]) -> str:
    if not context:
        return message
    kv = " ".join(f"{k}={v}" for k, v in context.items())
    return f"{message} | {kv}"


class PerformanceMonitor:
    """In-memory performance metrics."""

    def __init__(self) -> None:
        self._requests: Dict[str, list] = {}
        self._searches: Dict[str, list] = {}

    @contextmanager
    def track(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = (time.perf_counter() - start) * 1000.0
            self._requests.setdefault(name, []).append(elapsed)
            if len(self._requests[name]) > 200:
                self._requests[name] = self._requests[name][-200:]

    def track_search(self, query: str, duration_ms: float, result_count: int) -> None:
        self._searches.setdefault(query, []).append((duration_ms, result_count))

    def get_metrics(self) -> Dict[str, object]:
        out: Dict[str, object] = {}
        for name, samples in self._requests.items():
            if not samples:
                continue
            out[name] = {
                "count": len(samples),
                "avg_ms": round(sum(samples) / len(samples), 2),
                "max_ms": round(max(samples), 2),
                "min_ms": round(min(samples), 2),
            }
        return out


perf = PerformanceMonitor()
