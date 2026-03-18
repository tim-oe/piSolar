"""Scheduler service with cron-like syntax support."""

import signal
import sys
from collections.abc import Callable
from typing import Any

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from py_singleton import singleton

from pisolar.logging_config import get_logger


@singleton
class SchedulerService:
    """Scheduler service wrapping APScheduler with cron syntax support.

    This is a singleton - all instances of SchedulerService will be the same object.
    """

    _logger = get_logger("scheduler")

    def __init__(self) -> None:
        """Initialize the scheduler."""
        self._scheduler = BlockingScheduler()
        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals gracefully."""
        sig_name = signal.Signals(signum).name
        self._logger.info("Received %s, shutting down scheduler...", sig_name)
        self.stop()
        sys.exit(0)

    def add_job(
        self,
        func: Callable[..., Any],
        cron_expression: str,
        job_id: str,
        **kwargs: Any,
    ) -> None:
        """
        Add a job with cron-like scheduling.

        Args:
            func: The function to execute
            cron_expression: Cron expression (5 fields: min hour day month weekday)
            job_id: Unique identifier for the job
            **kwargs: Additional arguments passed to the function
        """
        parts = cron_expression.split()
        if len(parts) != 5:
            raise ValueError(
                f"Invalid cron expression '{cron_expression}'. "
                "Expected 5 fields: minute hour day month day_of_week"
            )

        minute, hour, day, month, day_of_week = parts

        trigger = CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
        )

        self._scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            replace_existing=True,
            kwargs=kwargs,
        )
        self._logger.info("Added job '%s' with schedule: %s", job_id, cron_expression)

    def start(self) -> None:
        """Start the scheduler (blocking)."""
        self._logger.info("Starting scheduler...")
        try:
            self._scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self._logger.info("Scheduler stopped")

    def stop(self) -> None:
        """Stop the scheduler."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            self._logger.info("Scheduler stopped")

    @property
    def running(self) -> bool:
        """Check if scheduler is running."""
        return self._scheduler.running
