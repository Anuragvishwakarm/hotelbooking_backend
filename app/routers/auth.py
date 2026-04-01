import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, field_validator

from app.database import get_db
from app.models.user import User, Guest, OTPSession, UserRole
from app.models.hotel import Hotel
from app.schemas.auth import (
    SendOTPRequest, VerifyOTPRequest, RegisterRequest,
    LoginRequest, RefreshTokenRequest, TokenResponse, OTPResponse,
)
from app.schemas.user import UserResponse
from app.utils.jwt import create_access_token, create_refresh_token, verify_token
from app.utils.security import hash_password, verify_password
from app.utils.otp import create_otp_session, verify_otp_session, send_otp_sms_sync
from app.dependencies import get_current_user, require_super_admin
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ─── Request Schema ───────────────────────────────────────────────────────────

class CreateStaffRequest(BaseModel):
    full_name: str
    phone: str
    password: str
    role: UserRole
    email: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        phone = re.sub(r"\D", "", v)
        if phone.startswith("91") and len(phone) == 12:
            phone = phone[2:]
        if not re.match(r"^[6-9]\d{9}$", phone):
            raise ValueError("Invalid Indian phone number.")
        return phone

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: UserRole) -> UserRole:
        if v == UserRole.SUPER_ADMIN:
            raise ValueError("Cannot create super admin via API.")
        return v



# ─── ADD IN app/routers/auth.py ───────────────────────────────────────────────
# 
# STEP 1: Add this class AFTER CreateStaffRequest class
#
class RegisterOwnerRequest(BaseModel):
    full_name: str
    phone: str
    email: Optional[str] = None
    password: str
    confirm_password: str
    business_name: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        phone = re.sub(r"\D", "", v)
        if phone.startswith("91") and len(phone) == 12:
            phone = phone[2:]
        if not re.match(r"^[6-9]\d{9}$", phone):
            raise ValueError("Invalid Indian phone number.")
        return phone

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Need at least one uppercase letter.")
        if not re.search(r"\d", v):
            raise ValueError("Need at least one number.")
        return v

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match.")
        return v


# STEP 2: Add this endpoint BEFORE /register endpoint
#
@router.post("/register-owner", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_hotel_owner(payload: RegisterOwnerRequest, db: Session = Depends(get_db)):
    """
    Self-registration for hotel owners.
    Creates user with hotel_admin role — no super admin needed.
    
    POST /auth/register-owner
    {
        "full_name": "Rajesh Sharma",
        "phone": "9876543210",
        "email": "rajesh@grandpalace.in",     (optional)
        "password": "Hotel@1234",
        "confirm_password": "Hotel@1234",
        "business_name": "Hotel Grand Palace"  (optional, informational only)
    }
    """
    if db.query(User).filter(User.phone == payload.phone).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this phone number already exists.",
        )
    if payload.email and db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    user = User(
        full_name=payload.full_name,
        phone=payload.phone,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=UserRole.HOTEL_ADMIN,
        is_verified=True,
        is_active=True,
        preferred_language="en",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token({"sub": str(user.id), "role": user.role.value})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

# ─── Helper: build UserResponse with hotel_id ────────────────────────────────

def _user_response(user: User, db: Session) -> UserResponse:
    """
    Build UserResponse and attach hotel_id for hotel_admin / super_admin.
    hotel_id is NOT a column on User — we compute it on the fly.
    """
    hotel_id: Optional[int] = None
    if user.role in (UserRole.HOTEL_ADMIN, UserRole.SUPER_ADMIN):
        hotel = db.query(Hotel).filter(Hotel.created_by == user.id).first()
        hotel_id = hotel.id if hotel else None

    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
        preferred_language=user.preferred_language,
        profile_photo_url=user.profile_photo_url,
        created_at=user.created_at,
        hotel_id=hotel_id,           # computed, not a DB column
    )


# ─── Admin: Create Hotel Admin / Staff ───────────────────────────────────────

@router.post("/admin/create-user", response_model=UserResponse, status_code=201)
def create_user_by_admin(
    payload: CreateStaffRequest,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """
    Super admin only — create hotel_admin, staff, or guest accounts.
    
    Postman example:
    POST /auth/admin/create-user
    Authorization: Bearer <super_admin_token>
    {
        "full_name": "Rajesh Sharma",
        "phone": "9876543210",
        "password": "Hotel@1234",
        "role": "hotel_admin",
        "email": "rajesh@grandpalace.in"
    }
    """
    if db.query(User).filter(User.phone == payload.phone).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this phone number already exists.",
        )
    if payload.email and db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists.",
        )

    user = User(
        full_name=payload.full_name,
        phone=payload.phone,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        is_verified=True,        # admin-created users are auto-verified
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_response(user, db)


# ─── Register (Guest only) ────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new guest user with phone + password."""
    if db.query(User).filter(User.phone == payload.phone).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this phone number already exists.",
        )
    if payload.email and db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        hashed_password=hash_password(payload.password),
        role=UserRole.GUEST,
        preferred_language=payload.preferred_language,
    )
    db.add(user)
    db.flush()

    guest = Guest(user_id=user.id)
    db.add(guest)
    db.commit()
    db.refresh(user)

    access_token = create_access_token({"sub": str(user.id), "role": user.role.value})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ─── Login ────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Login with phone + password."""
    user = db.query(User).filter(User.phone == payload.phone).first()
    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid phone number or password.",
        )
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid phone number or password.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    user.last_login = datetime.now(timezone.utc)
    db.commit()

    access_token = create_access_token({"sub": str(user.id), "role": user.role.value})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ─── OTP ─────────────────────────────────────────────────────────────────────

@router.post("/send-otp", response_model=OTPResponse)
def send_otp(payload: SendOTPRequest, db: Session = Depends(get_db)):
    """Send OTP to the given phone number for login/verification."""
    user = db.query(User).filter(User.phone == payload.phone).first()
    user_id = user.id if user else None

    otp_session = create_otp_session(db, phone=payload.phone, user_id=user_id)
    send_otp_sms_sync(payload.phone, otp_session.otp_code)

    return OTPResponse(
        message="OTP sent successfully.",
        phone=payload.phone,
        expires_in_seconds=300,
    )


@router.post("/verify-otp", response_model=TokenResponse)
def verify_otp(payload: VerifyOTPRequest, db: Session = Depends(get_db)):
    """
    Verify OTP. If user doesn't exist, auto-register as guest.
    full_name is required for new users.
    """
    try:
        is_valid = verify_otp_session(db, phone=payload.phone, otp=payload.otp)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP. Please check and try again.",
        )

    user = db.query(User).filter(User.phone == payload.phone).first()

    if not user:
        if not payload.full_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="full_name is required for new users.",
            )
        user = User(
            full_name=payload.full_name,
            phone=payload.phone,
            role=UserRole.GUEST,
            is_verified=True,
        )
        db.add(user)
        db.flush()
        guest = Guest(user_id=user.id)
        db.add(guest)
    else:
        user.is_verified = True

    user.last_login = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    access_token = create_access_token({"sub": str(user.id), "role": user.role.value})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ─── Refresh Token ────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
def refresh_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Get a new access token using the refresh token."""
    token_payload = verify_token(payload.refresh_token, token_type="refresh")
    if not token_payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    user_id = token_payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive.",
        )

    access_token = create_access_token({"sub": str(user.id), "role": user.role.value})
    new_refresh = create_refresh_token({"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ─── Get Me ───────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the currently authenticated user's profile with hotel_id."""
    return _user_response(current_user, db)


# ─── Logout ───────────────────────────────────────────────────────────────────

@router.post("/logout")
def logout():
    """
    Logout endpoint. Client should delete tokens locally.
    (Stateless JWT — Redis blacklist Phase 3 mein add hoga.)
    """
    return {"message": "Logged out successfully. Please delete your tokens."}