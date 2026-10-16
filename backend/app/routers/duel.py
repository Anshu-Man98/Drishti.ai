"""
Duel Arena API Router (F6 Dueling AI).
Provides endpoints to trigger adversarial duels and retrieve rounds/learned patterns.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from backend.app.schemas import Claim
from backend.app.services.db import db_service
from backend.agents.duel import run_duel, DuelResult, create_fraudster_agent
from backend.app.dependencies import get_current_user

router = APIRouter(prefix="/duel", tags=["duel"])


import re


class StartDuelRequest(BaseModel):
    claim_id: Optional[str] = Field(default=None, description="Base claim ID to mutate. If omitted, uses first available authentic claim.")
    rounds: int = Field(default=5, ge=1, le=10, description="Maximum number of duel rounds")


@router.post("/start", response_model=DuelResult)
async def start_duel(req: Optional[StartDuelRequest] = None, user=Depends(get_current_user)):
    """
    Executes an adversarial duel where the Fraudster agent attempts to mutate the base claim
    to maximize payout while evading FinShield's multi-agent pipeline.
    """
    req = req or StartDuelRequest()
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

    result = run_duel(base_claim, max_rounds=req.rounds)
    return result


@router.get("/{duel_id}/rounds", response_model=List[Dict[str, Any]])
async def get_duel_rounds_endpoint(duel_id: str, user=Depends(get_current_user)):
    """Retrieves all rounds for a given duel."""
    rounds = db_service.get_duel_rounds(duel_id)
    return rounds


@router.get("/patterns/learned", response_model=List[Dict[str, Any]])
async def get_learned_patterns_endpoint(user=Depends(get_current_user)):
    """Retrieves all evasion patterns learned from adversarial duels."""
    patterns = db_service.get_learned_patterns()
    return patterns
