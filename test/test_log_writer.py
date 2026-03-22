"""
MapSplat - Export Log Writer Tests

Tests for the format_log_line helper and file-append behavior.
"""

__version__ = "0.1.0"

import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestFormatLogLine(unittest.TestCase):
    """Test the format_log_line pure-Python helper."""

    def _fn(self):
        from log_utils import format_log_line
        return format_log_line

    def test_info_level_appears_uppercase(self):
        line = self._fn()("hello", "info")
        self.assertIn("[INFO]", line)

    def test_warning_level_appears_uppercase(self):
        line = self._fn()("watch out", "warning")
        self.assertIn("[WARNING]", line)

    def test_error_level_appears_uppercase(self):
        line = self._fn()("oops", "error")
        self.assertIn("[ERROR]", line)

    def test_success_level_appears_uppercase(self):
        line = self._fn()("done", "success")
        self.assertIn("[SUCCESS]", line)

    def test_unknown_level_falls_back_to_info(self):
        line = self._fn()("msg", "debug")
        self.assertIn("[INFO]", line)

    def test_message_appears_in_line(self):
        line = self._fn()("my important message", "info")
        self.assertIn("my important message", line)

    def test_fixed_timestamp_appears_correctly(self):
        dt = datetime(2026, 2, 22, 14, 6, 26)
        line = self._fn()("hello", "info", dt=dt)
        self.assertTrue(line.startswith("2026-02-22 14:06:26"))

    def test_line_ends_with_newline(self):
        line = self._fn()("hello", "info")
        self.assertTrue(line.endswith("\n"))


class TestLogFileAppend(unittest.TestCase):
    """Test that log file writing appends and does not overwrite."""

    def _fn(self):
        from log_utils import format_log_line
        return format_log_line

    def test_second_run_preserves_first_run_content(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("previous run content\n")
            path = f.name
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(self._fn()("new export started", "info"))
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("previous run content", content)
            self.assertIn("new export started", content)
        finally:
            os.unlink(path)

    def test_log_file_contains_all_messages_in_order(self):
        messages = [
            ("Starting export...", "info"),
            ("Converting layers...", "info"),
            ("Export complete!", "success"),
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            path = f.name
        try:
            with open(path, "a", encoding="utf-8") as f:
                for msg, level in messages:
                    f.write(self._fn()(msg, level))
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()
            texts = [l.strip() for l in lines]
            self.assertTrue(any("Starting export" in t for t in texts))
            self.assertTrue(any("Converting layers" in t for t in texts))
            self.assertTrue(any("Export complete" in t for t in texts))
            # Order preserved
            start_idx = next(i for i, t in enumerate(texts) if "Starting export" in t)
            conv_idx = next(i for i, t in enumerate(texts) if "Converting layers" in t)
            done_idx = next(i for i, t in enumerate(texts) if "Export complete" in t)
            self.assertLess(start_idx, conv_idx)
            self.assertLess(conv_idx, done_idx)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
