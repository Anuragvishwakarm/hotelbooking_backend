"""
routers/staff.py — Staff Management Router
HotelBook v2.0 · Staff Management Module
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.hotel import Hotel
from app.models.user import User, UserRole, Staff
from app.schemas.staff import (
    StaffCreateRequest,
    StaffUpdateRequest,
    DutyToggleRequest,
    StaffResponse,
    StaffListResponse,
)
from app.dependencies import get_current_user
from app.utils.security import hash_password

router = APIRouter(prefix="/hotels", tags=["staff"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_hotel_or_403(hotel_id: int, current_user: User, db: Session) -> Hotel:
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    is_owner       = hotel.created_by == current_user.id
    is_super_admin = current_user.role == UserRole.SUPER_ADMIN
    if not (is_owner or is_super_admin):
        raise HTTPException(status_code=403, detail="Access denied — not your hotel")
    return hotel


def _staff_response(staff: Staff) -> StaffResponse:
    return StaffResponse.model_validate(staff)


def _generate_employee_id(hotel_id: int, db: Session) -> str:
    """Auto-increment: EMP-4-0001, EMP-4-0002, EMP-4-0003..."""
    last_staff = (
        db.query(Staff)
        .filter(Staff.hotel_id == hotel_id)
        .filter(Staff.employee_id.isnot(None))
        .order_by(Staff.id.desc())
        .first()
    )
    if last_staff and last_staff.employee_id:
        try:
            last_num = int(last_staff.employee_id.split("-")[-1])
        except ValueError:
            last_num = 0
    else:
        last_num = 0

    new_num = last_num + 1
    return f"EMP-{hotel_id}-{str(new_num).zfill(4)}"


# ── 1. List Staff ─────────────────────────────────────────────────────────────

@router.get("/{hotel_id}/staff/", response_model=StaffListResponse)
def list_staff(
    hotel_id: int,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    _get_hotel_or_403(hotel_id, current_user, db)

    staff_list = (
        db.query(Staff)
        .options(joinedload(Staff.user))
        .filter(Staff.hotel_id == hotel_id)
        .order_by(Staff.joined_at.desc())
        .all()
    )
    return StaffListResponse(
        total=len(staff_list),
        items=[_staff_response(s) for s in staff_list],
    )


# ── 2. Add Staff ──────────────────────────────────────────────────────────────

@router.post("/{hotel_id}/staff/", response_model=StaffResponse, status_code=201)
def add_staff(
    hotel_id:     int,
    payload:      StaffCreateRequest,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    _get_hotel_or_403(hotel_id, current_user, db)

    existing_user = db.query(User).filter(User.phone == payload.phone).first()
    if existing_user:
        existing_staff = (
            db.query(Staff)
            .filter(Staff.user_id == existing_user.id, Staff.hotel_id == hotel_id)
            .first()
        )
        if existing_staff:
            raise HTTPException(
                status_code=409,
                detail="This phone number is already registered as staff at this hotel",
            )
        user = existing_user
        if user.role == UserRole.GUEST:
            user.role = UserRole.STAFF
            db.add(user)
    else:
        user = User(
            phone           = payload.phone,
            full_name       = payload.full_name,
            hashed_password = hash_password(payload.password),
            role            = UserRole.STAFF,
            is_active       = True,
            is_verified     = True,
        )
        db.add(user)
        db.flush()

    # Auto-generate employee_id if not provided
    emp_id = payload.employee_id or _generate_employee_id(hotel_id, db)

    staff = Staff(
        user_id     = user.id,
        hotel_id    = hotel_id,
        staff_role  = payload.staff_role.value,
        shift       = payload.shift.value,
        employee_id = emp_id,
        is_on_duty  = False,
    )
    db.add(staff)
    db.commit()
    db.refresh(staff)
    staff.user  # trigger lazy load
    return _staff_response(staff)


# ── 3. Update Staff ───────────────────────────────────────────────────────────

@router.patch("/staff/{staff_id}", response_model=StaffResponse)
def update_staff(
    staff_id:     int,
    payload:      StaffUpdateRequest,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    staff = (
        db.query(Staff)
        .options(joinedload(Staff.user))
        .filter(Staff.id == staff_id)
        .first()
    )
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")

    _get_hotel_or_403(staff.hotel_id, current_user, db)

    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(staff, field, value.value if hasattr(value, "value") else value)

    db.commit()
    db.refresh(staff)
    return _staff_response(staff)


# ── 4. Toggle Duty ────────────────────────────────────────────────────────────

@router.patch("/staff/{staff_id}/duty", response_model=StaffResponse)
def toggle_duty(
    staff_id:     int,
    payload:      DutyToggleRequest,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    staff = (
        db.query(Staff)
        .options(joinedload(Staff.user))
        .filter(Staff.id == staff_id)
        .first()
    )
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")

    _get_hotel_or_403(staff.hotel_id, current_user, db)

    staff.is_on_duty = payload.is_on_duty
    db.commit()
    db.refresh(staff)
    return _staff_response(staff)


# ── 5. Remove Staff ───────────────────────────────────────────────────────────

@router.delete("/staff/{staff_id}", status_code=204)
def remove_staff(
    staff_id:     int,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    staff = (
        db.query(Staff)
        .options(joinedload(Staff.user))
        .filter(Staff.id == staff_id)
        .first()
    )
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")

    _get_hotel_or_403(staff.hotel_id, current_user, db)

    user = db.query(User).filter(User.id == staff.user_id).first()
    if user:
        user.is_active = False
        db.add(user)

    db.delete(staff)
    db.commit()