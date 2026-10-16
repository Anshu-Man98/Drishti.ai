import json
from typing import List, Optional, Dict, Any
from datetime import datetime

from backend.app.config import settings
from backend.app.exceptions import CloudServiceError
from backend.app.schemas import Claim, Dossier, ClaimSummary, ChatMessage

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

    def save_claim(self, claim: Claim) -> None:
        claim_dict = json.loads(claim.model_dump_json())
        claim_dict["created_at"] = datetime.utcnow().isoformat()
        try:
            self.client.collection("claims").document(claim.claim_id).set(claim_dict)
        except Exception as e:
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to save claim '{claim.claim_id}' to Firestore: {e}",
                retryable=True
            )

    def get_claim(self, claim_id: str) -> Optional[Claim]:
        try:
            doc = self.client.collection("claims").document(claim_id).get()
            if doc.exists:
                return Claim.model_validate(doc.to_dict())
            return None
        except Exception as e:
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to get claim '{claim_id}' from Firestore: {e}",
                retryable=True
            )

    def list_claims(self, limit: int = 50, offset: int = 0) -> List[ClaimSummary]:
        try:
            docs = list(self.client.collection("claims").limit(limit).offset(offset).stream())
            if not docs:
                return []

            dossier_refs = [self.client.collection("dossiers").document(d.to_dict().get("claim_id", d.id)) for d in docs]
            dossiers_map: Dict[str, Dict[str, Any]] = {}
            try:
                for d_doc in self.client.get_all(dossier_refs):
                    if d_doc.exists:
                        dossiers_map[d_doc.id] = d_doc.to_dict()
            except Exception:
                for ref in dossier_refs:
                    try:
                        d_doc = ref.get()
                        if d_doc.exists:
                            dossiers_map[d_doc.id] = d_doc.to_dict()
                    except Exception:
                        pass

            summaries: List[ClaimSummary] = []
            for doc in docs:
                c = doc.to_dict()
                cid = c.get("claim_id", doc.id)
                d_data = dossiers_map.get(cid)
                verdict = d_data.get("verdict") if d_data else None
                risk_score = d_data.get("risk_score") if d_data else None
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
                    verdict=verdict,
                    risk_score=risk_score
                ))
            return summaries
        except Exception as e:
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to list claims from Firestore: {e}",
                retryable=True
            )

    def save_dossier(self, dossier: Dossier) -> None:
        dossier_dict = json.loads(dossier.model_dump_json())
        dossier_dict["created_at"] = datetime.utcnow().isoformat()
        try:
            self.client.collection("dossiers").document(dossier.claim_id).set(dossier_dict)
        except Exception as e:
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to save dossier '{dossier.claim_id}' to Firestore: {e}",
                retryable=True
            )

    def get_dossier(self, claim_id: str) -> Optional[Dossier]:
        try:
            doc = self.client.collection("dossiers").document(claim_id).get()
            if doc.exists:
                return Dossier.model_validate(doc.to_dict())
            return None
        except Exception as e:
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to get dossier '{claim_id}' from Firestore: {e}",
                retryable=True
            )

    def set_agent_status(self, claim_id: str, agent_name: str, status: str) -> None:
        now = datetime.utcnow().isoformat()
        try:
            self.client.collection("claims").document(claim_id).collection("agent_status").document(agent_name).set({
                "status": status,
                "agent_name": agent_name,
                "updated_at": now
            })
        except Exception as e:
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to update agent status for '{claim_id}/{agent_name}' in Firestore: {e}",
                retryable=True
            )

    def get_agent_statuses(self, claim_id: str) -> Dict[str, str]:
        statuses = {
            "forensics": "idle",
            "policy": "idle",
            "crossref": "idle",
            "spacetime": "idle",
            "injection": "idle",
            "provenance": "idle",
            "synthesizer": "idle"
        }
        try:
            docs = self.client.collection("claims").document(claim_id).collection("agent_status").stream()
            for doc in docs:
                d = doc.to_dict()
                if "status" in d:
                    statuses[doc.id] = d["status"]
            return statuses
        except Exception as e:
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
            self.client.collection("claims").document(claim_id).collection("chat_messages").add(msg_dict)
        except Exception as e:
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to save chat message for '{claim_id}' to Firestore: {e}",
                retryable=True
            )

    def get_chat_history(self, claim_id: str) -> List[ChatMessage]:
        try:
            docs = (
                self.client.collection("claims")
                .document(claim_id)
                .collection("chat_messages")
                .order_by("created_at")
                .stream()
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
            self.client.collection("issuance_ledger").document(doc_id).set(record)
        except Exception as e:
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to record issuance '{doc_id}' in Firestore: {e}",
                retryable=True
            )

    def get_issuance(self, doc_id: str) -> Optional[Dict[str, Any]]:
        try:
            doc = self.client.collection("issuance_ledger").document(doc_id).get()
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
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
            docs = [doc.to_dict() for doc in query.stream()]
            if not docs:
                return None
            docs.sort(key=lambda d: str(d.get("issued_at", "")), reverse=True)
            return docs[0]
        except Exception as e:
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to query issuance ledger for '{claim_id}' from Firestore: {e}",
                retryable=True
            )

    def save_duel_round(self, duel_id: str, round_number: int, round_data: Dict[str, Any]) -> None:
        try:
            self.client.collection("duels").document(duel_id).collection("rounds").document(str(round_number)).set(round_data)
        except Exception as e:
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to save duel round '{duel_id}/{round_number}' to Firestore: {e}",
                retryable=True
            )

    def get_duel_rounds(self, duel_id: str) -> List[Dict[str, Any]]:
        try:
            docs = self.client.collection("duels").document(duel_id).collection("rounds").order_by("round_number").stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to get duel rounds for '{duel_id}' from Firestore: {e}",
                retryable=True
            )

    def save_learned_pattern(self, pattern: Dict[str, Any]) -> None:
        pid = pattern.get("pattern_id") or f"PAT-LEARNED-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        pattern["pattern_id"] = pid
        try:
            self.client.collection("learned_patterns").document(pid).set(pattern)
        except Exception as e:
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to save learned pattern '{pid}' to Firestore: {e}",
                retryable=True
            )

    def get_learned_patterns(self) -> List[Dict[str, Any]]:
        try:
            docs = self.client.collection("learned_patterns").stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            raise CloudServiceError(
                service="firestore",
                message=f"Failed to get learned patterns from Firestore: {e}",
                retryable=True
            )


db_service = DatabaseService()
