from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from app.models.booking import BookingStatus, BookingSource, MealPlan, FolioItemCategory


class BookingCreate(BaseModel):
    hotel_id: int
    room_type_id: int
    check_in_date: date
    check_out_date: date
    adults: int = 1
    children: int = 0
    meal_plan: MealPlan = MealPlan.EP
    special_requests: Optional[str] = None
    preferred_room_id: Optional[int] = None  # specific room chosen by guest

    @field_validator("check_out_date")
    @classmethod
    def validate_dates(cls, checkout: date, values) -> date:
        checkin = values.data.get("check_in_date")
        if checkin and checkout <= checkin:
            raise ValueError("Check-out must be after check-in.")
        if checkin and (checkout - checkin).days > 90:
            raise ValueError("Booking cannot exceed 90 nights.")
        return checkout

    @field_validator("adults")
    @classmethod
    def validate_adults(cls, v: int) -> int:
        if v < 1 or v > 10:
            raise ValueError("Adults must be between 1 and 10.")
        return v


class BookingUpdate(BaseModel):
    check_in_date: Optional[date] = None
    check_out_date: Optional[date] = None
    adults: Optional[int] = None
    children: Optional[int] = None
    meal_plan: Optional[MealPlan] = None
    special_requests: Optional[str] = None
    room_id: Optional[int] = None


class BookingCancelRequest(BaseModel):
    reason: Optional[str] = None


class BookingResponse(BaseModel):
    id: int
    booking_ref: str
    guest_user_id: int
    hotel_id: int
    room_id: Optional[int] = None
    room_type_id: int
    check_in_date: date
    check_out_date: date
    actual_check_in: Optional[datetime] = None
    actual_check_out: Optional[datetime] = None
    adults: int
    children: int
    meal_plan: MealPlan
    status: BookingStatus
    source: BookingSource
    room_rate_per_night: Decimal
    num_nights: int
    subtotal: Decimal
    gst_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    special_requests: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class BookingListResponse(BaseModel):
    id: int
    booking_ref: str
    hotel_id: int
    check_in_date: date
    check_out_date: date
    num_nights: int
    adults: int
    status: BookingStatus
    total_amount: Decimal
    created_at: datetime

    class Config:
        from_attributes = True


class FolioItemCreate(BaseModel):
    description: str
    category: FolioItemCategory = FolioItemCategory.OTHERS
    quantity: int = 1
    unit_price: Decimal
    date: date


class FolioItemResponse(BaseModel):
    id: int
    folio_id: int
    description: str
    category: FolioItemCategory
    quantity: int
    unit_price: Decimal
    amount: Decimal
    date: date
    created_at: datetime

    class Config:
        from_attributes = True


class FolioResponse(BaseModel):
    id: int
    booking_id: int
    folio_number: str
    subtotal: Decimal
    gst_amount: Decimal
    total: Decimal
    paid: Decimal
    balance: Decimal
    is_closed: bool
    items: List[FolioItemResponse] = []
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    size: int
    pages: int