"""
MapSplat - Log Utilities

Pure-Python helpers for formatting and writing export log lines.
No QGIS or Qt dependencies — importable in unit tests without a live QGIS instance.
"""

__version__ = "0.6.16"

from datetime import datetime

_LEVEL_MAP = {
    "info": "INFO",
    "warning": "WARNING",
    "error": "ERROR",
    "success": "SUCCESS",
}


def format_log_line(message, level, dt=None):
    """Format a single log line with timestamp and level tag.

    :param message: Log message text.
    :param level: Severity string — 'info', 'warning', 'error', 'success'.
    :param dt: datetime to use for the timestamp; defaults to now.
    :returns: Formatted string ending with a newline.
    """
    if dt is None:
        dt = datetime.now()
    tag = _LEVEL_MAP.get(level, "INFO")
    return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} [{tag}] {message}\n"
