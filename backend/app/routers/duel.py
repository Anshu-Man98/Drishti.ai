from datetime import datetime
import logging
import re
from typing import Optional, List, Dict, Any
import uuid

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from pydantic import BaseModel, Field

from backend.app.schemas import Claim
from backend.app.services.db import db_service
from backend.agents.duel import run_duel, DuelResult, create_fraudster_agent
from backend.app.dependencies import get_current_user

logger = logging.getLogger("finshield.routers.duel")
router = APIRouter(prefix="/duel", tags=["duel"])


class StartDuelRequest(BaseModel):
    claim_id: Optional[str] = Field(default=None, description="Base claim ID to mutate. If omitted, uses first available authentic claim.")
    rounds: int = Field(default=5, ge=1, le=10, description="Maximum number of duel rounds")
    wait: bool = Field(default=False, description="If True, executes synchronously. If False, runs in background and returns duel_id immediately.")


class DuelStatusResponse(BaseModel):
    duel_id: str
    status: str  # "running" | "completed" | "failed"
    current_round: int
    max_rounds: int
    base_claim_id: Optional[str] = None
    baseline_amount: Optional[float] = None
    winning_side: Optional[str] = None
    error: Optional[str] = None
    rounds: List[Dict[str, Any]] = Field(default_factory=list)
    learned_pattern: Optional[Dict[str, Any]] = None


def _execute_duel_in_background(duel_id: str, claim_obj: Claim, max_rounds: int):
    """Background runner for adversarial duel, saving progress and errors to Firestore."""
    try:
        logger.info("Background duel %s launched for claim %s (%d rounds)", duel_id, claim_obj.claim_id, max_rounds)
        result = run_duel(claim_obj, max_rounds=max_rounds, duel_id=duel_id)
        w_side = str(result.winning_side) if result.winning_side is not None else None
        lp = result.learned_pattern if isinstance(getattr(result, "learned_pattern", None), dict) else None
        db_service.save_duel_meta(duel_id, {
            "duel_id": duel_id,
            "status": "completed",
            "current_round": len(result.rounds) if hasattr(result.rounds, "__len__") else 0,
            "max_rounds": max_rounds,
            "base_claim_id": claim_obj.claim_id,
            "baseline_amount": float(claim_obj.total_claimed),
            "winning_side": w_side,
            "error": None,
            "learned_pattern": lp,
            "completed_at": datetime.utcnow().isoformat(),
        })
        logger.info("Background duel %s completed successfully (winner: %s)", duel_id, w_side)
    except Exception as exc:
        logger.error("Background duel %s encountered a failure: %s", duel_id, exc, exc_info=True)
        db_service.save_duel_meta(duel_id, {
            "duel_id": duel_id,
            "status": "failed",
            "error": str(exc),
            "failed_at": datetime.utcnow().isoformat(),
        })


@router.post("/start", response_model=DuelResult)
async def start_duel(
    req: Optional[StartDuelRequest] = None,
    background_tasks: BackgroundTasks = None,
    wait: Optional[bool] = Query(None, description="Override synchronous execution mode"),
    user=Depends(get_current_user)
):
    """
    Executes an adversarial duel where the Fraudster agent attempts to mutate the base claim
    to maximize payout while evading FinShield's multi-agent pipeline.
    By default (wait=False), returns duel_id immediately while rounds run asynchronously in the background.
    """
    req = req or StartDuelRequest()
    is_sync = wait if wait is not None else req.wait

    base_claim: Optional[Claim] = None
    if req.claim_id:
        base_claim = db_service.get_claim(req.claim_id)
        if not base_claim:
            raise HTTPException(status_code=404, detail=f"Claim {req.claim_id} not found")
    else:
        # Prefer canonical clean claim G1 if available
        g1_claim = db_service.get_claim("CLM-G1-CLEAN-DEMO")
        if g1_claim and g1_claim.line_items:
            base_claim = g1_claim
        else:
            all_claims = db_service.list_claims(limit=50)
            clean_claims = [
                c for c in all_claims
                if not c.claim_id.startswith(("CLM-SEC-", "CLM-BOUNDS-", "CLM-API-TEST"))
                and not re.search(r"-D\d+$", c.claim_id)
            ]
            chosen_claim_id: Optional[str] = None
            for c in clean_claims:
                dossier = db_service.get_dossier(c.claim_id)
                if dossier and str(dossier.verdict).lower() in ("approve", "verdict.approve"):
                    chosen_claim_id = c.claim_id
                    break
            if not chosen_claim_id and clean_claims:
                g1_match = next((c.claim_id for c in clean_claims if "G1" in c.claim_id), None)
                chosen_claim_id = g1_match or clean_claims[0].claim_id

            if chosen_claim_id:
                base_claim = db_service.get_claim(chosen_claim_id)

    if not base_claim or not base_claim.line_items:
        raise HTTPException(
            status_code=400,
            detail="No suitable base claim with line items found in database to initiate duel."
        )

    duel_id = f"DUEL-{uuid.uuid4().hex[:8].upper()}"

    if is_sync:
        # Synchronous execution for scripts & legacy callers
        result = run_duel(base_claim, max_rounds=req.rounds, duel_id=duel_id)
        db_service.save_duel_meta(duel_id, {
            "duel_id": duel_id,
            "status": "completed",
            "current_round": len(result.rounds),
            "max_rounds": req.rounds,
            "base_claim_id": base_claim.claim_id,
            "baseline_amount": float(base_claim.total_claimed),
            "winning_side": result.winning_side,
            "learned_pattern": result.learned_pattern if isinstance(getattr(result, "learned_pattern", None), dict) else None,
            "completed_at": datetime.utcnow().isoformat(),
        })
        return result

    # Asynchronous background execution: return duel_id immediately
    initial_meta = {
        "duel_id": duel_id,
        "base_claim_id": base_claim.claim_id,
        "baseline_amount": float(base_claim.total_claimed),
        "max_rounds": req.rounds,
        "current_round": 1,
        "status": "running",
        "winning_side": None,
        "error": None,
        "started_at": datetime.utcnow().isoformat(),
    }
    db_service.save_duel_meta(duel_id, initial_meta)

    if background_tasks is not None:
        background_tasks.add_task(_execute_duel_in_background, duel_id, base_claim, req.rounds)

    return DuelResult(
        duel_id=duel_id,
        base_claim_id=base_claim.claim_id,
        baseline_amount=float(base_claim.total_claimed),
        max_rounds=req.rounds,
        rounds=[],
        status="running",
        winning_side="running",
        learned_pattern=None
    )


@router.get("/{duel_id}/status", response_model=DuelStatusResponse)
async def get_duel_status_endpoint(duel_id: str, user=Depends(get_current_user)):
    """Retrieves live round progress and lifecycle status of a duel."""
    meta = db_service.get_duel_meta(duel_id)
    rounds = db_service.get_duel_rounds(duel_id)

    if not meta and not rounds:
        raise HTTPException(status_code=404, detail=f"Duel '{duel_id}' not found.")

    meta = meta or {}
    status = meta.get("status", "completed" if rounds else "running")
    current_round = meta.get("current_round", max(1, len(rounds)))

    return DuelStatusResponse(
        duel_id=duel_id,
        status=str(status),
        current_round=int(current_round),
        max_rounds=int(meta.get("max_rounds", 5)),
        base_claim_id=str(meta.get("base_claim_id")) if meta.get("base_claim_id") else None,
        baseline_amount=float(meta.get("baseline_amount")) if meta.get("baseline_amount") is not None else None,
        winning_side=str(meta.get("winning_side")) if meta.get("winning_side") is not None else None,
        error=str(meta.get("error")) if meta.get("error") is not None else None,
        rounds=rounds,
        learned_pattern=meta.get("learned_pattern") if isinstance(meta.get("learned_pattern"), dict) else None
    )


@router.get("/{duel_id}/rounds", response_model=List[Dict[str, Any]])
async def get_duel_rounds_endpoint(duel_id: str, user=Depends(get_current_user)):
    """Retrieves all rounds for a given duel."""
    meta = db_service.get_duel_meta(duel_id)
    rounds = db_service.get_duel_rounds(duel_id)
    if not meta and not rounds:
        raise HTTPException(status_code=404, detail=f"Duel '{duel_id}' not found.")
    return rounds


@router.get("/patterns/learned", response_model=List[Dict[str, Any]])
async def get_learned_patterns_endpoint(user=Depends(get_current_user)):
    """Retrieves all evasion patterns learned from adversarial duels."""
    patterns = db_service.get_learned_patterns()
    return patterns
