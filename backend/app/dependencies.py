"""
Authentication and Role-Based Authorization Dependencies for FinShield.
Supports Firebase Auth ID Tokens / Cloud IAP with offline development fallbacks.
"""

import os
from typing import Optional, Dict, Any
from fastapi import Header, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.app.config import settings

security = HTTPBearer(auto_error=False)


async def get_current_user(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Dict[str, Any]:
    """
    Validates Bearer token on requests.
    In production (LOCAL_FALLBACK=False), verifies Firebase ID token or IAP.
    In local/test environments, supports test/dev tokens with roles.
    Returns decoded user dictionary {uid, email, role}.
    """
    if not auth_header or not auth_header.credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Missing Bearer token in Authorization header."
        )

    token = auth_header.credentials.strip()

    # 1. Production Mode: Verify with Firebase Auth
    if not settings.LOCAL_FALLBACK:
        try:
            import firebase_admin
            from firebase_admin import auth as firebase_auth
            decoded = firebase_auth.verify_id_token(token)
            role = decoded.get("role", "adjuster")  # default claim role
            return {
                "uid": decoded.get("uid"),
                "email": decoded.get("email"),
                "role": role,
                "claims": decoded
            }
        except Exception as e:
            raise HTTPException(
                status_code=401,
                detail=f"Invalid authentication token: {e}"
            )

    # 2. Local / Development / Test Mode
    # Token prefixes dictate test role
    if token in ("dev-token", "test-token", "adjuster-token") or token.startswith("adjuster-") or token.startswith("test-adjuster"):
        return {
            "uid": "usr-adjuster-dev",
            "email": "adjuster@finshield.internal",
            "role": "adjuster"
        }
    elif token in ("viewer-token",) or token.startswith("viewer-") or token.startswith("test-viewer"):
        return {
            "uid": "usr-viewer-dev",
            "email": "viewer@finshield.internal",
            "role": "viewer"
        }
    elif len(token) >= 16:
        # Generic non-empty bearer token treated as adjuster in dev
        return {
            "uid": f"usr-{token[:8]}",
            "email": f"user_{token[:6]}@finshield.internal",
            "role": "adjuster"
        }

    raise HTTPException(
        status_code=401,
        detail="Invalid authentication token."
    )


async def require_adjuster_role(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Enforces that the authenticated user possesses the 'adjuster' or 'admin' role.
    """
    role = current_user.get("role")
    if role not in ("adjuster", "admin"):
        raise HTTPException(
            status_code=403,
            detail=f"Forbidden: Operation requires 'adjuster' role, but user has '{role}'."
        )
    return current_user
