"""Tests for ARGUS Performance contention detection."""

import threading
import time

import pytest

from argus.performance.contention import (
    ContentionDetector,
    ContentionError,
    DeadlockError,
    LockWrapper,
)


class TestLockWrapper:
    """Tests for LockWrapper."""

    def test_acquire_and_release(self):
        lock = LockWrapper("test-lock")
        assert lock.acquire() is True
        assert lock.is_locked is True
        lock.release()
        assert lock.is_locked is False

    def test_acquire_with_timeout(self):
        lock = LockWrapper("test-lock", timeout=0.1)
        assert lock.acquire() is True
        lock.release()

    def test_acquire_timeout_fails(self):
        lock = LockWrapper("test-lock", timeout=0.01)
        lock.acquire()
        # Second acquire should fail due to timeout
        assert lock.acquire(blocking=True, timeout=0.01) is False
        lock.release()

    def test_owner_tracking(self):
        lock = LockWrapper("test-lock")
        assert lock.owner is None
        lock.acquire()
        assert lock.owner == threading.current_thread().ident
        lock.release()
        assert lock.owner is None

    def test_wait_count(self):
        lock = LockWrapper("test-lock")
        lock.acquire()
        lock.release()
        assert lock.wait_count == 1

    def test_contention_count(self):
        lock = LockWrapper("test-lock", timeout=0.01)
        lock.acquire()
        # This should fail and increment contention count
        lock.acquire(blocking=True, timeout=0.01)
        assert lock.contention_count == 1
        lock.release()


class TestContentionDetector:
    """Tests for ContentionDetector."""

    def test_record_lock_acquire(self):
        detector = ContentionDetector()
        detector.record_lock_acquire(threading.current_thread().ident, "lock-1")
        # No exception means success

    def test_record_lock_release(self):
        detector = ContentionDetector()
        thread_id = threading.current_thread().ident
        detector.record_lock_acquire(thread_id, "lock-1")
        detector.record_lock_release(thread_id, "lock-1")
        # No exception means success

    def test_detect_deadlock_no_cycle(self):
        detector = ContentionDetector()
        detector.record_lock_acquire(1, "lock-a")
        detector.record_lock_acquire(2, "lock-b")
        cycle = detector.detect_deadlock()
        assert cycle is None

    def test_record_contention(self):
        detector = ContentionDetector()
        detector.record_contention("lock-1", 0.5)
        events = detector.get_contention_events()
        assert len(events) == 1
        assert events[0]["lock_name"] == "lock-1"

    def test_clear_events(self):
        detector = ContentionDetector()
        detector.record_contention("lock-1", 0.5)
        detector.clear_events()
        assert len(detector.get_contention_events()) == 0

    def test_contention_with_multiple_locks(self):
        detector = ContentionDetector()
        detector.record_contention("lock-1", 0.1)
        detector.record_contention("lock-2", 0.2)
        detector.record_contention("lock-3", 0.3)
        events = detector.get_contention_events()
        assert len(events) == 3
