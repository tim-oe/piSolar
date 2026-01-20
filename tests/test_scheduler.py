"""Tests for scheduler module."""

import pytest

from pisolar.scheduler import SchedulerService


class TestSchedulerService:
    """Tests for SchedulerService class."""

    def test_scheduler_creation(self):
        """Test scheduler can be created."""
        scheduler = SchedulerService()
        assert scheduler is not None
        assert scheduler.running is False

    def test_add_job_valid_cron(self):
        """Test adding a job with valid cron expression."""
        scheduler = SchedulerService()
        call_count = 0

        def test_func():
            nonlocal call_count
            call_count += 1

        scheduler.add_job(test_func, "*/5 * * * *", job_id="test_job")

        # Job should be added without error
        # We don't start the scheduler to avoid blocking

    def test_add_job_invalid_cron(self):
        """Test adding a job with invalid cron expression raises error."""
        scheduler = SchedulerService()

        def test_func():
            pass

        with pytest.raises(ValueError, match="Invalid cron expression"):
            scheduler.add_job(test_func, "invalid", job_id="test_job")

    def test_add_job_wrong_field_count(self):
        """Test cron with wrong number of fields raises error."""
        scheduler = SchedulerService()

        def test_func():
            pass

        # Only 3 fields instead of 5
        with pytest.raises(ValueError, match="Expected 5 fields"):
            scheduler.add_job(test_func, "* * *", job_id="test_job")
