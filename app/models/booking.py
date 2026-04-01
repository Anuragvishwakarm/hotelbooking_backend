from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    Text, JSON, Enum, ForeignKey, DECIMAL, Date
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class BookingStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class BookingSource(str, enum.Enum):
    ONLINE_WEB = "online_web"
    ONLINE_APP = "online_app"
    WALK_IN = "walk_in"
    PHONE = "phone"
    OTA = "ota"
    CORPORATE = "corporate"


class MealPlan(str, enum.Enum):
    EP = "ep"
    CP = "cp"
    MAP = "map"
    AP = "ap"
    AI = "ai"


class FolioItemCategory(str, enum.Enum):   # ✅ ADD THIS
    ROOM = "room"
    FOOD_BEVERAGE = "food_beverage"
    LAUNDRY = "laundry"
    SPA = "spa"
    MINIBAR = "minibar"
    TELEPHONE = "telephone"
    TRANSPORT = "transport"
    OTHERS = "others"
    
class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    booking_ref = Column(String(20), unique=True, nullable=False, index=True)

    # ✅ FK
    guest_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=True)
    room_type_id = Column(Integer, ForeignKey("room_types.id"), nullable=False)

    # Dates
    check_in_date = Column(Date, nullable=False)
    check_out_date = Column(Date, nullable=False)
    actual_check_in = Column(DateTime(timezone=True), nullable=True)
    actual_check_out = Column(DateTime(timezone=True), nullable=True)

    # Guests
    adults = Column(Integer, default=1)
    children = Column(Integer, default=0)
    meal_plan = Column(Enum(MealPlan), default=MealPlan.EP)

    # Status
    status = Column(Enum(BookingStatus), default=BookingStatus.PENDING, nullable=False)
    source = Column(Enum(BookingSource), default=BookingSource.ONLINE_WEB)

    # Pricing
    room_rate_per_night = Column(DECIMAL(10, 2), nullable=False)
    num_nights = Column(Integer, nullable=False)
    subtotal = Column(DECIMAL(10, 2), nullable=False)
    gst_amount = Column(DECIMAL(10, 2), default=0)
    discount_amount = Column(DECIMAL(10, 2), default=0)
    total_amount = Column(DECIMAL(10, 2), nullable=False)

    # Notes
    special_requests = Column(Text, nullable=True)
    internal_notes = Column(Text, nullable=True)

    # ✅ MULTIPLE USER ACTIONS (IMPORTANT)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    cancelled_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    checked_in_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    checked_out_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # ================= RELATIONSHIPS =================

    # ✅ FIXED (main relation)
    guest_user = relationship(
        "User",
        back_populates="bookings",
        foreign_keys=[guest_user_id]
    )

    # ✅ IMPORTANT (to avoid error)
    cancelled_user = relationship(
        "User",
        foreign_keys=[cancelled_by]
    )

    checked_in_user = relationship(
        "User",
        foreign_keys=[checked_in_by]
    )

    checked_out_user = relationship(
        "User",
        foreign_keys=[checked_out_by]
    )

    # Other relations
    hotel = relationship("Hotel", back_populates="bookings")
    room = relationship("Room", back_populates="bookings")
    room_type = relationship("RoomType", back_populates="bookings")
    payments = relationship("Payment", back_populates="booking")

    folio = relationship(
        "Folio",
        back_populates="booking",
        uselist=False
    )



class Folio(Base):
    __tablename__ = "folios"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), unique=True, nullable=False)
    folio_number = Column(String(20), unique=True, nullable=False)
    subtotal = Column(DECIMAL(10, 2), default=0)
    gst_amount = Column(DECIMAL(10, 2), default=0)
    total = Column(DECIMAL(10, 2), default=0)
    paid = Column(DECIMAL(10, 2), default=0)
    balance = Column(DECIMAL(10, 2), default=0)
    is_closed = Column(Boolean, default=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    invoice_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    booking = relationship("Booking", back_populates="folio")
    items = relationship("FolioItem", back_populates="folio")


class FolioItem(Base):
    __tablename__ = "folio_items"

    id = Column(Integer, primary_key=True, index=True)
    folio_id = Column(Integer, ForeignKey("folios.id"), nullable=False, index=True)
    description = Column(String(255), nullable=False)
    category = Column(Enum(FolioItemCategory), default=FolioItemCategory.ROOM)
    quantity = Column(Integer, default=1)
    unit_price = Column(DECIMAL(10, 2), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    date = Column(Date, nullable=False)
    added_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    folio = relationship("Folio", back_populates="items")
