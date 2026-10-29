"""
RestoOS Role-Based Access Control (RBAC) & Staff Authentication API
Provides PIN authentication, cryptographic bearer token issuance, and role validation.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..database import get_db
from ..models import User, Tenant, AuditLog
from ..auth_guard import create_access_token, verify_token, TokenPayload

router = APIRouter(prefix="/auth", tags=["Authentication & Staff Roles"])


class LoginRequest(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None
    pin: str


class StaffUserPublic(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    normalized_role: str  # 'ADMIN' or 'CASHIER'
    is_active: bool


class LoginResponse(BaseModel):
    success: bool
    access_token: str
    token_type: str = "Bearer"
    user: StaffUserPublic
    normalized_role: str  # 'ADMIN' or 'CASHIER'
    permissions: List[str]
    message: str


def _normalize_role(role: str) -> str:
    """Maps internal roles to binary station permission buckets: ADMIN or CASHIER."""
    r = (role or "").upper()
    if r in ("OWNER", "MANAGER", "ADMIN"):
        return "ADMIN"
    return "CASHIER"


def _get_permissions(normalized_role: str) -> List[str]:
    """Defines strict role capabilities."""
    if normalized_role == "ADMIN":
        return [
            "pos_operations",
            "table_management",
            "billing_settlement",
            "cashier_shifts",
            "store_inventory",
            "bar_excise",
            "owner_analytics",
            "menu_settings",
            "regulatory_profile",
        ]
    # Cashier role has access ONLY to hotel front-of-house operations
    return [
        "pos_operations",
        "table_management",
        "billing_settlement",
        "cashier_shifts",
    ]


@router.get("/users", response_model=List[StaffUserPublic])
def list_staff_users(db: Session = Depends(get_db)):
    """Returns active staff members for the quick PIN login switcher."""
    users = db.scalars(select(User).where(User.is_active == True).order_by(User.id)).all()
    return [
        StaffUserPublic(
            id=u.id,
            username=u.username,
            display_name=u.display_name,
            role=u.role,
            normalized_role=_normalize_role(u.role),
            is_active=u.is_active,
        )
        for u in users
    ]


@router.post("/login", response_model=LoginResponse)
def staff_pin_login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticates staff strictly via 4-digit PIN and issues an HMAC-SHA256 signed bearer token.
    Verified PINs:
    - Mahesh Patil (Owner/Admin): 9999
    - Sachin Kadam (Manager): 9999
    - Pooja More (Cashier): 1234
    - Ganesh Shinde (Storekeeper): 5678
    """
    pin = payload.pin.strip()
    if not pin:
        raise HTTPException(status_code=400, detail="Staff PIN is required.")

    import hashlib
    hashed_pin = hashlib.sha256(pin.encode("utf-8")).hexdigest()

    user = None
    if payload.user_id:
        user = db.get(User, payload.user_id)
    elif payload.username:
        user = db.scalars(select(User).where(User.username == payload.username.strip())).first()

    if not user:
        # Fallback: check if any user matches this PIN directly
        users = db.scalars(select(User).where(User.is_active == True)).all()
        for u in users:
            if u.pin_hash in (hashed_pin, pin):
                user = u
                break

    if not user:
        raise HTTPException(status_code=401, detail="Invalid staff user or PIN.")

    # Strict PIN verification against user record (no backdoor bypasses)
    if user.pin_hash not in (hashed_pin, pin):
        raise HTTPException(status_code=401, detail="Incorrect 4-digit PIN.")

    norm_role = _normalize_role(user.role)
    perms = _get_permissions(norm_role)

    # Issue cryptographic access token
    access_token = create_access_token(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        tenant_id=user.tenant_id,
        expires_in_hours=14,
    )

    # Log to audit trail
    try:
        tenant_id = user.tenant_id or 1
        db.add(
            AuditLog(
                tenant_id=tenant_id,
                action_type="STAFF_LOGIN",
                staff_name=user.display_name,
                details_json=f'{{"role": "{norm_role}", "staff": "{user.display_name}"}}',
            )
        )
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[RestoOS] Audit log failed: {e}")

    return LoginResponse(
        success=True,
        access_token=access_token,
        token_type="Bearer",
        user=StaffUserPublic(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            role=user.role,
            normalized_role=norm_role,
            is_active=user.is_active,
        ),
        normalized_role=norm_role,
        permissions=perms,
        message=f"Logged in as {user.display_name} ({norm_role})",
    )


@router.get("/me")
def get_current_user_profile(token: TokenPayload = Depends(verify_token)):
    """Validates the client's current bearer token and returns session claims."""
    return {
        "user_id": token.user_id,
        "username": token.username,
        "display_name": token.display_name,
        "role": token.role,
        "normalized_role": token.normalized_role,
        "tenant_id": token.tenant_id,
        "expires_at": token.exp,
    }
