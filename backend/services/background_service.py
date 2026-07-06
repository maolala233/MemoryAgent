"""Background task scheduling (best-effort, in-process)."""
from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

from ..utils.logger import info, warn


class BackgroundService:
    def __init__(self) -> None:
        self._tasks: Dict[str, threading.Timer] = {}
        self._running = False

    def schedule(self, name: str, interval_seconds: int,
                 func: Callable[[], None]) -> None:
        def runner() -> None:
            try:
                func()
            except Exception as exc:
                warn(f"Background task {name} failed", exc=exc)
            finally:
                if self._running:
                    timer = threading.Timer(interval_seconds, runner)
                    timer.daemon = True
                    self._tasks[name] = timer
                    timer.start()

        timer = threading.Timer(interval_seconds, runner)
        timer.daemon = True
        self._tasks[name] = timer
        timer.start()
        info(f"Scheduled background task '{name}' every {interval_seconds}s")

    def start_default(self) -> None:
        self._running = True
        from .memory_service import memory_service

        self.schedule("vault_rescan", 6 * 3600, memory_service.rescan_vault)

    def stop(self) -> None:
        self._running = False
        for timer in self._tasks.values():
            timer.cancel()
        self._tasks.clear()


background_service = BackgroundService()
