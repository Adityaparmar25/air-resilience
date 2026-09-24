"""Firebase Authentication and Server-Side Role-Based Access Control (RBAC).

Verifies Firebase ID tokens server-side and checks roles against the operational store.
Never trusts client-supplied role claims without cryptographic verification.
"""

from dataclasses import dataclass
import logging
import os
from typing import List, Optional

from fastapi import Depends, Header, HTTPException, status

from apps.api.config import get_settings
from services.operational.store import get_operational_store

logger = logging.getLogger(__name__)


@dataclass
class UserIdentity:
    """Authenticated user identity extracted from verified Firebase ID token."""
    uid: str
    email: Optional[str]
    role: str
    display_name: Optional[str] = None


# Development / test mock identities
TEST_IDENTITIES = {
    "test-token-authority": UserIdentity(
        uid="authority-test-user-01",
        email="authority@delhi-cpcb.gov.in",
        role="AUTHORITY",
        display_name="Delhi Authority Officer",
    ),
    "test-token-admin": UserIdentity(
        uid="admin-test-user-01",
        email="admin@air-resilience.network",
        role="ADMIN",
        display_name="System Administrator",
    ),
    "test-token-dispatcher": UserIdentity(
        uid="dispatcher-test-user-01",
        email="dispatcher@cpcb.gov.in",
        role="DISPATCHER",
        display_name="Incident Dispatcher",
    ),
    "test-token-operator": UserIdentity(
        uid="operator-test-user-01",
        email="field@haryana-pcb.gov.in",
        role="FIELD_OPERATOR",
        display_name="Haryana Field Operator",
    ),
    "test-token-citizen": UserIdentity(
        uid="citizen-test-user-01",
        email="citizen@example.com",
        role="CITIZEN",
        display_name="Citizen User",
    ),
}

_firebase_app_initialized = False


def _init_firebase_app():
    global _firebase_app_initialized
    if _firebase_app_initialized:
        return
    try:
        import firebase_admin

        if not firebase_admin._apps:
            settings = get_settings()
            options = {}
            if settings.FIREBASE_PROJECT_ID:
                options["projectId"] = settings.FIREBASE_PROJECT_ID
            elif settings.GOOGLE_CLOUD_PROJECT:
                options["projectId"] = settings.GOOGLE_CLOUD_PROJECT

            firebase_admin.initialize_app(options=options if options else None)
        _firebase_app_initialized = True
    except Exception as exc:
        logger.warning(f"Could not initialize Firebase Admin SDK: {exc}")


def verify_bearer_token(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
) -> UserIdentity:
    """Verify Bearer token and return authenticated UserIdentity.
    
    In production: Strictly verifies Firebase ID token via Firebase Admin SDK.
    Never trusts client-supplied headers without cryptographic proof.
    """
    settings = get_settings()
    is_prod = settings.ENV == "production"

    if is_prod:
        # In production, strictly require Authorization: Bearer <token>
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Missing or invalid Authorization header. Expected 'Bearer <token>'.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = authorization.split("Bearer ", 1)[1].strip()
        _init_firebase_app()
        try:
            import firebase_admin.auth as fb_auth

            decoded = fb_auth.verify_id_token(token)
            uid = decoded.get("uid")
            email = decoded.get("email")
            display_name = decoded.get("name")
            store = get_operational_store()
            role = store.get_user_role(uid, email)
            return UserIdentity(uid=uid, email=email, role=role, display_name=display_name)
        except Exception as exc:
            logger.error(f"Firebase token verification failed in production: {exc}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid, expired, or unverified authentication token.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

    # Development or Testing mode
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()
        if token in TEST_IDENTITIES:
            return TEST_IDENTITIES[token]

    # For dev/test backward compatibility where X-User-Role was provided in unit tests
    if x_user_role:
        role_key = x_user_role.strip().upper()
        for identity in TEST_IDENTITIES.values():
            if identity.role.upper() == role_key:
                return identity
        return UserIdentity(
            uid=f"dev-user-{role_key.lower()}",
            email=f"{role_key.lower()}@dev.local",
            role=role_key,
        )

    # Dev/test default when no auth headers are passed
    return TEST_IDENTITIES["test-token-authority"]


def require_role(allowed_roles: Optional[List[str]] = None):
    """Enforce that the authenticated user possesses one of the allowed roles."""
    valid_roles = [r.upper() for r in (allowed_roles or ["AUTHORITY", "ADMIN", "DISPATCHER", "FIELD_OPERATOR"])]

    def role_checker(identity: UserIdentity = Depends(verify_bearer_token)) -> UserIdentity:
        if identity.role.upper() not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Unauthorized: Role '{identity.role}' cannot perform this authority action. Allowed roles: {valid_roles}",
            )
        return identity

    return role_checker
