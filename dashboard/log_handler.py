import logging
import asyncio
from collections import deque
from datetime import datetime

MAX_LOG_ENTRIES = 1000

_log_buffer: deque = deque(maxlen=MAX_LOG_ENTRIES)
_sse_queues: list[asyncio.Queue] = []

LEVEL_COLORS = {
    "DEBUG": "text-secondary",
    "INFO": "text-info",
    "WARNING": "text-warning",
    "ERROR": "text-danger",
    "CRITICAL": "text-danger fw-bold",
}


class DashboardLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        try:
            entry = {
                "time": datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                "level": record.levelname,
                "logger": record.name,
                "message": self.format(record),
                "color": LEVEL_COLORS.get(record.levelname, "text-light"),
            }
            _log_buffer.append(entry)
            for q in list(_sse_queues):
                try:
                    q.put_nowait(entry)
                except asyncio.QueueFull:
                    pass
        except Exception:
            pass


def get_recent_logs(limit: int = 200) -> list[dict]:
    entries = list(_log_buffer)
    return entries[-limit:]


def register_sse_queue(q: asyncio.Queue):
    _sse_queues.append(q)


def unregister_sse_queue(q: asyncio.Queue):
    if q in _sse_queues:
        _sse_queues.remove(q)


def setup_log_capture():
    handler = DashboardLogHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S"))
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
