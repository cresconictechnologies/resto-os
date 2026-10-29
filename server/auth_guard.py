"""
RestoOS Production Cryptographic Authentication & RBAC Route Guards
Enforces station-level security (Cashier vs Admin) using HMAC-SHA256 signed bearer tokens.
"""

from datetime import datetime, timezone, timedelta
import os
import hmac
import hashlib
import json
from typing import Optional, List
from fastapi import Header, HTTPException, Depends, status
from pydantic import BaseModel

# Secret key for signing bearer tokens
SECRET_KEY = os.getenv("SESSION_SECRET", "restoos-pune-sahyadri-secret-key-2026-production")


class TokenPayload(BaseModel):
    user_id: int
    username: str
    display_name: str
    role: str
    normalized_role: str  # 'ADMIN' or 'CASHIER'
    tenant_id: int
    exp: int


def create_access_token(
    user_id: int,
    username: str,
    display_name: str,
    role: str,
    tenant_id: int = 1,
    expires_in_hours: int = 14,
) -> str:
    """
    Issues an HMAC-SHA256 signed access token for station logins.
    Token validity defaults to a full 14-hour restaurant operating shift.
    """
    norm_role = "ADMIN" if role.upper() in ("OWNER", "MANAGER", "ADMIN") else "CASHIER"
    exp = int((datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)).timestamp())
    payload = {
        "uid": user_id,
        "usr": username,
        "name": display_name,
        "role": role,
        "nrole": norm_role,
        "tid": tenant_id,
        "exp": exp,
    }
    payload_json = json.dumps(payload, separators=(",", ":"))
    signature = hmac.new(SECRET_KEY.encode(), payload_json.encode(), hashlib.sha256).hexdigest()
    raw = f"{payload_json}.{signature}"
    return raw.encode("utf-8").hex()


def verify_token(authorization: Optional[str] = Header(None)) -> TokenPayload:
    """
    Validates the Authorization: Bearer <token> header.
    Rejects missing, expired, or tampered tokens with 401 Unauthorized.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token missing. Please sign in with staff PIN.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format. Expected 'Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_hex = authorization[7:].strip()
    try:
        raw = bytes.fromhex(token_hex).decode("utf-8")
        if "." not in raw:
            raise ValueError("Malformed token format")

        payload_json, signature = raw.rsplit(".", 1)
        expected_sig = hmac.new(SECRET_KEY.encode(), payload_json.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Security signature verification failed. Token rejected.",
            )

        data = json.loads(payload_json)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        if data.get("exp", 0) < now_ts:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Staff session expired. Please re-enter your 4-digit PIN.",
            )

        return TokenPayload(
            user_id=data["uid"],
            username=data["usr"],
            display_name=data.get("name", data["usr"]),
            role=data.get("role", "CASHIER"),
            normalized_role=data.get("nrole", "CASHIER"),
            tenant_id=data.get("tid", 1),
            exp=data["exp"],
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or unparseable session token.",
        )


def require_admin(token: TokenPayload = Depends(verify_token)) -> TokenPayload:
    """
    Restricts access strictly to Admin / Owner / Manager station credentials.
    Cashiers attempting to access management or statutory registers receive 403 Forbidden.
    """
    if token.normalized_role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied for role '{token.role}'. Admin privileges required.",
        )
    return token


def require_cashier_or_admin(token: TokenPayload = Depends(verify_token)) -> TokenPayload:
    """Permits both front-of-house Cashiers and Admins."""
    if token.normalized_role not in ("CASHIER", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied for current user role.",
        )
    return token
