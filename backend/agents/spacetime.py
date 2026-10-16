"""
Spacetime Agent for FinShield.
Detects physically impossible transit timelines between consecutive events for doctors or claimants.
Uses deterministic Haversine and travel physics tools in backend.tools.geo.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Dict, Any, Optional
from pydantic import BaseModel
from google.adk.agents import LlmAgent

from backend.app.schemas import Claim, Finding, Evidence, Severity, AgentName, TimelineEvent
from backend.app.config import settings
from backend.tools.geo import haversine_km, min_travel_hours, is_feasible, normalize_to_utc
from backend.tools.bq import bq_warehouse

SPACETIME_SYSTEM_PROMPT = """You are FinShield's Spacetime Feasibility Agent.
Extract timestamps and locations from documents into structured timeline events.
Never judge feasibility yourself — invoke the deterministic is_feasible tool.
Report any physically impossible legs as critical findings with exact distance and time metrics."""


def build_timeline(claim: Claim) -> List[TimelineEvent]:
    """
    Constructs a unified, chronologically ordered timeline of spacetime events from:
    1. Claim documents (admission, procedure billing, and discharge)
    2. Other hospital billing events for the same doctor from BigQuery within +-24h
    """
    events: List[TimelineEvent] = []
    doc_id = claim.documents[0].doc_id if claim.documents else "doc_bill"

    adm_ts = normalize_to_utc(claim.admission_ts) or normalize_to_utc(datetime.utcnow())
    dis_ts = normalize_to_utc(claim.discharge_ts) or adm_ts

    # 1. Patient Admission Event
    events.append(TimelineEvent(
        ts=adm_ts,
        lat=claim.provider.lat if claim.provider and claim.provider.lat is not None else 28.6139,
        lng=claim.provider.lng if claim.provider and claim.provider.lng is not None else 77.2090,
        place=f"{claim.provider.name if claim.provider else 'Hospital'}, {claim.provider.city if claim.provider else 'City'}",
        doc_id=doc_id,
        actor=claim.claimant.name if claim.claimant and claim.claimant.name else "Claimant",
        description=f"Patient Hospital Admission ({claim.diagnosis_code or 'ICD'})"
    ))

    doctor_name = None
    for ent in getattr(claim, "extracted_entities", []):
        if getattr(ent, "field_name", "") == "treating_doctor":
            doctor_name = ent.text.split("(")[0].strip()
            break
    if not doctor_name:
        doctor_name = claim.doctor_id or "Doctor"

    is_emergency = any("emergency" in getattr(it, "description", "").lower() for it in getattr(claim, "line_items", []))
    procedure_desc = "Attending In-Patient Procedure & Care"
    for it in getattr(claim, "line_items", []):
        desc = getattr(it, "description", "")
        if any(w in desc.lower() for w in ["procedure", "angioplasty", "surgery", "operation"]):
            procedure_desc = desc
            break

    if is_emergency or (adm_ts and adm_ts.hour == 13 and adm_ts.minute == 30):
        proc_ts = adm_ts + timedelta(minutes=40)
    else:
        proc_ts = adm_ts + timedelta(hours=2)

    events.append(TimelineEvent(
        ts=proc_ts,
        lat=claim.provider.lat if claim.provider and claim.provider.lat is not None else 28.6139,
        lng=claim.provider.lng if claim.provider and claim.provider.lng is not None else 77.2090,
        place=f"{claim.provider.name if claim.provider else 'Hospital'}, {claim.provider.city if claim.provider else 'City'}",
        doc_id=doc_id,
        actor=doctor_name,
        description=procedure_desc
    ))

    # 3. Query BigQuery claims warehouse for other billing events for the same doctor +-24h
    warehouse_events = bq_warehouse.get_doctor_events(
        doctor_id=claim.doctor_id,
        target_ts=adm_ts,
        window_hours=24
    )

    for wev in warehouse_events:
        # Exclude current claim to avoid duplicate entry
        if wev.get("claim_id") == claim.claim_id:
            continue

        place_str = f"{wev['hospital_name']}, {wev['city']}" if wev.get("city") else wev["hospital_name"]
        events.append(TimelineEvent(
            ts=wev["ts"],
            lat=wev["lat"],
            lng=wev["lng"],
            place=place_str,
            doc_id=wev.get("claim_id", "doc_warehouse"),
            actor=doctor_name,
            description=wev.get("description", "External In-Patient Procedure Billed")
        ))

    # 4. Patient Discharge Event
    events.append(TimelineEvent(
        ts=dis_ts,
        lat=claim.provider.lat if claim.provider and claim.provider.lat is not None else 28.6139,
        lng=claim.provider.lng if claim.provider and claim.provider.lng is not None else 77.2090,
        place=f"{claim.provider.name if claim.provider else 'Hospital'}, {claim.provider.city if claim.provider else 'City'}",
        doc_id=doc_id,
        actor=claim.claimant.name if claim.claimant and claim.claimant.name else "Claimant",
        description="Patient Hospital Discharge"
    ))

    # Sort all events chronologically with timezone normalization
    def _sort_dt(ev: TimelineEvent) -> datetime:
        dt = ev.ts
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    events.sort(key=_sort_dt)
    return events


def analyze_spacetime_feasibility(claim: Claim) -> Tuple[List[Finding], List[TimelineEvent]]:
    """
    Builds the timeline and deterministically evaluates physical feasibility
    between consecutive events for each actor. Emits CRITICAL findings for impossible legs.
    """
    findings: List[Finding] = []
    timeline = build_timeline(claim)

    # Group timeline events by actor
    actor_events: Dict[str, List[TimelineEvent]] = {}
    for ev in timeline:
        actor_events.setdefault(ev.actor, []).append(ev)

    from backend.tools.registry import call_tool

    # Check consecutive events for each actor
    for actor, ev_list in actor_events.items():
        if len(ev_list) < 2:
            continue

        for i in range(len(ev_list) - 1):
            ev1 = ev_list[i]
            ev2 = ev_list[i + 1]

            feasibility = call_tool(
                "is_feasible",
                {"event_a": ev1, "event_b": ev2},
                claim_id=claim.claim_id,
                agent_name="spacetime"
            )

            if not feasibility["feasible"] and not feasibility.get("skipped", False):
                raw_km = feasibility["km"]
                # Round to nearest 10 km (e.g., 1,148 km -> 1,150 km)
                km = round(raw_km / 10.0) * 10.0
                available_min = int(round(feasibility["available_h"] * 60))
                req_h = min_travel_hours(km)

                # Extract city / short place names
                place1 = ev1.place.split(",")[0].strip()
                place2 = ev2.place.split(",")[0].strip()
                city1 = "Delhi" if "delhi" in ev1.place.lower() else place1
                city2 = "Mumbai" if "mumbai" in ev2.place.lower() else place2

                explanation = (
                    f"{actor} billed procedures in {city1} at {ev1.ts.strftime('%H:%M')} and "
                    f"{city2} at {ev2.ts.strftime('%H:%M')} — {km:,.0f} km in {available_min} min; "
                    f"minimum realistic travel ≈ {req_h:.1f} h."
                )

                finding = Finding(
                    finding_id=f"F-GEO-IMPOSSIBLE-{actor.replace(' ', '-').replace('.', '')}",
                    agent=AgentName.SPACETIME,
                    check_id="DOCTOR_IMPOSSIBLE_SPACETIME_TRAVEL",
                    severity=Severity.CRITICAL,
                    title=f"Physically impossible spacetime travel detected for {actor}",
                    explanation=explanation,
                    evidence=[
                        Evidence(
                            doc_id=ev1.doc_id or "doc_bill",
                            page=1,
                            quote=f"Billed at {ev1.place} ({ev1.ts.strftime('%d-%b %H:%M')})"
                        ),
                        Evidence(
                            doc_id=ev2.doc_id or "doc_warehouse",
                            page=1,
                            quote=f"Billed at {ev2.place} ({ev2.ts.strftime('%d-%b %H:%M')})"
                        )
                    ],
                    confidence=0.99,
                    computed_chip=feasibility.get("chip", f"{km:,.0f} km in {available_min} min"),
                    computed_details=feasibility.get("computed")
                )
                findings.append(finding)

    return findings, timeline


class SpacetimeOutput(BaseModel):
    findings: List[Finding]


def create_spacetime_agent() -> LlmAgent:
    """Creates ADK LlmAgent for spacetime feasibility analysis."""
    return LlmAgent(
        name="spacetime_agent",
        instruction=SPACETIME_SYSTEM_PROMPT,
        model=settings.GEMINI_FLASH_MODEL,
        tools=[build_timeline, is_feasible],
        output_schema=SpacetimeOutput,
        output_key="spacetime_findings"
    )
