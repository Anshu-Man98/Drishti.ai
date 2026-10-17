import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from backend.app.config import settings
from backend.app.dependencies import get_current_user
from backend.tools.bq import bq_warehouse

logger = logging.getLogger("finshield.routers.graph")

router = APIRouter(prefix="/graph", tags=["graph"])


class NetworkNode(BaseModel):
    id: str
    label: str
    type: str  # 'claimant' | 'doctor' | 'hospital' | 'bank_account'
    ring_id: str
    risk_score: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NetworkEdge(BaseModel):
    source: str
    target: str
    type: str  # 'shares_account_with' | 'treated_by' | 'admitted_to' | 'practiced_at'
    label: Optional[str] = None
    claim_id: Optional[str] = None
    amount: Optional[float] = None


class FraudRingSummary(BaseModel):
    ring_id: str
    title: str
    type: str  # 'shared_bank_account' | 'ghost_doctor_syndicate' | 'hospital_cluster'
    claim_count: int
    claimant_count: int
    total_amount: float
    primary_entity: str
    risk_level: str  # 'critical' | 'high' | 'medium'
    description: str
    sample_cities: List[str] = Field(default_factory=list)


class RingDetailResponse(BaseModel):
    ring: FraudRingSummary
    nodes: List[NetworkNode]
    edges: List[NetworkEdge]
    claims: List[Dict[str, Any]]


class GraphRingsResponse(BaseModel):
    rings: List[FraudRingSummary]
    selected_ring: Optional[RingDetailResponse] = None


def _fetch_fraud_rings() -> List[FraudRingSummary]:
    """Queries live BigQuery claims data for active fraud rings."""
    rings: List[FraudRingSummary] = []

    # 1. Shared Bank Account Collusion Rings
    bank_query = f"""
    SELECT 
        bank_account_hash,
        COUNT(DISTINCT claimant_id) as claimant_count,
        COUNT(claim_id) as claim_count,
        ROUND(SUM(total_claimed), 2) as total_amount,
        ARRAY_AGG(DISTINCT city IGNORE NULLS LIMIT 4) as sample_cities
    FROM `{settings.GCP_PROJECT}.{settings.BIGQUERY_DATASET}.claims`
    WHERE bank_account_hash IS NOT NULL AND bank_account_hash != ""
    GROUP BY bank_account_hash
    HAVING claimant_count > 1
    ORDER BY claimant_count DESC
    LIMIT 10
    """
    try:
        bank_results = list(bq_warehouse.client.query(bank_query).result())
        for idx, row in enumerate(bank_results):
            bhash = row.bank_account_hash
            parts = bhash.split('_')
            suffix = parts[-1] if parts else bhash[-4:]
            ring_id = f"RING-BANK-{suffix.upper()}"
            risk_level = "critical" if row.claimant_count >= 20 else "high"
            
            rings.append(FraudRingSummary(
                ring_id=ring_id,
                title=f"Syndicate {suffix.upper()}: Shared Bank Account Ring",
                type="shared_bank_account",
                claim_count=int(row.claim_count),
                claimant_count=int(row.claimant_count),
                total_amount=float(row.total_amount),
                primary_entity=bhash,
                risk_level=risk_level,
                description=f"{row.claimant_count} distinct claimants routing claim disbursements into the same centralized bank account.",
                sample_cities=list(row.sample_cities or [])
            ))
    except Exception as e:
        logger.error(f"Failed to query shared bank rings: {e}")

    # 2. Ghost Doctor Multi-City Syndicates (Impossible Travel)
    doc_query = f"""
    SELECT 
        doctor_id,
        COUNT(DISTINCT hospital_id) as hospital_count,
        COUNT(DISTINCT city) as city_count,
        COUNT(DISTINCT claimant_id) as claimant_count,
        COUNT(claim_id) as claim_count,
        ROUND(SUM(total_claimed), 2) as total_amount,
        ARRAY_AGG(DISTINCT city IGNORE NULLS LIMIT 4) as sample_cities
    FROM `{settings.GCP_PROJECT}.{settings.BIGQUERY_DATASET}.claims`
    WHERE fraud_type = "impossible_travel"
    GROUP BY doctor_id
    HAVING claim_count >= 2
    ORDER BY claim_count DESC
    LIMIT 5
    """
    try:
        doc_results = list(bq_warehouse.client.query(doc_query).result())
        for row in doc_results:
            did = row.doctor_id
            ring_id = f"RING-DOC-{did.replace('DOC-', '')}"
            rings.append(FraudRingSummary(
                ring_id=ring_id,
                title=f"Syndicate {did}: Ghost Doctor Velocity",
                type="ghost_doctor_syndicate",
                claim_count=int(row.claim_count),
                claimant_count=int(row.claimant_count),
                total_amount=float(row.total_amount),
                primary_entity=did,
                risk_level="high",
                description=f"Physician billed patient admissions across {row.city_count} distant cities in physically impossible transit windows.",
                sample_cities=list(row.sample_cities or [])
            ))
    except Exception as e:
        logger.error(f"Failed to query doctor rings: {e}")

    return rings


def _build_subgraph_for_ring(ring: FraudRingSummary, limit: int = 20) -> RingDetailResponse:
    """Builds nodes, edges, and real claim records for a given fraud ring."""
    from google.cloud import bigquery

    nodes_dict: Dict[str, NetworkNode] = {}
    edges_list: List[NetworkEdge] = []
    claims_list: List[Dict[str, Any]] = []

    if ring.type == "shared_bank_account":
        query = f"""
        SELECT 
            claim_id, policy_id, insurer_id, claimant_id, claimant_name, claimant_phone,
            bank_account_hash, hospital_id, hospital_name, city, lat, lng, doctor_id,
            admission_ts, discharge_ts, diagnosis_code, total_claimed, is_fraud, fraud_type
        FROM `{settings.GCP_PROJECT}.{settings.BIGQUERY_DATASET}.claims`
        WHERE bank_account_hash = @target
        ORDER BY total_claimed DESC
        LIMIT @limit
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("target", "STRING", ring.primary_entity),
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
            ]
        )
    else:  # ghost_doctor_syndicate
        query = f"""
        SELECT 
            claim_id, policy_id, insurer_id, claimant_id, claimant_name, claimant_phone,
            bank_account_hash, hospital_id, hospital_name, city, lat, lng, doctor_id,
            admission_ts, discharge_ts, diagnosis_code, total_claimed, is_fraud, fraud_type
        FROM `{settings.GCP_PROJECT}.{settings.BIGQUERY_DATASET}.claims`
        WHERE doctor_id = @target
        ORDER BY admission_ts DESC
        LIMIT @limit
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("target", "STRING", ring.primary_entity),
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
            ]
        )

    try:
        rows = list(bq_warehouse.client.query(query, job_config=job_config).result())
    except Exception as e:
        logger.error(f"Failed to query claims for ring {ring.ring_id}: {e}")
        rows = []

    # Insert Central Hub Node
    if ring.type == "shared_bank_account":
        central_id = ring.primary_entity
        short = central_id[-6:] if len(central_id) >= 6 else central_id
        nodes_dict[central_id] = NetworkNode(
            id=central_id,
            label=f"Bank (*{short})",
            type="bank_account",
            ring_id=ring.ring_id,
            risk_score=95.0,
            metadata={"account_hash": central_id, "claims_analyzed": len(rows), "total_amount": ring.total_amount}
        )
    else:
        central_id = ring.primary_entity
        doc_num = central_id[4:] if central_id.startswith("DOC-") else central_id
        nodes_dict[central_id] = NetworkNode(
            id=central_id,
            label=f"Dr. {doc_num}",
            type="doctor",
            ring_id=ring.ring_id,
            risk_score=90.0,
            metadata={"doctor_id": central_id, "claims_analyzed": len(rows), "total_amount": ring.total_amount}
        )

    # Process each claim and connect nodes
    for r in rows:
        claim_dict = {
            "claim_id": r.claim_id,
            "policy_id": r.policy_id,
            "insurer_id": r.insurer_id,
            "claimant_id": r.claimant_id,
            "claimant_name": r.claimant_name or r.claimant_id,
            "claimant_phone": r.claimant_phone or "",
            "bank_account_hash": r.bank_account_hash or "",
            "hospital_id": r.hospital_id,
            "hospital_name": r.hospital_name or r.hospital_id,
            "city": r.city,
            "doctor_id": r.doctor_id,
            "admission_ts": r.admission_ts.isoformat() if r.admission_ts else "",
            "discharge_ts": r.discharge_ts.isoformat() if r.discharge_ts else "",
            "diagnosis_code": r.diagnosis_code or "",
            "total_claimed": float(r.total_claimed or 0),
            "is_fraud": int(r.is_fraud or 0),
            "fraud_type": r.fraud_type or "clean",
        }
        claims_list.append(claim_dict)

        # 1. Claimant node
        cid = r.claimant_id
        if cid not in nodes_dict:
            nodes_dict[cid] = NetworkNode(
                id=cid,
                label=r.claimant_name or cid,
                type="claimant",
                ring_id=ring.ring_id,
                risk_score=85.0 if r.is_fraud else 45.0,
                metadata={
                    "claimant_id": cid,
                    "phone": r.claimant_phone,
                    "city": r.city,
                    "claim_id": r.claim_id,
                    "amount": float(r.total_claimed or 0)
                }
            )

        # Edge to central node (if bank ring)
        if ring.type == "shared_bank_account":
            edges_list.append(NetworkEdge(
                source=cid,
                target=central_id,
                type="shares_account_with",
                label=f"₹{int(r.total_claimed or 0):,}",
                claim_id=r.claim_id,
                amount=float(r.total_claimed or 0)
            ))

        # 2. Doctor node
        did = r.doctor_id
        if did:
            if did not in nodes_dict:
                dnum = did[4:] if did.startswith("DOC-") else did
                nodes_dict[did] = NetworkNode(
                    id=did,
                    label=f"Dr. {dnum}",
                    type="doctor",
                    ring_id=ring.ring_id,
                    metadata={"doctor_id": did}
                )
            if ring.type == "shared_bank_account":
                edges_list.append(NetworkEdge(
                    source=cid,
                    target=did,
                    type="treated_by",
                    label="Treated by",
                    claim_id=r.claim_id
                ))
            else:
                # Ghost doctor ring: edge from doctor to claimant
                edges_list.append(NetworkEdge(
                    source=central_id,
                    target=cid,
                    type="treated_by",
                    label=r.city,
                    claim_id=r.claim_id,
                    amount=float(r.total_claimed or 0)
                ))

        # 3. Hospital node
        hid = r.hospital_id
        if hid:
            if hid not in nodes_dict:
                nodes_dict[hid] = NetworkNode(
                    id=hid,
                    label=r.hospital_name or hid,
                    type="hospital",
                    ring_id=ring.ring_id,
                    metadata={"hospital_id": hid, "city": r.city, "lat": r.lat, "lng": r.lng}
                )
            if ring.type == "shared_bank_account":
                edges_list.append(NetworkEdge(
                    source=cid,
                    target=hid,
                    type="admitted_to",
                    label=r.city,
                    claim_id=r.claim_id
                ))
            else:
                # Ghost doctor ring: edge from doctor to hospital
                edges_list.append(NetworkEdge(
                    source=central_id,
                    target=hid,
                    type="practiced_at",
                    label=r.city,
                    claim_id=r.claim_id
                ))

    return RingDetailResponse(
        ring=ring,
        nodes=list(nodes_dict.values()),
        edges=edges_list,
        claims=claims_list
    )


@router.get("/rings", response_model=GraphRingsResponse)
async def get_fraud_rings(
    ring_id: Optional[str] = Query(None, description="Optional ring ID to expand"),
    limit: int = Query(20, ge=5, le=100, description="Max claims to include in subgraph"),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Returns list of detected fraud rings in BigQuery, and builds the
    interactive network subgraph for the selected or top ring.
    """
    rings = _fetch_fraud_rings()
    if not rings:
        return GraphRingsResponse(rings=[], selected_ring=None)

    # Find the target ring
    selected_summary: Optional[FraudRingSummary] = None
    if ring_id:
        selected_summary = next((r for r in rings if r.ring_id.upper() == ring_id.upper()), None)

    if not selected_summary:
        selected_summary = rings[0]

    detail = _build_subgraph_for_ring(selected_summary, limit=limit)
    return GraphRingsResponse(rings=rings, selected_ring=detail)


@router.get("/rings/{ring_id}", response_model=RingDetailResponse)
async def get_single_ring(
    ring_id: str,
    limit: int = Query(20, ge=5, le=100),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Returns the full subgraph and claim member list for a specific fraud ring."""
    rings = _fetch_fraud_rings()
    target = next((r for r in rings if r.ring_id.upper() == ring_id.upper()), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Fraud ring '{ring_id}' not found.")

    return _build_subgraph_for_ring(target, limit=limit)
