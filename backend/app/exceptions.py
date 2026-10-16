class CloudServiceError(Exception):
    """
    Raised when a Google Cloud service (Firestore, GCS, BigQuery, Document AI, Gemini, Secret Manager)
    fails or is unreachable. Never silently falls back to local or in-memory stand-ins.
    """
    def __init__(self, service: str, message: str, retryable: bool = True):
        super().__init__(message)
        self.service = service
        self.message = message
        self.retryable = retryable

    def to_dict(self):
        return {
            "error": self.message,
            "service": self.service,
            "retryable": self.retryable
        }
