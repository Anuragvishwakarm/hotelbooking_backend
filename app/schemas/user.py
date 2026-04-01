from pydantic import BaseModel, EmailStr
from typing import Optional, Any
from datetime import datetime
from app.models.user import UserRole, IDType, StaffRole


class UserBase(BaseModel):
    full_name: str
    email: Optional[str] = None
    phone: str
    preferred_language: str = "en"


class UserCreate(UserBase):
    password: str
    role: UserRole = UserRole.GUEST


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    preferred_language: Optional[str] = None
    profile_photo_url: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: Optional[str] = None
    phone: str
    role: UserRole
    is_active: bool
    is_verified: bool
    preferred_language: str
    hotel_id: Optional[int] = None 
    profile_photo_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class GuestProfileCreate(BaseModel):
    id_type: Optional[IDType] = None
    id_number: Optional[str] = None
    nationality: str = "Indian"
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    preferences: Optional[Any] = None


class GuestProfileUpdate(GuestProfileCreate):
    pass


class GuestProfileResponse(BaseModel):
    id: int
    user_id: int
    id_type: Optional[IDType] = None
    nationality: str
    city: Optional[str] = None
    state: Optional[str] = None
    loyalty_points: int
    total_stays: int
    is_vip: bool
    created_at: datetime

    class Config:
        from_attributes = True


class GuestWithUser(BaseModel):
    user: UserResponse
    guest_profile: Optional[GuestProfileResponse] = None

    class Config:
        from_attributes = True


class StaffCreate(BaseModel):
    user_id: int
    hotel_id: int
    staff_role: StaffRole
    employee_id: Optional[str] = None
    shift: Optional[str] = None


class StaffResponse(BaseModel):
    id: int
    user_id: int
    hotel_id: int
    staff_role: StaffRole
    employee_id: Optional[str] = None
    shift: Optional[str] = None
    is_on_duty: bool
    joined_at: datetime
    user: Optional[UserResponse] = None

    class Config:
        from_attributes = True
