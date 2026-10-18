import json
import logging
import re
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from backend.app.config import settings
from backend.app.exceptions import CloudServiceError
from backend.app.schemas import (
    Claim, Dossier, ClaimSummary, ChatMessage, Finding, Severity, Evidence, AgentName
)

logger = logging.getLogger("finshield.services.db")

try:
    from google.cloud import firestore
    _firestore_available = True
except Exception:
    _firestore_available = False


class DatabaseService:
    """
    Cloud-native Firestore Database Service.
    All claims, dossiers, agent statuses, chat history, issuance records,
    duel rounds, and learned patterns live exclusively in Google Cloud Firestore.
    There is no local or in-memory fallback.
    """
    def __init__(self):
        self._fs_client = None
        self._init_client()

    def _init_client(self):
        if _firestore_available and settings.GCP_PROJECT:
            try:
                self._fs_client = firestore.Client(
                    project=settings.GCP_PROJECT,
                    database=settings.FIRESTORE_DATABASE
                )
            except Exception as e:
                self._fs_client = None
                if settings.REQUIRE_CLOUD_ON_STARTUP:
                    raise CloudServiceError(
                        service="firestore",
                        message=f"Failed to initialize Firestore client for project '{settings.GCP_PROJECT}': {e}",
                        retryable=True
                    )

    @property
    def client(self) -> Any:
        if self._fs_client is None:
            self._init_client()
        if self._fs_client is None:
            raise CloudServiceError(
                service="firestore",
                message="Cloud Firestore client is unavailable. Live Firestore connection required.",
                retryable=True
            )
        return self._fs_client

    def _call_fs(self, func: Any, *args: Any, timeout: float = 15.0, max_retries: Optional[int] = None, **kwargs: Any) -> Any:
        from backend.app.services.cloud_call import cloud_call
        retries = max_retries if max_retries is not None else settings.CLOUD_CALL_MAX_RETRIES
        return cloud_call(
            func,
            *args,
            service="firestore",
            timeout=timeout,
            max_retries=retries,
            **kwargs
        )

    def save_claim(self, claim: Claim) -> None:
        claim_dict = json.loads(claim.model_dump_json())
        claim_dict["created_at"] = datetime.utcnow().isoformat()
        try:
            self._call_fs(self.client.collection("claims").document(claim.claim_id).set, claim_dict, timeout=10.0)
        except Exception as e:
            if isinstance(e, CloudServiceError):
                raise
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to save claim '{claim.claim_id}' to Firestore: {e}",
                retryable=True
            )

    def get_claim(self, claim_id: str) -> Optional[Claim]:
        try:
            doc = self._call_fs(self.client.collection("claims").document(claim_id).get, timeout=10.0)
            if doc.exists:
                return Claim.model_validate(doc.to_dict())
            return None
        except Exception as e:
            if isinstance(e, CloudServiceError):
                raise
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to get claim '{claim_id}' from Firestore: {e}",
                retryable=True
            )

    CATEGORY_MAPPINGS = {
        "Arithmetic & Math Mismatches": ["MATH", "SUBTOTAL", "SUM", "ARITH", "TOTAL_PAYABLE"],
        "Policy Limit & Benchmark Breaches": ["ROOM_RENT", "CAP", "BENCHMARK", "UNBUNDLE", "CO_PAY"],
        "Spacetime & Teleportation Anomalies": ["SPACETIME", "TRAVEL", "TELEPORT", "IMPOSSIBLE"],
        "Cross-Insurer & Syndicate Rings": ["DUPLICATE", "CROSS_INSURER", "FRAUD_RING", "SHARED_BANK"],
        "Document Forgery & Tampering": ["FONT", "METADATA", "ELA", "COMPRESSION", "TAMPER"],
        "Prompt Injection Attacks": ["INJECTION", "HIDDEN_TEXT"],
        "BQML Anomaly Outliers": ["BQML", "ANOMALY", "ML"],
    }

    @classmethod
    def _claim_matches_category(cls, dossier_data: Optional[Dict[str, Any]], target_category: str) -> bool:
        if not dossier_data or not target_category:
            return False
        cat_lower = target_category.strip().lower()

        # Match all anomalies (e.g. "all_anomalies", "all anomalies")
        if cat_lower in ("all_anomalies", "all anomalies", "anomalies", "all-anomalies"):
            for f in dossier_data.get("findings", []):
                sev = (f.get("severity") or "").lower()
                if sev == "info":
                    continue
                ch = f"{f.get('check_id') or ''} {f.get('category') or ''} {f.get('title') or ''}".upper()
                if any(noise in ch for noise in ["UNGROUNDED", "INTERNAL", "DOCUMENT_UNREADABLE"]):
                    continue
                for keywords in cls.CATEGORY_MAPPINGS.values():
                    if any(k in ch for k in keywords):
                        return True
            return False

        # Specific category keyword match
        target_keywords = None
        for cat_name, keywords in cls.CATEGORY_MAPPINGS.items():
            if cat_lower == cat_name.lower() or cat_lower in cat_name.lower() or cat_name.lower() in cat_lower:
                target_keywords = keywords
                break

        if target_keywords:
            for f in dossier_data.get("findings", []):
                sev = (f.get("severity") or "").lower()
                if sev == "info":
                    continue
                ch = f"{f.get('check_id') or ''} {f.get('category') or ''} {f.get('title') or ''}".upper()
                if any(noise in ch for noise in ["UNGROUNDED", "INTERNAL", "DOCUMENT_UNREADABLE"]):
                    continue
                if any(k in ch for k in target_keywords):
                    return True
            return False

        # Substring fallback
        cat_upper = target_category.strip().upper()
        for f in dossier_data.get("findings", []):
            sev = (f.get("severity") or "").lower()
            if sev == "info":
                continue
            ch = f"{f.get('check_id') or ''} {f.get('category') or ''} {f.get('title') or ''}".upper()
            if cat_upper in ch:
                return True
        return False

    def list_claims_paged(
        self,
        limit: int = 50,
        offset: int = 0,
        verdict: Optional[str] = None,
        sort_by: Optional[str] = "created_at",
        sort_order: Optional[str] = "desc",
        search: Optional[str] = None,
        include_synthetic: bool = False,
        exclude_synthetic: Optional[bool] = None,
        category: Optional[str] = None,
    ) -> tuple[List[ClaimSummary], int]:
        try:
            docs = self._call_fs(lambda: list(self.client.collection("claims").stream()), timeout=20.0)
            if not docs:
                return [], 0

            dossier_refs = [self.client.collection("dossiers").document(d.to_dict().get("claim_id", d.id)) for d in docs]
            dossiers_map: Dict[str, Dict[str, Any]] = {}
            try:
                for d_doc in self._call_fs(lambda: list(self.client.get_all(dossier_refs)), timeout=20.0):
                    if d_doc.exists:
                        dossiers_map[d_doc.id] = d_doc.to_dict()
            except Exception as e:
                logger.warning("Batch get_all failed for dossiers, falling back to individual gets: %s", e)
                for ref in dossier_refs:
                    try:
                        d_doc = self._call_fs(ref.get, timeout=5.0)
                        if d_doc.exists:
                            dossiers_map[d_doc.id] = d_doc.to_dict()
                    except Exception as err:
                        logger.warning("Could not fetch individual dossier for %s: %s", getattr(ref, "id", "unknown"), err)

            summaries: List[ClaimSummary] = []
            for doc in docs:
                c = doc.to_dict()
                cid = c.get("claim_id", doc.id)
                d_data = dossiers_map.get(cid)
                verdict_val = d_data.get("verdict") if d_data else None
                risk_score = d_data.get("risk_score") if d_data else None
                source_val = c.get("source") or ("demo" if any(t in cid.upper() for t in ("DEMO", "SYNTH")) else "duel" if "DUEL" in cid.upper() else "upload")
                summaries.append(ClaimSummary(
                    claim_id=cid,
                    policy_id=c.get("policy_id") or "POL-UNKNOWN",
                    insurer_id=c.get("insurer_id") or "INS-UNKNOWN",
                    claimant_name=c.get("claimant", {}).get("name") if c.get("claimant") else "Unknown",
                    hospital_name=c.get("provider", {}).get("name") if c.get("provider") else "Unknown",
                    city=c.get("provider", {}).get("city") if c.get("provider") else "Unknown",
                    total_claimed=c.get("total_claimed") or 0.0,
                    admission_ts=c.get("admission_ts") or datetime.utcnow(),
                    discharge_ts=c.get("discharge_ts") or datetime.utcnow(),
                    diagnosis_code=c.get("diagnosis_code") or "Z00.0",
                    doc_count=len(c.get("documents", [])),
                    created_at=c.get("created_at") or datetime.utcnow(),
                    verdict=verdict_val,
                    risk_score=risk_score,
                    source=source_val
                ))

            # Filter synthetic/demo/duel claims unless include_synthetic is True
            if exclude_synthetic is not None:
                should_include = not exclude_synthetic
            else:
                should_include = include_synthetic

            if not should_include:
                summaries = [
                    s for s in summaries
                    if s.source == "upload"
                    and not any(tag in s.claim_id.upper() for tag in ("-DEMO", "DEMO-", "-SYNTH", "SYNTH-", "-DUEL", "DUEL-"))
                ]

            # Filter by search string
            if search:
                s_lower = search.strip().lower()
                summaries = [
                    s for s in summaries
                    if s_lower in s.claim_id.lower()
                    or s_lower in s.claimant_name.lower()
                    or s_lower in s.hospital_name.lower()
                    or s_lower in s.city.lower()
                    or s_lower in s.diagnosis_code.lower()
                    or s_lower in s.policy_id.lower()
                    or s_lower in s.insurer_id.lower()
                ]

            # Filter by verdict
            if verdict and verdict.lower() != "all":
                v_target = verdict.lower()
                if v_target == "unreviewed":
                    summaries = [s for s in summaries if not s.verdict]
                else:
                    summaries = [
                        s for s in summaries
                        if s.verdict and (s.verdict.value.lower() if hasattr(s.verdict, "value") else str(s.verdict).lower()) == v_target
                    ]

            # Filter by anomaly category / vector
            if category and category.strip():
                summaries = [
                    s for s in summaries
                    if self._claim_matches_category(dossiers_map.get(s.claim_id), category)
                ]

            # Sort records
            is_desc = (sort_order or "desc").lower() == "desc"
            if sort_by == "total_claimed":
                summaries.sort(key=lambda x: x.total_claimed or 0.0, reverse=is_desc)
            elif sort_by == "risk_score":
                summaries.sort(key=lambda x: x.risk_score or 0, reverse=is_desc)
            elif sort_by == "claimant_name":
                summaries.sort(key=lambda x: (x.claimant_name or "").lower(), reverse=is_desc)
            elif sort_by == "hospital_name":
                summaries.sort(key=lambda x: (x.hospital_name or "").lower(), reverse=is_desc)
            elif sort_by == "diagnosis_code":
                summaries.sort(key=lambda x: (x.diagnosis_code or "").lower(), reverse=is_desc)
            elif sort_by == "claim_id":
                summaries.sort(key=lambda x: x.claim_id, reverse=is_desc)
            else: # Default: created_at
                summaries.sort(key=lambda x: str(x.created_at or ""), reverse=is_desc)

            total_count = len(summaries)
            paged = summaries[offset : offset + limit]
            return paged, total_count
        except Exception as e:
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to list claims from Firestore: {e}",
                retryable=True
            )

    def list_claims(self, limit: int = 50, offset: int = 0, include_synthetic: bool = True, category: Optional[str] = None) -> List[ClaimSummary]:
        paged, _ = self.list_claims_paged(limit=limit, offset=offset, include_synthetic=include_synthetic, category=category)
        return paged

    def save_dossier(self, dossier: Dossier) -> None:
        dossier_dict = json.loads(dossier.model_dump_json())
        dossier_dict["created_at"] = datetime.utcnow().isoformat()
        try:
            self._call_fs(self.client.collection("dossiers").document(dossier.claim_id).set, dossier_dict, timeout=10.0)
        except Exception as e:
            if isinstance(e, CloudServiceError):
                raise
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to save dossier '{dossier.claim_id}' to Firestore: {e}",
                retryable=True
            )

    def get_dossier(self, claim_id: str) -> Optional[Dossier]:
        try:
            doc = self._call_fs(self.client.collection("dossiers").document(claim_id).get, timeout=10.0)
            if doc.exists:
                return Dossier.model_validate(doc.to_dict())
            return None
        except Exception as e:
            if isinstance(e, CloudServiceError):
                raise
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to get dossier '{claim_id}' from Firestore: {e}",
                retryable=True
            )

    def set_agent_status(self, claim_id: str, agent_name: str, status: str) -> None:
        now = datetime.utcnow().isoformat()
        try:
            self._call_fs(
                self.client.collection("claims").document(claim_id).collection("agent_status").document(agent_name).set,
                {
                    "status": status,
                    "agent_name": agent_name,
                    "updated_at": now
                },
                timeout=5.0,
                max_retries=1
            )
        except Exception as e:
            logger.warning(
                "Failed to update agent status for '%s/%s' in Firestore: %s",
                claim_id, agent_name, e
            )

    def get_agent_statuses(self, claim_id: str) -> Dict[str, str]:
        canonical_agents = [
            "forensics",
            "policy",
            "crossref",
            "spacetime",
            "ml",
            "injection",
            "provenance",
            "rag",
        ]
        statuses = {agent: "idle" for agent in canonical_agents}
        try:
            docs = self._call_fs(
                lambda: list(self.client.collection("claims").document(claim_id).collection("agent_status").stream()),
                timeout=10.0
            )
            for doc in docs:
                d = doc.to_dict()
                if "status" in d:
                    statuses[doc.id] = d["status"]

            # If no agent status docs were written yet, check if dossier exists to reflect completed state
            if not docs:
                dossier = self.get_dossier(claim_id)
                if dossier:
                    for agent in canonical_agents:
                        if any(f.check_id.startswith(f"AGENT_FAILED:{agent}") for f in dossier.findings):
                            statuses[agent] = "error"
                        else:
                            statuses[agent] = "done"

            return statuses
        except Exception as e:
            if isinstance(e, CloudServiceError):
                raise
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to get agent statuses for '{claim_id}' from Firestore: {e}",
                retryable=True
            )

    def save_chat_message(
        self,
        claim_id: str,
        role: str,
        content: str,
        cited_finding_ids: Optional[List[str]] = None
    ) -> None:
        now = datetime.utcnow().isoformat()
        msg_dict = {
            "role": role,
            "content": content,
            "cited_finding_ids": cited_finding_ids or [],
            "created_at": now
        }
        try:
            self._call_fs(
                self.client.collection("claims").document(claim_id).collection("chat_messages").add,
                msg_dict,
                timeout=10.0
            )
        except Exception as e:
            if isinstance(e, CloudServiceError):
                raise
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to save chat message for '{claim_id}' to Firestore: {e}",
                retryable=True
            )

    def get_chat_history(self, claim_id: str) -> List[ChatMessage]:
        try:
            docs = self._call_fs(
                lambda: list(
                    self.client.collection("claims")
                    .document(claim_id)
                    .collection("chat_messages")
                    .order_by("created_at")
                    .stream()
                ),
                timeout=10.0
            )
            messages = []
            for doc in docs:
                d = doc.to_dict()
                messages.append(ChatMessage(
                    role=d.get("role", "assistant"),
                    content=d.get("content", ""),
                    cited_finding_ids=d.get("cited_finding_ids", []),
                    created_at=datetime.fromisoformat(d.get("created_at", datetime.utcnow().isoformat()))
                ))
            return messages
        except Exception as e:
            if isinstance(e, CloudServiceError):
                raise
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to get chat history for '{claim_id}' from Firestore: {e}",
                retryable=True
            )

    def record_issuance(
        self,
        doc_id: str,
        claim_id: str,
        doc_type: str,
        amount_paise: int,
        content_hash: str,
        signature: str,
        issued_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        issued_at_val = issued_at or datetime.utcnow()
        record = {
            "doc_id": doc_id,
            "claim_id": claim_id,
            "doc_type": doc_type,
            "amount_paise": amount_paise,
            "content_hash": content_hash,
            "signature": signature,
            "issued_at": issued_at_val.isoformat(),
            "metadata": metadata or {}
        }
        try:
            self._call_fs(
                self.client.collection("issuance_ledger").document(doc_id).set,
                record,
                timeout=10.0
            )
        except Exception as e:
            if isinstance(e, CloudServiceError):
                raise
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to record issuance '{doc_id}' in Firestore: {e}",
                retryable=True
            )

    def get_issuance(self, doc_id: str) -> Optional[Dict[str, Any]]:
        try:
            doc = self._call_fs(self.client.collection("issuance_ledger").document(doc_id).get, timeout=10.0)
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            if isinstance(e, CloudServiceError):
                raise
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to get issuance record '{doc_id}' from Firestore: {e}",
                retryable=True
            )

    def get_issuance_for_claim(self, claim_id: str, doc_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        try:
            coll = self.client.collection("issuance_ledger")
            query = coll.where(filter=firestore.FieldFilter("claim_id", "==", claim_id))
            if doc_type:
                query = query.where(filter=firestore.FieldFilter("doc_type", "==", doc_type))
            docs = self._call_fs(lambda: [doc.to_dict() for doc in query.stream()], timeout=10.0)
            if not docs:
                return None
            docs.sort(key=lambda d: str(d.get("issued_at", "")), reverse=True)
            return docs[0]
        except Exception as e:
            if isinstance(e, CloudServiceError):
                raise
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to query issuance ledger for '{claim_id}' from Firestore: {e}",
                retryable=True
            )

    def save_duel_round(self, duel_id: str, round_number: int, round_data: Dict[str, Any]) -> None:
        try:
            self._call_fs(
                self.client.collection("duels").document(duel_id).collection("rounds").document(str(round_number)).set,
                round_data,
                timeout=10.0
            )
        except Exception as e:
            if isinstance(e, CloudServiceError):
                raise
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to save duel round '{duel_id}/{round_number}' to Firestore: {e}",
                retryable=True
            )

    def get_duel_rounds(self, duel_id: str) -> List[Dict[str, Any]]:
        try:
            docs = self._call_fs(
                lambda: [doc.to_dict() for doc in self.client.collection("duels").document(duel_id).collection("rounds").order_by("round_number").stream()],
                timeout=10.0
            )
            return docs
        except Exception as e:
            if isinstance(e, CloudServiceError):
                raise
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to get duel rounds for '{duel_id}' from Firestore: {e}",
                retryable=True
            )

    def save_duel_meta(self, duel_id: str, meta_data: Dict[str, Any]) -> None:
        try:
            self._call_fs(lambda: self.client.collection("duels").document(duel_id).set(meta_data, merge=True), timeout=10.0)
        except TypeError:
            try:
                self._call_fs(lambda: self.client.collection("duels").document(duel_id).set(meta_data), timeout=10.0)
            except Exception as e:
                logger.error("Failed to save duel meta for '%s': %s", duel_id, e)
        except Exception as e:
            logger.error("Failed to save duel meta for '%s': %s", duel_id, e)

    def get_duel_meta(self, duel_id: str) -> Optional[Dict[str, Any]]:
        try:
            doc = self._call_fs(self.client.collection("duels").document(duel_id).get, timeout=10.0)
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            logger.error("Failed to get duel meta for '%s': %s", duel_id, e)
            return None

    def save_learned_pattern(self, pattern: Dict[str, Any]) -> None:
        pid = pattern.get("pattern_id") or f"PAT-LEARNED-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        pattern["pattern_id"] = pid
        try:
            self._call_fs(
                self.client.collection("learned_patterns").document(pid).set,
                pattern,
                timeout=10.0
            )
        except Exception as e:
            if isinstance(e, CloudServiceError):
                raise
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to save learned pattern '{pid}' to Firestore: {e}",
                retryable=True
            )

    def get_learned_patterns(self) -> List[Dict[str, Any]]:
        try:
            docs = self._call_fs(lambda: [doc.to_dict() for doc in self.client.collection("learned_patterns").stream()], timeout=10.0)
            return docs
        except Exception as e:
            if isinstance(e, CloudServiceError):
                raise
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to get learned patterns from Firestore: {e}",
                retryable=True
            )

    def find_firestore_duplicates(self, claim: Claim) -> List[Finding]:
        """
        Cross-claim duplicate detector for claims stored in Firestore.
        Detects:
        1. Exact document SHA-256 match -> EXACT_DUPLICATE_BILL (CRITICAL)
        2. Same bill/invoice number + hospital + total + patient -> EXACT_DUPLICATE_BILL (CRITICAL)
        3. Same patient + hospital + overlapping admission dates (+-3d) + similar total (+-5%) -> EXACT_DUPLICATE_BILL (HIGH)

        Excludes the claim itself and respects the `source` marker:
        - Duel claims are adversarial learning mutations; a duel mutation of a base claim is not a duplicate.
        """
        from backend.app.schemas import Finding, Severity, AgentName, Evidence
        from backend.tools.date_utils import parse_flexible_date

        findings: List[Finding] = []
        if not claim or not claim.claim_id:
            return findings

        # Source marker rule: duel claims are adversarial simulations mutating a base claim.
        if getattr(claim, "source", "") == "duel":
            return findings

        current_sha256s = {
            d.sha256.lower().strip() for d in (claim.documents or [])
            if getattr(d, "sha256", None)
        }

        current_bill_no = (
            (claim.metadata or {}).get("bill_no") or
            (claim.metadata or {}).get("invoice_number") or
            (claim.metadata or {}).get("bill_number")
        )
        if not current_bill_no and claim.documents:
            for cd in claim.documents:
                fn = getattr(cd, "filename", "") or ""
                if fn:
                    m_inv = re.search(r"(?:INV|BILL)-[A-Za-z0-9\-]+", fn, re.IGNORECASE)
                    if m_inv:
                        current_bill_no = m_inv.group(0)
                        break

        current_hospital = claim.provider.name.strip().lower() if claim.provider and claim.provider.name else ""
        current_patient = claim.claimant.name.strip().lower() if claim.claimant and claim.claimant.name else ""
        current_total = float(claim.total_claimed or 0.0)
        current_adm = parse_flexible_date(claim.admission_ts)
        curr_created = parse_flexible_date(getattr(claim, "created_at", None))

        try:
            docs = self._call_fs(lambda: list(self.client.collection("claims").stream()), timeout=15.0)
        except Exception as e:
            logger.warning("Failed to stream Firestore claims for duplicate check: %s", e)
            return findings

        for d_doc in docs:
            c_dict = d_doc.to_dict()
            if not isinstance(c_dict, dict):
                continue
            existing_id = c_dict.get("claim_id", d_doc.id)

            # 1. Self-exclusion
            if existing_id == claim.claim_id:
                continue

            # 2. Source marker rules:
            # - Duel claims are adversarial simulations mutating a base claim. They do not flag duplicates.
            existing_source = c_dict.get("source", "")
            if existing_source == "duel":
                continue

            # - Demo claims are ground-truth benchmark claims. A demo claim cannot be a duplicate of a user upload.
            if getattr(claim, "source", "") == "demo" and existing_source != "demo":
                continue

            # - Temporal order: an earlier claim cannot be a duplicate of a claim submitted later.
            exist_created = parse_flexible_date(c_dict.get("created_at"))
            if curr_created and exist_created and exist_created > curr_created:
                continue

            existing_docs = c_dict.get("documents", []) or []
            existing_sha256s = {
                doc_item.get("sha256", "").lower().strip() for doc_item in existing_docs
                if isinstance(doc_item, dict) and doc_item.get("sha256")
            }

            existing_claimant = c_dict.get("claimant") or {}
            existing_patient = (existing_claimant.get("name") or "").strip().lower()

            existing_provider = c_dict.get("provider") or {}
            existing_hospital = (existing_provider.get("name") or "").strip().lower()

            existing_meta = c_dict.get("metadata") or {}
            existing_bill_no = (
                existing_meta.get("bill_no") or
                existing_meta.get("invoice_number") or
                existing_meta.get("bill_number")
            )
            if not existing_bill_no and existing_docs:
                for ed in existing_docs:
                    fn = (ed.get("filename") or "") if isinstance(ed, dict) else (getattr(ed, "filename", "") or "")
                    if fn:
                        m_ex = re.search(r"(?:INV|BILL)-[A-Za-z0-9\-]+", fn, re.IGNORECASE)
                        if m_ex:
                            existing_bill_no = m_ex.group(0)
                            break

            existing_total = float(c_dict.get("total_claimed") or 0.0)
            existing_adm = parse_flexible_date(c_dict.get("admission_ts"))

            # Case A: Same document SHA-256 -> EXACT_DUPLICATE_BILL (CRITICAL)
            matched_shas = current_sha256s & existing_sha256s
            if matched_shas and any(s for s in matched_shas):
                matched_sha = next(iter(matched_shas))
                findings.append(Finding(
                    finding_id="F-XREF-FS-EXACT-DUP",
                    agent=AgentName.CROSSREF,
                    check_id="EXACT_DUPLICATE_BILL",
                    severity=Severity.CRITICAL,
                    title=f"Exact duplicate bill resubmitted: matches {existing_id}",
                    explanation=(
                        f"Uploaded bill file matches identical document (SHA-256: {matched_sha[:12]}...) "
                        f"previously submitted under claim '{existing_id}'. Resubmitting the identical document constitutes double-billing."
                    ),
                    evidence=[Evidence(doc_id="doc_main", page=1, quote=f"Matching SHA-256: {matched_sha[:16]} under claim {existing_id}")],
                    confidence=1.0,
                    computed_chip=f"Duplicate: {existing_id}",
                    computed_details={
                        "matching_claim_id": existing_id,
                        "matched_sha256": matched_sha,
                        "duplicate_type": "exact_document_sha256"
                    }
                ))
                return findings

            # Case B: Same bill/invoice number + hospital + total + patient -> near-exact duplicate (CRITICAL)
            if current_bill_no and existing_bill_no:
                norm_curr = re.sub(r"[^A-Za-z0-9]", "", current_bill_no.lower())
                norm_exist = re.sub(r"[^A-Za-z0-9]", "", existing_bill_no.lower())
                if norm_curr and norm_curr == norm_exist:
                    hosp_match = not current_hospital or not existing_hospital or (current_hospital in existing_hospital or existing_hospital in current_hospital)
                    tot_match = abs(current_total - existing_total) <= 1.0 or abs(current_total - existing_total) <= max(1.0, current_total * 0.01)
                    pat_match = not current_patient or not existing_patient or (current_patient in existing_patient or existing_patient in current_patient)
                    if hosp_match and tot_match and pat_match:
                        findings.append(Finding(
                            finding_id="F-XREF-FS-INVOICE-DUP",
                            agent=AgentName.CROSSREF,
                            check_id="EXACT_DUPLICATE_BILL",
                            severity=Severity.CRITICAL,
                            title=f"Duplicate invoice number resubmitted: {current_bill_no} (matches {existing_id})",
                            explanation=(
                                f"Invoice number '{current_bill_no}' was already claimed under '{existing_id}' "
                                f"for patient '{existing_patient.title() or 'Unknown'}' at '{existing_hospital.title() or 'the same facility'}' "
                                f"for ₹{existing_total:,.2f}. Resubmitting the same invoice number is double-billing."
                            ),
                            evidence=[Evidence(doc_id="doc_main", page=1, quote=f"Duplicate invoice {current_bill_no} in claim {existing_id}")],
                            confidence=1.0,
                            computed_chip=f"Duplicate Inv: {current_bill_no}",
                            computed_details={
                                "matching_claim_id": existing_id,
                                "invoice_number": current_bill_no,
                                "duplicate_type": "invoice_number_match"
                            }
                        ))
                        return findings

            # Case C: Same patient + hospital + overlapping admission dates + similar total -> possible duplicate (HIGH)
            if current_patient and existing_patient and current_adm and existing_adm:
                if (current_patient in existing_patient or existing_patient in current_patient):
                    if (current_hospital in existing_hospital or existing_hospital in current_hospital):
                        adm_diff_days = abs((current_adm - existing_adm).total_seconds())
                        if adm_diff_days <= 3 * 86400:  # within 3 days admission
                            tot_ratio = current_total / max(1.0, existing_total)
                            if 0.95 <= tot_ratio <= 1.05:  # within +/- 5% range
                                findings.append(Finding(
                                    finding_id="F-XREF-FS-OVERLAP-DUP",
                                    agent=AgentName.CROSSREF,
                                    check_id="EXACT_DUPLICATE_BILL",
                                    severity=Severity.HIGH,
                                    title=f"Possible duplicate claim with overlapping dates: matches {existing_id}",
                                    explanation=(
                                        f"Existing claim '{existing_id}' for patient '{existing_patient.title()}' at "
                                        f"'{existing_hospital.title()}' has overlapping hospitalization dates and similar claimed amount "
                                        f"(₹{existing_total:,.2f} vs ₹{current_total:,.2f})."
                                    ),
                                    evidence=[Evidence(doc_id="doc_main", page=1, quote=f"Overlapping claim {existing_id}: {existing_adm.strftime('%d-%b-%Y')} / ₹{existing_total:,.2f}")],
                                    confidence=0.90,
                                    computed_chip=f"Overlap: {existing_id}",
                                    computed_details={
                                        "matching_claim_id": existing_id,
                                        "duplicate_type": "patient_hospital_date_overlap"
                                    }
                                ))
                                return findings

        return findings


db_service = DatabaseService()

