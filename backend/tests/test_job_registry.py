"""Tests for the persisted background job registry."""
import pytest
from datetime import datetime

from app.services import job_registry
from app.database_models import IndexJob, Archive


def test_create_job(db_session):
    """Creating a job returns a persisted IndexJob with pending status."""
    archive = Archive(id="a1", name="test.zim", path="/tmp/test.zim", size_bytes=100, article_count=0)
    db_session.add(archive)
    db_session.commit()

    job = job_registry.create_job(db_session, "a1", total=500)
    assert job.archive_id == "a1"
    assert job.status == "pending"
    assert job.progress == 0
    assert job.total == 500

    db_job = db_session.query(IndexJob).filter(IndexJob.id == job.id).first()
    assert db_job is not None
    assert db_job.status == "pending"


def test_get_job(db_session):
    """get_job retrieves a job by id."""
    archive = Archive(id="a2", name="test.zim", path="/tmp/test2.zim", size_bytes=100, article_count=0)
    db_session.add(archive)
    db_session.commit()
    job = job_registry.create_job(db_session, "a2")

    retrieved = job_registry.get_job(db_session, job.id)
    assert retrieved is not None
    assert retrieved.id == job.id

    missing = job_registry.get_job(db_session, 9999)
    assert missing is None


def test_get_latest_job(db_session):
    """get_latest_job returns the most recent job for an archive."""
    archive = Archive(id="a3", name="test.zim", path="/tmp/test3.zim", size_bytes=100, article_count=0)
    db_session.add(archive)
    db_session.commit()

    j1 = job_registry.create_job(db_session, "a3", total=100)
    j2 = job_registry.create_job(db_session, "a3", total=200)

    latest = job_registry.get_latest_job(db_session, "a3")
    assert latest.id == j2.id
    assert latest.total == 200


def test_update_job_status(db_session):
    """update_job_status transitions job states correctly."""
    archive = Archive(id="a4", name="test.zim", path="/tmp/test4.zim", size_bytes=100, article_count=0)
    db_session.add(archive)
    db_session.commit()
    job = job_registry.create_job(db_session, "a4")

    job_registry.update_job_status(db_session, job.id, "running")
    assert job_registry.get_job(db_session, job.id).status == "running"
    assert job_registry.get_job(db_session, job.id).started_at is not None

    job_registry.update_job_status(db_session, job.id, "running", progress=50)
    assert job_registry.get_job(db_session, job.id).progress == 50

    job_registry.update_job_status(db_session, job.id, "completed")
    assert job_registry.get_job(db_session, job.id).status == "completed"
    assert job_registry.get_job(db_session, job.id).completed_at is not None

    job_registry.update_job_status(db_session, job.id, "failed", error_message="something broke")
    assert job_registry.get_job(db_session, job.id).status == "failed"
    assert "something broke" in job_registry.get_job(db_session, job.id).error_message


def test_pause_resume_cancel(db_session):
    """pause, resume, cancel lifecycle works correctly."""
    archive = Archive(id="a5", name="test.zim", path="/tmp/test5.zim", size_bytes=100, article_count=0)
    db_session.add(archive)
    db_session.commit()
    job = job_registry.create_job(db_session, "a5")
    job_registry.update_job_status(db_session, job.id, "running", progress=10)

    # Pause
    paused = job_registry.pause_job(db_session, "a5")
    assert paused.status == "paused"

    # Resume
    resumed = job_registry.resume_job(db_session, "a5")
    assert resumed.status == "running"

    # Cancel
    cancelled = job_registry.cancel_job(db_session, "a5")
    assert cancelled.status == "cancelled"

    # Resuming a cancelled job returns None (starts new job instead)
    none_job = job_registry.resume_job(db_session, "a5")
    assert none_job is None


def test_get_all_active_jobs(db_session):
    """get_all_active_jobs returns only pending/running/paused jobs."""
    archive = Archive(id="a6", name="test.zim", path="/tmp/test6.zim", size_bytes=100, article_count=0)
    db_session.add(archive)
    db_session.commit()

    j1 = job_registry.create_job(db_session, "a6")
    job_registry.update_job_status(db_session, j1.id, "running")

    j2 = job_registry.create_job(db_session, "a6")
    job_registry.update_job_status(db_session, j2.id, "completed")

    active = job_registry.get_all_active_jobs(db_session)
    assert len(active) == 1
    assert active[0].id == j1.id


def test_get_status_no_job(db_session):
    """get_status returns None when no job exists."""
    status = job_registry.get_status(db_session, "nonexistent")
    assert status is None


def test_mark_interrupted_on_startup(db_session):
    """mark_interrupted_on_startup marks running jobs as failed."""
    archive = Archive(id="a7", name="test.zim", path="/tmp/test7.zim", size_bytes=100, article_count=0)
    db_session.add(archive)
    db_session.commit()

    job = job_registry.create_job(db_session, "a7")
    job_registry.update_job_status(db_session, job.id, "running")

    job_registry.mark_interrupted_on_startup(db_session)

    updated = job_registry.get_job(db_session, job.id)
    assert updated.status == "failed"
    assert "restarted" in updated.error_message


def test_get_jobs_for_archive(db_session):
    """get_jobs_for_archive returns all jobs for an archive in desc order."""
    archive = Archive(id="a8", name="test.zim", path="/tmp/test8.zim", size_bytes=100, article_count=0)
    db_session.add(archive)
    db_session.commit()

    j1 = job_registry.create_job(db_session, "a8")
    j2 = job_registry.create_job(db_session, "a8")
    j3 = job_registry.create_job(db_session, "a8")

    jobs = job_registry.get_jobs_for_archive(db_session, "a8")
    assert len(jobs) == 3
    assert jobs[0].id == j3.id  # desc order
    assert jobs[1].id == j2.id
    assert jobs[2].id == j1.id
