"""
schemas/staff.py — Staff Management Pydantic Schemas
HotelBook v2.0 · Staff Management Module
"""
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from enum import Enum


# ── Enums (mirror DB enums) ──────────────────────────────────────────────────

class StaffRole(str, Enum):
    front_desk   = "front_desk"
    housekeeping = "housekeeping"
    manager      = "manager"
    accountant   = "accountant"
    security     = "security"


class ShiftType(str, Enum):
    morning = "morning"
    evening = "evening"
    night   = "night"


# ── Request Schemas ──────────────────────────────────────────────────────────

class StaffCreateRequest(BaseModel):
    """
    Used in POST /hotels/{hotel_id}/staff/
    Creates a user account + staff record in one shot.
    """
    # User account fields
    phone:        str
    full_name:    str
    password:     str

    # Staff-specific fields
    staff_role:   StaffRole
    shift:        ShiftType
    employee_id:  Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit() or len(v) != 10:
            raise ValueError("Phone must be 10-digit Indian mobile number")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class StaffUpdateRequest(BaseModel):
    """Used in PATCH /hotels/staff/{staff_id}"""
    staff_role:  Optional[StaffRole] = None
    shift:       Optional[ShiftType] = None
    is_on_duty:  Optional[bool]      = None
    employee_id: Optional[str]       = None


class DutyToggleRequest(BaseModel):
    """Used in PATCH /hotels/staff/{staff_id}/duty"""
    is_on_duty: bool


# ── Response Schemas ─────────────────────────────────────────────────────────

class StaffUserInfo(BaseModel):
    """Embedded user info in staff response"""
    id:         int
    phone:      str
    full_name:  str
    email:      Optional[str] = None
    is_active:  bool

    model_config = {"from_attributes": True}


class StaffResponse(BaseModel):
    """Full staff record returned by all staff endpoints"""
    id:          int
    hotel_id:    int
    staff_role:  str
    employee_id: Optional[str] = None
    shift:       Optional[str] = None
    is_on_duty:  bool
    joined_at:   datetime
    user:        StaffUserInfo

    model_config = {"from_attributes": True}


class StaffListResponse(BaseModel):
    """Paginated staff list"""
    total:  int
    items:  list[StaffResponse]