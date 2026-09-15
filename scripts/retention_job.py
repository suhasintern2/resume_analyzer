#!/usr/bin/env python3
"""Scheduled retention/purge job (Task 6, amendment §6).

Deletes RECORD files and their ``files`` rows for interviews whose
evaluation is complete AND older than RETENTION_DAYS. Runs standalone so it
can be driven by cron/systemd-timer — request handling never triggers it.

Example cron line (daily at 02:30):
    30 2 * * * cd /path/to/resumeanalyzer && venv/bin/python scripts/retention_job.py >> /var/log/resume_retention.log 2>&1

Exit code 0 on success, 1 on any error.
"""

import logging
import os
import sys

# Make the project root importable when run as a plain script from cron.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.db import SessionLocal
from app.services.retention_service import purge_expired_records

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)


def main() -> int:
    try:
        with SessionLocal() as session:
            summary = purge_expired_records(
                session, retention_days=settings.RETENTION_DAYS,
            )
        total = sum(len(types) for types in summary.values())
        print(f"retention_job: purged {total} record file(s)")
        return 0
    except Exception:
        logging.exception("retention_job failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())