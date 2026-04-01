from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    Enum, ForeignKey, Text, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class UserRole(str, enum.Enum):
    GUEST = "guest"
    STAFF = "staff"
    HOTEL_ADMIN = "hotel_admin"
    SUPER_ADMIN = "super_admin"


class StaffRole(str, enum.Enum):
    FRONT_DESK = "front_desk"
    HOUSEKEEPING = "housekeeping"
    MANAGER = "manager"
    ACCOUNTANT = "accountant"
    SECURITY = "security"


class IDType(str, enum.Enum):
    AADHAAR = "aadhaar"
    PASSPORT = "passport"
    PAN = "pan"
    VOTER_ID = "voter_id"
    DRIVING_LICENSE = "driving_license"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    phone = Column(String(15), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=True)
    role = Column(Enum(UserRole), default=UserRole.GUEST, nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    preferred_language = Column(String(5), default="en")
    profile_photo_url = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

    # ✅ Profiles
    guest_profile = relationship("Guest", back_populates="user", uselist=False)
    staff_profile = relationship("Staff", back_populates="user", uselist=False)

    # ✅ IMPORTANT FIX
    bookings = relationship(
        "Booking",
        back_populates="guest_user",
        foreign_keys="Booking.guest_user_id"
    )

    cancelled_bookings = relationship(
        "Booking",
        foreign_keys="Booking.cancelled_by"
    )

    checkins_done = relationship(
        "Booking",
        foreign_keys="Booking.checked_in_by"
    )

    checkouts_done = relationship(
        "Booking",
        foreign_keys="Booking.checked_out_by"
    )

    otp_sessions = relationship("OTPSession", back_populates="user")

class Guest(Base):
    __tablename__ = "guests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    id_type = Column(Enum(IDType), nullable=True)
    id_number = Column(String(50), nullable=True)
    id_document_url = Column(String(500), nullable=True)
    date_of_birth = Column(DateTime, nullable=True)
    nationality = Column(String(100), default="Indian")
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    pincode = Column(String(10), nullable=True)
    preferences = Column(JSON, nullable=True)
    loyalty_points = Column(Integer, default=0)
    total_stays = Column(Integer, default=0)
    is_vip = Column(Boolean, default=False)
    is_blacklisted = Column(Boolean, default=False)
    blacklist_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="guest_profile")


class Staff(Base):
    __tablename__ = "staff"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False)
    staff_role = Column(Enum(StaffRole), nullable=False)
    employee_id = Column(String(50), unique=True, nullable=True)
    shift = Column(String(20), nullable=True)  # morning/evening/night
    is_on_duty = Column(Boolean, default=False)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="staff_profile")
    hotel = relationship("Hotel", back_populates="staff_members")


class OTPSession(Base):
    __tablename__ = "otp_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    phone = Column(String(15), nullable=False, index=True)
    otp_code = Column(String(6), nullable=False)
    is_used = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="otp_sessions")
