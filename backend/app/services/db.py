import json
import sqlite3
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from backend.app.config import settings
from backend.app.schemas import Claim, Dossier, ClaimSummary, ChatMessage

try:
    from google.cloud import firestore
    _firestore_available = True
except Exception:
    _firestore_available = False


class DatabaseService:
    def __init__(self):
        self._fs_client = None
        self.local_db_path = Path(settings.LOCAL_DATA_DIR) / "finshield.db"
        self.local_db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_sqlite()

        if _firestore_available and not settings.LOCAL_FALLBACK:
            try:
                self._fs_client = firestore.Client(
                    project=settings.GCP_PROJECT,
                    database=settings.FIRESTORE_DATABASE
                )
            except Exception:
                self._fs_client = None

    def _init_sqlite(self):
        with sqlite3.connect(self.local_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS claims (
                    claim_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dossiers (
                    claim_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    claim_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    cited_finding_ids TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def save_claim(self, claim: Claim) -> None:
        claim_dict = json.loads(claim.model_dump_json())
        # SQLite
        with sqlite3.connect(self.local_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO claims (claim_id, data, created_at) VALUES (?, ?, ?)",
                (claim.claim_id, json.dumps(claim_dict), datetime.utcnow().isoformat())
            )
            conn.commit()

        # Firestore if available
        if self._fs_client:
            try:
                self._fs_client.collection("claims").document(claim.claim_id).set(claim_dict)
            except Exception as e:
                print(f"[DB] Firestore write failed: {e}")

    def get_claim(self, claim_id: str) -> Optional[Claim]:
        if self._fs_client:
            try:
                doc = self._fs_client.collection("claims").document(claim_id).get()
                if doc.exists:
                    return Claim.model_validate(doc.to_dict())
            except Exception as e:
                print(f"[DB] Firestore get failed: {e}")

        with sqlite3.connect(self.local_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data FROM claims WHERE claim_id = ?", (claim_id,))
            row = cursor.fetchone()
            if row:
                return Claim.model_validate_json(row[0])
        return None

    def list_claims(self, limit: int = 50) -> List[ClaimSummary]:
        summaries: List[ClaimSummary] = []
        with sqlite3.connect(self.local_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT claim_id, data FROM claims ORDER BY created_at DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            for claim_id, data_str in rows:
                c = json.loads(data_str)
                # Check if dossier exists
                cursor.execute("SELECT data FROM dossiers WHERE claim_id = ?", (claim_id,))
                d_row = cursor.fetchone()
                verdict = None
                risk_score = None
                if d_row:
                    d_data = json.loads(d_row[0])
                    verdict = d_data.get("verdict")
                    risk_score = d_data.get("risk_score")

                summaries.append(ClaimSummary(
                    claim_id=c["claim_id"],
                    policy_id=c["policy_id"],
                    insurer_id=c["insurer_id"],
                    claimant_name=c["claimant"]["name"],
                    hospital_name=c["provider"]["name"],
                    city=c["provider"]["city"],
                    total_claimed=c["total_claimed"],
                    admission_ts=c["admission_ts"],
                    discharge_ts=c["discharge_ts"],
                    diagnosis_code=c["diagnosis_code"],
                    doc_count=len(c.get("documents", [])),
                    created_at=c.get("created_at") or datetime.utcnow(),
                    verdict=verdict,
                    risk_score=risk_score
                ))
        return summaries

    def save_dossier(self, dossier: Dossier) -> None:
        dossier_dict = json.loads(dossier.model_dump_json())
        with sqlite3.connect(self.local_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO dossiers (claim_id, data, created_at) VALUES (?, ?, ?)",
                (dossier.claim_id, json.dumps(dossier_dict), datetime.utcnow().isoformat())
            )
            conn.commit()

        if self._fs_client:
            try:
                self._fs_client.collection("dossiers").document(dossier.claim_id).set(dossier_dict)
            except Exception as e:
                print(f"[DB] Firestore dossier write failed: {e}")

    def get_dossier(self, claim_id: str) -> Optional[Dossier]:
        if self._fs_client:
            try:
                doc = self._fs_client.collection("dossiers").document(claim_id).get()
                if doc.exists:
                    return Dossier.model_validate(doc.to_dict())
            except Exception as e:
                print(f"[DB] Firestore dossier get failed: {e}")

        with sqlite3.connect(self.local_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data FROM dossiers WHERE claim_id = ?", (claim_id,))
            row = cursor.fetchone()
            if row:
                return Dossier.model_validate_json(row[0])
        return None

    def save_chat_message(
        self,
        claim_id: str,
        role: str,
        content: str,
        cited_finding_ids: Optional[List[str]] = None
    ) -> None:
        """Saves an adjuster chat message in Firestore under the claim, with local SQLite fallback."""
        now = datetime.utcnow().isoformat()
        cited_ids = cited_finding_ids or []

        # Local SQLite
        with sqlite3.connect(self.local_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_messages (claim_id, role, content, cited_finding_ids, created_at) VALUES (?, ?, ?, ?, ?)",
                (claim_id, role, content, json.dumps(cited_ids), now)
            )
            conn.commit()

        # Firestore under claims/{id}/chat_messages
        if self._fs_client:
            try:
                self._fs_client.collection("claims").document(claim_id).collection("chat_messages").add({
                    "role": role,
                    "content": content,
                    "cited_finding_ids": cited_ids,
                    "created_at": now
                })
            except Exception as e:
                print(f"[DB] Firestore chat message write failed: {e}")

    def get_chat_history(self, claim_id: str) -> List[ChatMessage]:
        """Retrieves chronological chat history for a claim."""
        # Check Firestore first
        if self._fs_client:
            try:
                docs = (
                    self._fs_client.collection("claims")
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
                if messages:
                    return messages
            except Exception as e:
                print(f"[DB] Firestore chat history query failed: {e}")

        # Local SQLite fallback
        messages = []
        with sqlite3.connect(self.local_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role, content, cited_finding_ids, created_at FROM chat_messages WHERE claim_id = ? ORDER BY id ASC",
                (claim_id,)
            )
            rows = cursor.fetchall()
            for role, content, cited_json, created_at_str in rows:
                cited_ids = json.loads(cited_json) if cited_json else []
                try:
                    dt = datetime.fromisoformat(created_at_str)
                except Exception:
                    dt = datetime.utcnow()
                messages.append(ChatMessage(
                    role=role,
                    content=content,
                    cited_finding_ids=cited_ids,
                    created_at=dt
                ))
        return messages


db_service = DatabaseService()
