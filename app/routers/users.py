from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, Guest
from app.schemas.user import (
    UserUpdate, UserResponse,
    GuestProfileCreate, GuestProfileUpdate, GuestProfileResponse,
    GuestWithUser,
)
from app.dependencies import get_current_user, require_hotel_admin, require_super_admin

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=GuestWithUser)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the full profile of the currently logged in user."""
    guest = db.query(Guest).filter(Guest.user_id == current_user.id).first()
    return {"user": current_user, "guest_profile": guest}


@router.patch("/me", response_model=UserResponse)
def update_my_profile(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update basic user info (name, email, language)."""
    if payload.email and payload.email != current_user.email:
        existing = db.query(User).filter(User.email == payload.email).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already in use by another account.",
            )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/me/guest-profile", response_model=GuestProfileResponse)
def get_guest_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the guest-specific profile (ID docs, preferences, loyalty)."""
    guest = db.query(Guest).filter(Guest.user_id == current_user.id).first()
    if not guest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest profile not found.",
        )
    return guest


@router.put("/me/guest-profile", response_model=GuestProfileResponse)
def upsert_guest_profile(
    payload: GuestProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update the guest profile."""
    guest = db.query(Guest).filter(Guest.user_id == current_user.id).first()

    if not guest:
        guest = Guest(user_id=current_user.id)
        db.add(guest)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(guest, field, value)

    db.commit()
    db.refresh(guest)
    return guest


@router.get("/{user_id}", response_model=GuestWithUser)
def get_user_by_id(
    user_id: int,
    current_user: User = Depends(require_hotel_admin),
    db: Session = Depends(get_db),
):
    """Get any user's full profile. Requires hotel admin or higher."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found.",
        )
    guest = db.query(Guest).filter(Guest.user_id == user_id).first()
    return {"user": user, "guest_profile": guest}


@router.get("/", response_model=list[UserResponse])
def list_users(
    page: int = 1,
    size: int = 20,
    search: str = None,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """List all users. Super admin only."""
    query = db.query(User)
    if search:
        query = query.filter(
            User.full_name.ilike(f"%{search}%")
            | User.phone.ilike(f"%{search}%")
            | User.email.ilike(f"%{search}%")
        )
    offset = (page - 1) * size
    return query.offset(offset).limit(size).all()


@router.patch("/{user_id}/toggle-active")
def toggle_user_active(
    user_id: int,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Activate or deactivate a user account. Super admin only."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account.")

    user.is_active = not user.is_active
    db.commit()
    action = "activated" if user.is_active else "deactivated"
    return {"message": f"User {user.full_name} has been {action}.", "is_active": user.is_active}
