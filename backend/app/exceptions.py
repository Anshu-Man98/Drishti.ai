"""
Drishti custom exception hierarchy.
Eliminates silent failures, replaces raw HTTPException(500), and provides structured error reporting.
"""

from typing import Optional, Dict, Any


class DrishtiError(Exception):
    """Base exception for all Drishti domain and system errors."""
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        code: str = "internal_error",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "error": self.message,
            "code": self.code,
            "status_code": self.status_code
        }
        if self.details:
            res["details"] = self.details
        return res


class CloudServiceError(DrishtiError):
    """
    Raised when a Google Cloud service (Firestore, GCS, BigQuery, Document AI, Gemini, Secret Manager)
    fails or is unreachable. Never silently falls back to local or in-memory stand-ins.
    """
    def __init__(self, service: str, message: str, retryable: bool = True):
        super().__init__(
            message=message,
            status_code=503,
            code="cloud_service_error",
            details={"service": service, "retryable": retryable}
        )
        self.service = service
        self.retryable = retryable

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": self.message,
            "service": self.service,
            "retryable": self.retryable
        }


class DocumentProcessingError(DrishtiError):
    """Raised when document extraction, parsing, or rendering fails."""
    def __init__(self, message: str, doc_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=422,
            code="document_processing_error",
            details={"doc_id": doc_id, **(details or {})}
        )


class StorageError(DrishtiError):
    """Raised when Cloud Storage (or local storage backend) fails to read, write, or find files."""
    def __init__(self, message: str, doc_id: Optional[str] = None, uri: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=500,
            code="storage_error",
            details={"doc_id": doc_id, "uri": uri, **(details or {})}
        )


class AgentExecutionError(DrishtiError):
    """Raised when a specialist agent or orchestrator runner fails unexpectedly."""
    def __init__(self, message: str, agent_name: Optional[str] = None, claim_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=500,
            code="agent_execution_error",
            details={"agent_name": agent_name, "claim_id": claim_id, **(details or {})}
        )


class AnalyticsError(DrishtiError):
    """Raised when an analytics aggregation query or dashboard computation fails."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=500,
            code="analytics_error",
            details=details or {}
        )


class ProvenanceSigningError(DrishtiError):
    """Raised when cryptographic signing or watermark stamping of a document fails."""
    def __init__(self, message: str, doc_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=500,
            code="provenance_signing_error",
            details={"doc_id": doc_id, **(details or {})}
        )


class DatabaseError(DrishtiError):
    """Raised when a database query or transaction fails unexpectedly."""
    def __init__(self, message: str, operation: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=500,
            code="database_error",
            details={"operation": operation, **(details or {})}
        )
