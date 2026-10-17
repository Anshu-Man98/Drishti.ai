"""
Per-Claim Concurrency Lock & Idempotency Manager for FinShield / Drishti.ai.

Prevents duplicate concurrent analyses of the same claim.
- If an analysis is already running for claim_id:
  - Synchronous mode: waits on the running analysis and returns the resulting Dossier.
  - Asynchronous mode: immediately returns the running status without duplicating execution.
"""

import time
import logging
import threading
from typing import Dict, Optional, Tuple, Any

from backend.app.schemas import Dossier
from backend.app.config import settings

logger = logging.getLogger("finshield.services.claim_lock")


class _ActiveAnalysis:
    def __init__(self, claim_id: str):
        self.claim_id = claim_id
        self.started_at = time.time()
        self.event = threading.Event()
        self.dossier: Optional[Dossier] = None
        self.error: Optional[Exception] = None
        self.is_done = False


class ClaimLockManager:
    def __init__(self):
        self._mutex = threading.Lock()
        self._active: Dict[str, _ActiveAnalysis] = {}

    def is_running(self, claim_id: str) -> bool:
        """Returns True if an analysis for claim_id is actively running."""
        with self._mutex:
            active = self._active.get(claim_id)
            return active is not None and not active.is_done

    def acquire_or_wait(
        self,
        claim_id: str,
        async_mode: bool = False,
        timeout: Optional[float] = None
    ) -> Tuple[bool, Optional[Dossier]]:
        """
        Attempts to acquire execution leadership for claim_id.
        Returns:
            (is_leader, dossier)
            - If is_leader=True: Caller must execute the pipeline and call complete_analysis().
            - If is_leader=False and async_mode=True: Analysis already running, caller should return status immediately.
            - If is_leader=False and async_mode=False: Waited for running analysis to finish, dossier returned.
        """
        wait_timeout = timeout if timeout is not None else settings.ANALYSIS_BUDGET_SECONDS

        with self._mutex:
            active = self._active.get(claim_id)
            if active is not None and not active.is_done:
                # Analysis is currently running
                if async_mode:
                    logger.info("Claim %s analysis is already running (async mode requested)", claim_id)
                    return False, None
                target = active
            else:
                # No active analysis running; become leader
                new_active = _ActiveAnalysis(claim_id)
                self._active[claim_id] = new_active
                logger.info("Acquired analysis execution leadership for claim %s", claim_id)
                return True, None

        # Synchronous follower: wait for leader to complete
        logger.info("Waiting for existing analysis of claim %s to complete...", claim_id)
        finished = target.event.wait(timeout=wait_timeout)
        if not finished:
            logger.warning("Timed out waiting for concurrent analysis of claim %s", claim_id)
            raise TimeoutError(f"Timed out waiting for in-progress analysis of claim {claim_id}")

        if target.error is not None:
            raise target.error

        return False, target.dossier

    def complete_analysis(
        self,
        claim_id: str,
        dossier: Optional[Dossier] = None,
        error: Optional[Exception] = None
    ) -> None:
        """Notifies all waiting callers that analysis for claim_id has completed."""
        with self._mutex:
            active = self._active.get(claim_id)
            if active is not None:
                active.dossier = dossier
                active.error = error
                active.is_done = True
                active.event.set()
                # Remove from active tracking
                self._active.pop(claim_id, None)
                logger.info("Completed and released analysis lock for claim %s", claim_id)

    def clear(self) -> None:
        """Clears all locks (for testing purposes)."""
        with self._mutex:
            for active in self._active.values():
                active.event.set()
            self._active.clear()


claim_lock_manager = ClaimLockManager()
