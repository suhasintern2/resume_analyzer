"""Pytest configuration for the resumeanalyzer test suite.

Disables the Task 8 background worker so tests never race it: tests drive
``process_next_job`` / ``recover_interviews`` explicitly.  Must run before any
``app.*`` import (config reads env at import time).
"""

import os

os.environ["WORKER_ENABLED"] = "false"