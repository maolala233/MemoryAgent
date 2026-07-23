"""Structured logging and lightweight performance monitoring."""
from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, Optional

LOG = logging.getLogger("memory_agent")

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
# 同一进程内,清理操作至少间隔 60 秒,避免每次写日志都扫描目录
_CLEANUP_INTERVAL_SECONDS = 60


def setup_logging(
    level: str = "INFO",
    log_dir: Optional[os.PathLike] = None,
    max_bytes: int = 50 * 1024 * 1024,
    retention_days: int = 7,
    backup_count: int = 20,
) -> None:
    """Initialize logging.

    - 日志会同时输出到 stderr 和(可选的)按大小滚动的文件中。
    - 当文件超过 ``max_bytes`` 时会自动滚动,文件名形如 ``memory_agent.log.1``。
    - 启动时以及每次滚动后,会清理 ``log_dir`` 下超过 ``retention_days`` 天的旧日志。
    - 如果 ``log_dir`` 不存在则会自动创建。
    """
    formatter = logging.Formatter(_LOG_FORMAT)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    # 清理已存在的 handler,避免在 reload / 多次启动场景下重复输出
    for handler in list(root.handlers):
        root.removeHandler(handler)

    # 控制台 handler(始终保留,方便容器/前台观察)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    # 文件 handler(可选):按大小滚动 + 启动/滚动时按时间清理
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        file_handler = _SizeAndTimeRotatingFileHandler(
            filename=log_path / "memory_agent.log",
            max_bytes=max_bytes,
            backup_count=backup_count,
            retention_days=retention_days,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
        # 启动时主动清理一次过期日志
        file_handler.cleanup_expired()

    # 抑制 uvicorn 自带 handler,避免 access log 等重复输出到 stderr
    for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(noisy)
        logger.handlers = [h for h in logger.handlers if not isinstance(h, logging.StreamHandler)] or [
            console_handler
        ]
        logger.propagate = False


class _SizeAndTimeRotatingFileHandler(RotatingFileHandler):
    """在 ``RotatingFileHandler`` 的基础上叠加"按 mtime 删除过期备份"的能力。"""

    def __init__(
        self,
        filename: os.PathLike,
        max_bytes: int,
        backup_count: int,
        retention_days: int,
        encoding: Optional[str] = None,
    ) -> None:
        super().__init__(
            filename=str(filename),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding=encoding or "utf-8",
        )
        self.retention_days = max(0, int(retention_days))
        self._base_path = Path(self.baseFilename)
        self._last_cleanup_ts = 0.0

    def cleanup_expired(self) -> None:
        """删除 ``log_dir`` 下 mtime 早于保留期限的日志文件。"""
        if self.retention_days <= 0:
            return
        cutoff = time.time() - self.retention_days * 86400
        # 匹配 memory_agent.log、memory_agent.log.1、memory_agent.log.2 ...
        pattern = self._base_path.name + "*"
        for log_file in self._base_path.parent.glob(pattern):
            try:
                if log_file.is_file() and log_file.stat().st_mtime < cutoff:
                    log_file.unlink()
            except OSError:
                # 删除失败不影响后续日志写入
                pass
        self._last_cleanup_ts = time.time()

    def _maybe_cleanup(self) -> None:
        now = time.time()
        # 节流:避免每次滚动都做目录扫描
        if now - self._last_cleanup_ts >= _CLEANUP_INTERVAL_SECONDS:
            self.cleanup_expired()

    def doRollover(self) -> None:  # noqa: N802 (stdlib API)
        super().doRollover()
        self._maybe_cleanup()

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        try:
            super().emit(record)
        finally:
            # 每次写入也尝试触发清理(内部已节流)
            self._maybe_cleanup()


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
