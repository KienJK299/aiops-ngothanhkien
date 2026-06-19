"""Structured JSON logger for the closed-loop orchestrator."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


class JsonLogger:
    def __init__(self, name: str):
        self._name = name

    def _emit(self, level: str, event_type: str, **kwargs: Any) -> None:
        kwargs.setdefault("service", "")
        kwargs.setdefault("action", "")
        kwargs.setdefault("result", "")
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "logger": self._name,
            "event_type": event_type,
            **kwargs,
        }
        print(json.dumps(record), flush=True)

    def info(self, event_type: str, **kwargs: Any) -> None:
        self._emit("INFO", event_type, **kwargs)

    def warning(self, event_type: str, **kwargs: Any) -> None:
        self._emit("WARNING", event_type, **kwargs)

    def error(self, event_type: str, **kwargs: Any) -> None:
        self._emit("ERROR", event_type, **kwargs)
