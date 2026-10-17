"""
FinShield LLM Token Budget Guard & Cloud Spend Tracker.

Hard caps total Gemini tokens consumed for a single claim analysis across all agents
(default: 30,000 prompt+candidate tokens) to prevent runaway loops or credit exhaustion.
Tracks running token counts and estimated costs (USD), reporting metrics in finalized dossiers.
"""

import logging
import threading
from typing import Dict, Tuple, Any

from backend.app.config import settings
from backend.app.exceptions import DrishtiError

logger = logging.getLogger("finshield.services.token_budget")


class TokenBudgetExceededError(DrishtiError):
    """Raised when an analysis exceeds the hard LLM token budget for a claim."""

    def __init__(self, claim_id: str, tokens_spent: int, token_budget: int):
        super().__init__(
            message=f"Gemini LLM token budget exceeded for claim {claim_id}: {tokens_spent} tokens used (limit: {token_budget}).",
            status_code=422,
            code="token_budget_exceeded",
            details={
                "claim_id": claim_id,
                "tokens_spent": tokens_spent,
                "token_budget": token_budget
            }
        )
        self.claim_id = claim_id
        self.tokens_spent = tokens_spent
        self.token_budget = token_budget


class TokenBudgetTracker:
    """Thread-safe per-claim and global Gemini LLM token and cost tracker."""

    def __init__(self):
        self._mutex = threading.Lock()
        self._claim_tokens: Dict[str, int] = {}
        self._claim_cost: Dict[str, float] = {}
        self._global_prompt_tokens: int = 0
        self._global_candidate_tokens: int = 0
        self._global_cost_usd: float = 0.0

    def record_usage(
        self,
        claim_id: str,
        prompt_tokens: int,
        candidate_tokens: int,
        model: str = "gemini-2.5-flash"
    ) -> int:
        """
        Records prompt and candidate token consumption for a claim.
        Computes USD cost based on published Gemini rates.
        Raises TokenBudgetExceededError if running total exceeds settings.MAX_CLAIM_LLM_TOKENS.
        """
        # Gemini 2.5/3.5 Flash pricing: $0.15 / 1M prompt tokens, $0.60 / 1M candidate tokens
        # Gemini Pro pricing: $1.25 / 1M prompt tokens, $5.00 / 1M candidate tokens
        is_pro = "pro" in model.lower()
        prompt_rate = 1.25 / 1_000_000.0 if is_pro else 0.15 / 1_000_000.0
        candidate_rate = 5.00 / 1_000_000.0 if is_pro else 0.60 / 1_000_000.0

        cost_for_call = (prompt_tokens * prompt_rate) + (candidate_tokens * candidate_rate)
        call_tokens = prompt_tokens + candidate_tokens

        with self._mutex:
            current_total = self._claim_tokens.get(claim_id, 0) + call_tokens
            current_cost = self._claim_cost.get(claim_id, 0.0) + cost_for_call

            self._claim_tokens[claim_id] = current_total
            self._claim_cost[claim_id] = current_cost

            self._global_prompt_tokens += prompt_tokens
            self._global_candidate_tokens += candidate_tokens
            self._global_cost_usd += cost_for_call

            budget = settings.MAX_CLAIM_LLM_TOKENS

            logger.info(
                "[TokenBudget] Claim %s consumed %d tokens (+%d this call, cost: $%.4f, total: %d/%d)",
                claim_id, current_total, call_tokens, cost_for_call, current_total, budget,
                extra={"claim_id": claim_id, "tokens_spent": current_total, "budget": budget}
            )

            if current_total > budget:
                logger.error(
                    "[TokenBudget] Hard budget exceeded for claim %s: %d > %d tokens",
                    claim_id, current_total, budget
                )
                raise TokenBudgetExceededError(claim_id, current_total, budget)

            return current_total

    def get_claim_usage(self, claim_id: str) -> Tuple[int, float]:
        """Returns (tokens_spent, cost_usd) for a given claim."""
        with self._mutex:
            tokens = self._claim_tokens.get(claim_id, 0)
            cost = round(self._claim_cost.get(claim_id, 0.0), 4)
            return tokens, cost

    def get_global_usage(self) -> Dict[str, Any]:
        """Returns cumulative global token usage and cost metrics."""
        with self._mutex:
            return {
                "claims_tracked": len(self._claim_tokens),
                "total_prompt_tokens": self._global_prompt_tokens,
                "total_candidate_tokens": self._global_candidate_tokens,
                "total_tokens": self._global_prompt_tokens + self._global_candidate_tokens,
                "total_cost_usd": round(self._global_cost_usd, 4),
                "budget_per_claim": settings.MAX_CLAIM_LLM_TOKENS,
            }

    def clear(self) -> None:
        """Resets all token tracking (for test isolation)."""
        with self._mutex:
            self._claim_tokens.clear()
            self._claim_cost.clear()
            self._global_prompt_tokens = 0
            self._global_candidate_tokens = 0
            self._global_cost_usd = 0.0


token_budget_tracker = TokenBudgetTracker()
