"""ARGUS Durable Execution Lock Manager.

Prevents concurrent resume of the same run.
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Optional

from argus.durable.models import LockState

logger = logging.getLogger(__name__)

LOCK_DIR = os.path.join(os.path.expanduser("~"), ".argus", "locks")
LOCK_TIMEOUT_SECONDS = 300  # 5 minutes


class LockManager:
    """Manages locks for run resume operations.

    Prevents two ARGUS processes from resuming the same run simultaneously.
    """

    def __init__(
        self,
        lock_dir: str = LOCK_DIR,
        lock_timeout: int = LOCK_TIMEOUT_SECONDS,
    ):
        self._lock_dir = lock_dir
        self._lock_timeout = lock_timeout
        os.makedirs(self._lock_dir, exist_ok=True)

    def acquire_lock(
        self,
        run_id: str,
        owner_id: str,
        force: bool = False,
    ) -> Optional[LockState]:
        """Acquire a lock on a run.

        Args:
            run_id: The run to lock
            owner_id: The ID of the process acquiring the lock
            force: Force acquire even if lock exists (for stale locks)

        Returns:
            LockState if lock acquired, None if lock already held
        """
        existing = self.get_lock(run_id)

        if existing:
            if existing.state == "acquired" and not force:
                if not self._is_lock_stale(existing):
                    logger.warning(f"Run {run_id} is already locked by {existing.owner_id}")
                    return None
                # Lock is stale, can be overridden
                logger.info(f"Overriding stale lock on run {run_id}")

        expires_at = (datetime.utcnow() + timedelta(seconds=self._lock_timeout)).isoformat()
        lock = LockState(
            run_id=run_id,
            owner_id=owner_id,
            acquired_at=datetime.utcnow().isoformat(),
            expires_at=expires_at,
            state="acquired",
        )

        self._save_lock(lock)
        logger.info(f"Lock acquired for run {run_id} by {owner_id}")
        return lock

    def release_lock(self, run_id: str, owner_id: str) -> bool:
        """Release a lock on a run.

        Args:
            run_id: The run to unlock
            owner_id: The ID of the process releasing the lock

        Returns:
            True if lock was released, False if not owner
        """
        lock = self.get_lock(run_id)
        if not lock:
            return True

        if lock.owner_id != owner_id:
            logger.warning(
                f"Cannot release lock on {run_id}: owned by {lock.owner_id}, not {owner_id}"
            )
            return False

        lock.state = "released"
        lock.metadata["released_at"] = datetime.utcnow().isoformat()
        self._save_lock(lock)
        logger.info(f"Lock released for run {run_id}")
        return True

    def get_lock(self, run_id: str) -> Optional[LockState]:
        """Get the lock state for a run."""
        path = self._lock_path(run_id)
        if not os.path.exists(path):
            return None

        try:
            with open(path, "r") as f:
                data = json.load(f)
            return LockState.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load lock for {run_id}: {e}")
            return None

    def is_locked(self, run_id: str) -> bool:
        """Check if a run is currently locked."""
        lock = self.get_lock(run_id)
        if not lock:
            return False

        if lock.state != "acquired":
            return False

        if self._is_lock_stale(lock):
            return False

        return True

    def get_owner(self, run_id: str) -> Optional[str]:
        """Get the owner of a run lock."""
        lock = self.get_lock(run_id)
        if not lock or lock.state != "acquired":
            return None
        return lock.owner_id

    def force_unlock(self, run_id: str) -> bool:
        """Force unlock a run (for admin/recovery purposes)."""
        lock = self.get_lock(run_id)
        if not lock:
            return True

        lock.state = "released"
        lock.metadata["force_unlocked_at"] = datetime.utcnow().isoformat()
        self._save_lock(lock)
        logger.warning(f"Force unlocked run {run_id}")
        return True

    def cleanup_stale_locks(self) -> int:
        """Clean up stale locks.

        Returns:
            Number of locks cleaned up
        """
        cleaned = 0
        for filename in os.listdir(self._lock_dir):
            if filename.endswith(".json"):
                run_id = filename[:-5]
                lock = self.get_lock(run_id)
                if lock and lock.state == "acquired" and self._is_lock_stale(lock):
                    lock.state = "stale"
                    self._save_lock(lock)
                    cleaned += 1
        return cleaned

    def _is_lock_stale(self, lock: LockState) -> bool:
        """Check if a lock is stale (expired)."""
        if not lock.expires_at:
            return False

        try:
            expires = datetime.fromisoformat(lock.expires_at)
            return datetime.utcnow() > expires
        except (ValueError, TypeError):
            return True

    def _save_lock(self, lock: LockState):
        """Save lock state to disk."""
        path = self._lock_path(lock.run_id)
        with open(path, "w") as f:
            json.dump(lock.to_dict(), f, indent=2)

    def _lock_path(self, run_id: str) -> str:
        """Get the file path for a lock."""
        return os.path.join(self._lock_dir, f"{run_id}.json")
