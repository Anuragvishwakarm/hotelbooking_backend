from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    Float, Text, JSON, Enum, ForeignKey, DECIMAL,TIMESTAMP
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class HotelStarRating(int, enum.Enum):
    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5


class RoomStatus(str, enum.Enum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"
    CLEANING = "cleaning"
    BLOCKED = "blocked"
    INSPECTING = "inspecting"


class BedType(str, enum.Enum):
    SINGLE = "single"
    DOUBLE = "double"
    QUEEN = "queen"
    KING = "king"
    TWIN = "twin"
    BUNK = "bunk"


class Hotel(Base):
    __tablename__ = "hotels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    slug = Column(String(255), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    star_rating = Column(Integer, default=3, nullable=False)
    address = Column(Text, nullable=False)
    city = Column(String(100), nullable=False, index=True)
    state = Column(String(100), nullable=False)
    pincode = Column(String(10), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    phone = Column(String(15), nullable=False)
    email = Column(String(255), nullable=True)
    website = Column(String(255), nullable=True)
    check_in_time = Column(String(10), default="14:00")
    check_out_time = Column(String(10), default="11:00")
    amenities = Column(JSON, nullable=True)
    policies = Column(JSON, nullable=True)
    photos = Column(JSON, nullable=True)
    cover_photo_url = Column(String(500), nullable=True)
    gst_number = Column(String(20), nullable=True)
    pan_number = Column(String(15), nullable=True)
    total_rooms = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    room_types = relationship("RoomType", back_populates="hotel")
    rooms = relationship("Room", back_populates="hotel")
    bookings = relationship("Booking", back_populates="hotel")
    staff_members = relationship("Staff", back_populates="hotel")


class RoomType(Base):
    __tablename__ = "room_types"

    id = Column(Integer, primary_key=True, index=True)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    bed_type = Column(Enum(BedType), nullable=False, default=BedType.DOUBLE)
    base_price = Column(DECIMAL(10, 2), nullable=False)
    weekend_price = Column(DECIMAL(10, 2), nullable=True)
    max_occupancy = Column(Integer, default=2)
    max_adults = Column(Integer, default=2)
    max_children = Column(Integer, default=1)
    area_sqft = Column(Float, nullable=True)
    floor = Column(Integer, nullable=True)
    amenities = Column(JSON, nullable=True)
    meal_plans = Column(JSON, nullable=True)   # ← ADD: store meal plans
    photos = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    hotel = relationship("Hotel", back_populates="room_types")
    rooms = relationship("Room", back_populates="room_type")
    bookings = relationship("Booking", back_populates="room_type")


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False, index=True)
    room_type_id = Column(Integer, ForeignKey("room_types.id"), nullable=False)
    room_number = Column(String(20), nullable=False)
    floor = Column(Integer, nullable=False)
    status = Column(Enum(RoomStatus), default=RoomStatus.AVAILABLE, nullable=False)
    is_smoking = Column(Boolean, default=False)
    is_accessible = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    last_cleaned_at = Column(DateTime(timezone=True), nullable=True)
    last_inspected_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    hotel = relationship("Hotel", back_populates="rooms")
    room_type = relationship("RoomType", back_populates="rooms")
    bookings = relationship("Booking", back_populates="room")


class StaffRoleEnum(enum.Enum):
    front_desk   = "front_desk"
    housekeeping = "housekeeping"
    manager      = "manager"
    accountant   = "accountant"
    security     = "security"

# class Staff(Base):
#     __tablename__ = "staff"

#     id          = Column(Integer, primary_key=True, index=True)
#     user_id     = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
#     hotel_id    = Column(Integer, ForeignKey("hotels.id"), nullable=False, index=True)
#     staff_role  = Column(String(50), nullable=False)
#     employee_id = Column(String(50), nullable=True, unique=True)
#     shift       = Column(String(20), nullable=True)
#     is_on_duty  = Column(Boolean, nullable=False, default=False)
#     joined_at   = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

#     user  = relationship("User",  foreign_keys=[user_id],  lazy="select")
#     hotel = relationship("Hotel", foreign_keys=[hotel_id], lazy="select")