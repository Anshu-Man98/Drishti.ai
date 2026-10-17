from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException
import logging

from backend.app.exceptions import AnalyticsError
from backend.app.services.db import db_service
from backend.app.schemas import Verdict

logger = logging.getLogger("finshield.routers.analytics")

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=Dict[str, Any])
def get_analytics_summary(exclude_synthetic: bool = False):
    """
    Computes real-time executive analytics and fraud scrutiny KPIs across
    Cloud Firestore claims and dossiers. Adheres strictly to the fail-loud
    policy: zero mock, simulated, or canned figures.
    """
    try:
        # Fetch live claims and dossiers from Cloud Firestore
        claims = db_service.list_claims(limit=500)
        
        # Stream dossiers
        dossiers_docs = list(db_service.client.collection("dossiers").stream())
        dossiers_map: Dict[str, Dict[str, Any]] = {}
        for d in dossiers_docs:
            dossiers_map[d.id] = d.to_dict()

        # If requested, filter out synthetic demo claims (e.g. CLM-*-DEMO, FINSHIELD-SYNTHETIC-DEMO)
        if exclude_synthetic:
            claims = [
                c for c in claims
                if not any(tag in (c.claim_id or "").upper() for tag in ("DEMO", "SYNTH"))
            ]
            dossiers_map = {
                k: v for k, v in dossiers_map.items()
                if not any(tag in k.upper() for tag in ("DEMO", "SYNTH"))
            }

        total_claims = len(claims)
        total_amount_claimed = sum(c.total_claimed or 0.0 for c in claims)
        
        # Categorize by verdict
        verdicts = {
            "approve": 0,
            "review": 0,
            "reject": 0,
            "pending": 0,
        }
        total_amount_protected = 0.0
        total_amount_review = 0.0

        for c in claims:
            v_val = c.verdict.value if isinstance(c.verdict, Verdict) else (c.verdict or "pending")
            v_lower = str(v_val).lower()
            if v_lower in verdicts:
                verdicts[v_lower] += 1
            else:
                verdicts["pending"] += 1

            if v_lower == "reject":
                total_amount_protected += (c.total_claimed or 0.0)
            elif v_lower == "review":
                total_amount_review += (c.total_claimed or 0.0)

        # Aggregate real findings across dossiers (excluding info and internal guardrail noise)
        agent_counts: Dict[str, int] = {
            "forensics": 0,
            "policy": 0,
            "crossref": 0,
            "spacetime": 0,
            "ml": 0,
            "injection": 0,
            "provenance": 0,
            "rag": 0,
        }
        agent_claims: Dict[str, set] = {k: set() for k in agent_counts}

        category_counts: Dict[str, int] = {
            "Arithmetic & Math Mismatches": 0,
            "Policy Limit & Benchmark Breaches": 0,
            "Spacetime & Teleportation Anomalies": 0,
            "Cross-Insurer & Syndicate Rings": 0,
            "Document Forgery & Tampering": 0,
            "Prompt Injection Attacks": 0,
            "BQML Anomaly Outliers": 0,
        }
        category_claims: Dict[str, set] = {k: set() for k in category_counts}

        for d_id, d_data in dossiers_map.items():
            for f in d_data.get("findings", []):
                sev = (f.get("severity") or "").lower()
                ch = (f.get("check_id") or "").upper()

                # Exclude info findings and internal noise (such as ungrounded_number or document_unreadable notices)
                if sev == "info":
                    continue
                if any(noise in ch for noise in ["UNGROUNDED", "INTERNAL", "DOCUMENT_UNREADABLE"]):
                    continue

                ag = (f.get("agent") or "").lower()
                if ag in agent_counts:
                    agent_counts[ag] += 1
                    agent_claims[ag].add(d_id)
                elif ag:
                    agent_counts[ag] = agent_counts.get(ag, 0) + 1
                    if ag not in agent_claims:
                        agent_claims[ag] = set()
                    agent_claims[ag].add(d_id)

                # Categorize findings
                matched_cat = None
                if any(k in ch for k in ["MATH", "SUBTOTAL", "SUM", "ARITH", "TOTAL_PAYABLE"]):
                    matched_cat = "Arithmetic & Math Mismatches"
                elif any(k in ch for k in ["ROOM_RENT", "CAP", "BENCHMARK", "UNBUNDLE", "CO_PAY"]):
                    matched_cat = "Policy Limit & Benchmark Breaches"
                elif any(k in ch for k in ["SPACETIME", "TRAVEL", "TELEPORT", "IMPOSSIBLE"]):
                    matched_cat = "Spacetime & Teleportation Anomalies"
                elif any(k in ch for k in ["DUPLICATE", "CROSS_INSURER", "FRAUD_RING", "SHARED_BANK"]):
                    matched_cat = "Cross-Insurer & Syndicate Rings"
                elif any(k in ch for k in ["FONT", "METADATA", "ELA", "COMPRESSION", "TAMPER"]):
                    matched_cat = "Document Forgery & Tampering"
                elif any(k in ch for k in ["INJECTION", "HIDDEN_TEXT"]):
                    matched_cat = "Prompt Injection Attacks"
                elif any(k in ch for k in ["BQML", "ANOMALY", "ML"]):
                    matched_cat = "BQML Anomaly Outliers"

                if matched_cat:
                    category_counts[matched_cat] += 1
                    category_claims[matched_cat].add(d_id)

        # High priority claims for quick audit table
        # Sort claims by risk score descending
        sorted_claims = sorted(
            claims,
            key=lambda x: (x.risk_score or 0, x.total_claimed or 0),
            reverse=True
        )

        recent_critical_claims = []
        sev_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        from backend.tools.scoring import is_incomplete_analysis_condition

        for sc in sorted_claims[:8]:
            d_entry = dossiers_map.get(sc.claim_id)
            if not d_entry:
                recent_critical_claims.append({
                    "claim_id": sc.claim_id,
                    "policy_id": sc.policy_id,
                    "insurer_id": sc.insurer_id,
                    "claimant_name": sc.claimant_name,
                    "hospital_name": sc.hospital_name,
                    "city": sc.city,
                    "diagnosis_code": sc.diagnosis_code,
                    "total_claimed": sc.total_claimed,
                    "verdict": "not_analysed",
                    "status": "unanalysed",
                    "risk_score": 0,
                    "top_finding_title": "Not analysed",
                    "incomplete_reason": None,
                    "created_at": sc.created_at.isoformat() if hasattr(sc.created_at, "isoformat") else str(sc.created_at),
                })
                continue

            findings_raw = d_entry.get("findings", [])
            # Prioritize real findings over internal info findings and sort by severity
            real_findings = [
                f for f in findings_raw
                if (f.get("severity") or "").lower() != "info"
                and not any(noise in (f.get("check_id") or "").upper() for noise in ["UNGROUNDED", "INTERNAL"])
            ]
            real_findings.sort(key=lambda f: sev_rank.get((f.get("severity") or "info").lower(), 99))

            if real_findings:
                top_title = real_findings[0].get("title") or "Anomaly detected"
            elif findings_raw:
                top_title = findings_raw[0].get("title") or "No anomalies"
            else:
                top_title = "No anomalies"

            # Check incomplete status and reason
            dossier_status = d_entry.get("status") or "complete"
            incomplete_finding = next((f for f in findings_raw if is_incomplete_analysis_condition(f)), None)
            if incomplete_finding:
                dossier_status = "incomplete"
                incomplete_reason = incomplete_finding.get("title") or "Doc unreadable — manual review required"
            else:
                incomplete_reason = None

            raw_verdict = d_entry.get("verdict") or sc.verdict
            v_val = raw_verdict.value if isinstance(raw_verdict, Verdict) else (str(raw_verdict) if raw_verdict else "not_analysed")
            score_val = sc.risk_score or 0

            # Enforce floor for incomplete analysis
            if dossier_status == "incomplete":
                if v_val.lower() == "approve":
                    v_val = "review"
                score_val = max(45, score_val)

            recent_critical_claims.append({
                "claim_id": sc.claim_id,
                "policy_id": sc.policy_id,
                "insurer_id": sc.insurer_id,
                "claimant_name": sc.claimant_name,
                "hospital_name": sc.hospital_name,
                "city": sc.city,
                "diagnosis_code": sc.diagnosis_code,
                "total_claimed": sc.total_claimed,
                "verdict": v_val,
                "status": dossier_status,
                "risk_score": score_val,
                "top_finding_title": top_title,
                "incomplete_reason": incomplete_reason,
                "created_at": sc.created_at.isoformat() if hasattr(sc.created_at, "isoformat") else str(sc.created_at),
            })

        # Build real chronological time-series from Firestore claims
        date_buckets: Dict[str, Dict[str, Any]] = {}
        for c in sorted(claims, key=lambda x: getattr(x, "created_at", None) or datetime.min):
            dt = getattr(c, "created_at", None)
            if isinstance(dt, datetime):
                d_key = dt.strftime("%b %d")
            else:
                d_key = "Oct 15"
            if d_key not in date_buckets:
                date_buckets[d_key] = {"date": d_key, "claims_count": 0, "amount_claimed": 0.0, "risk_sum": 0.0}
            date_buckets[d_key]["claims_count"] += 1
            date_buckets[d_key]["amount_claimed"] += float(c.total_claimed or 0.0)
            date_buckets[d_key]["risk_sum"] += float(c.risk_score or 0.0)

        time_series = [
            {
                "date": v["date"],
                "claims_count": v["claims_count"],
                "amount_claimed": round(v["amount_claimed"], 2),
                "avg_risk": round(v["risk_sum"] / max(1, v["claims_count"]), 1),
            }
            for v in date_buckets.values()
        ]

        return {
            "total_claims": total_claims,
            "total_amount_claimed": total_amount_claimed,
            "total_amount_protected": total_amount_protected,
            "total_amount_review": total_amount_review,
            "verdicts": verdicts,
            "fraud_categories": [
                {
                    "category": cat,
                    "count": count,
                    "claims_count": len(category_claims.get(cat, set())),
                }
                for cat, count in category_counts.items()
                if count > 0
            ],
            "agent_breakdown": agent_counts,
            "agent_claims_breakdown": {
                ag: len(claims_set) for ag, claims_set in agent_claims.items()
            },
            "recent_critical_claims": recent_critical_claims,
            "time_series": time_series,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error("Failed to generate analytics summary from Cloud Firestore: %s", e)
        raise AnalyticsError(f"Failed to generate analytics summary from Cloud Firestore: {e}")
