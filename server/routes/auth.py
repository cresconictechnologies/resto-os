"""
RestoOS Role-Based Access Control (RBAC) & Staff Authentication API
Provides PIN authentication and role validation for Cashier and Admin stations.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..database import get_db
from ..models import User, Tenant, AuditLog

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
    user: StaffUserPublic
    normalized_role: str  # 'ADMIN' or 'CASHIER'
    permissions: List[str]
    message: str


def _normalize_role(role: str) -> str:
    """Maps internal roles to binary UI permission buckets: ADMIN or CASHIER."""
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
    Authenticates staff via 4-digit PIN.
    Default PINs:
    - Mahesh Patil (Owner/Admin): 9999
    - Sachin Kadam (Manager): 9999
    - Pooja More (Cashier): 1234
    - Ganesh Shinde (Storekeeper): 5678
    """
    pin = payload.pin.strip()
    if not pin:
        raise HTTPException(status_code=400, detail="Staff PIN is required.")

    user = None
    if payload.user_id:
        user = db.get(User, payload.user_id)
    elif payload.username:
        user = db.scalars(select(User).where(User.username == payload.username.strip())).first()

    if not user:
        # Fallback: check if any user matches this PIN directly
        users = db.scalars(select(User).where(User.is_active == True)).all()
        for u in users:
            if u.pin_hash == pin:
                user = u
                break

    if not user:
        raise HTTPException(status_code=401, detail="Invalid staff user or PIN.")

    # Validate PIN (plain comparison with seed pin_hash or 1234 / 9999 universal fallback)
    if user.pin_hash != pin and pin not in ("1234", "9999"):
        raise HTTPException(status_code=401, detail="Incorrect 4-digit PIN.")

    norm_role = _normalize_role(user.role)
    perms = _get_permissions(norm_role)

    # Log to audit trail
    try:
        tenant = db.scalars(select(Tenant)).first()
        tenant_id = tenant.id if tenant else 1
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
        print(f"[RestoOS] Audit log failed: {e}")

    return LoginResponse(
        success=True,
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
