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
    In production, verifies Firebase ID token or IAP.
    In development and test environments with ALLOW_DEV_TOKENS=True, supports dev tokens with roles.
    Returns decoded user dictionary {uid, email, role}.
    """
    if not auth_header or not auth_header.credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Missing Bearer token in Authorization header."
        )

    token = auth_header.credentials.strip()

    # 1. Dev token escape hatch: enabled only when settings.ALLOW_DEV_TOKENS is True
    if settings.ALLOW_DEV_TOKENS:
        if token in ("dev-token", "test-token", "adjuster-token") or token.startswith("adjuster-") or token.startswith("test-"):
            role = "viewer" if "viewer" in token else "adjuster"
            return {
                "uid": f"usr-{role}-dev",
                "email": f"{role}@finshield.internal",
                "role": role
            }
        elif token in ("viewer-token",) or token.startswith("viewer-"):
            return {
                "uid": "usr-viewer-dev",
                "email": "viewer@finshield.internal",
                "role": "viewer"
            }
        elif len(token) >= 16:
            # Generic dev token in local development
            return {
                "uid": f"usr-{token[:8]}",
                "email": f"user_{token[:6]}@finshield.internal",
                "role": "adjuster"
            }

    # 2. Production Mode: Verify with Firebase Auth
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
