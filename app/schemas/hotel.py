from pydantic import BaseModel, field_validator
from typing import Optional, List, Any
from datetime import datetime
from decimal import Decimal
from app.models.hotel import RoomStatus, BedType


class HotelCreate(BaseModel):
    name: str
    description: Optional[str] = None
    star_rating: int = 3
    address: str
    city: str
    state: str
    pincode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: str
    email: Optional[str] = None
    check_in_time: str = "14:00"
    check_out_time: str = "11:00"
    amenities: Optional[List[str]] = None
    # frontend sends 'gstin' but DB column is 'gst_number' — mapped in router
    gstin: Optional[str] = None
    pan_number: Optional[str] = None
    # not DB columns — stored in policies JSON by router
    cancellation_policy: Optional[str] = None
    pet_policy: Optional[str] = None
    maps_link: Optional[str] = None
    category: Optional[str] = None

    @field_validator("star_rating")
    @classmethod
    def validate_star(cls, v: int) -> int:
        if v not in (1, 2, 3, 4, 5):
            raise ValueError("Star rating must be 1–5.")
        return v


class HotelUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    star_rating: Optional[int] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    amenities: Optional[List[str]] = None
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    cover_photo_url: Optional[str] = None
    is_active: Optional[bool] = None
    gstin: Optional[str] = None
    pan_number: Optional[str] = None
    cancellation_policy: Optional[str] = None
    pet_policy: Optional[str] = None
    maps_link: Optional[str] = None
    category: Optional[str] = None


class HotelResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    star_rating: int
    address: str
    city: str
    state: str
    pincode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    amenities: Optional[Any] = None
    cover_photo_url: Optional[str] = None
    total_rooms: int
    is_active: bool
    is_verified: bool
    created_at: datetime
    gst_number: Optional[str] = None       # actual DB column name
    pan_number: Optional[str] = None
    policies: Optional[Any] = None         # cancellation_policy etc. stored here

    class Config:
        from_attributes = True


class HotelListResponse(BaseModel):
    id: int
    name: str
    slug: str
    star_rating: int
    city: str
    state: str
    cover_photo_url: Optional[str] = None
    total_rooms: int
    is_active: bool
    amenities: Optional[Any] = None
    min_price: Optional[Decimal] = None

    class Config:
        from_attributes = True


class RoomTypeCreate(BaseModel):
    hotel_id: Optional[int] = None        # comes from URL path — excluded in router
    name: str
    description: Optional[str] = None
    bed_type: BedType = BedType.DOUBLE
    base_price: Decimal
    weekend_price: Optional[Decimal] = None
    max_occupancy: int = 2
    max_adults: int = 2
    max_children: int = 1
    area_sqft: Optional[float] = None
    amenities: Optional[List[str]] = None
    meal_plans: Optional[List[str]] = None  # DB column added in models/hotel.py

    @field_validator("base_price")
    @classmethod
    def validate_price(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Base price must be greater than 0.")
        return v


class RoomTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    base_price: Optional[Decimal] = None
    weekend_price: Optional[Decimal] = None
    max_occupancy: Optional[int] = None
    area_sqft: Optional[float] = None
    amenities: Optional[List[str]] = None
    meal_plans: Optional[List[str]] = None
    is_active: Optional[bool] = None


class RoomTypeResponse(BaseModel):
    id: int
    hotel_id: int
    name: str
    description: Optional[str] = None
    bed_type: BedType
    base_price: Decimal
    weekend_price: Optional[Decimal] = None
    max_occupancy: int
    max_adults: int
    max_children: int
    area_sqft: Optional[float] = None
    amenities: Optional[Any] = None
    meal_plans: Optional[Any] = None       # ← added
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class RoomCreate(BaseModel):
    hotel_id: Optional[int] = None        # comes from URL path — excluded in router
    room_type_id: int
    room_number: str
    floor: int
    status: Optional[RoomStatus] = None
    is_smoking: bool = False
    is_accessible: bool = False
    notes: Optional[str] = None


class RoomUpdate(BaseModel):
    room_number: Optional[str] = None
    floor: Optional[int] = None
    room_type_id: Optional[int] = None
    status: Optional[RoomStatus] = None
    is_smoking: Optional[bool] = None
    is_accessible: Optional[bool] = None
    notes: Optional[str] = None


class RoomResponse(BaseModel):
    id: int
    hotel_id: int
    room_type_id: int
    room_number: str
    floor: int
    status: RoomStatus
    is_smoking: bool
    is_accessible: bool
    notes: Optional[str] = None
    last_cleaned_at: Optional[datetime] = None
    room_type: Optional[RoomTypeResponse] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AvailabilityQuery(BaseModel):
    hotel_id: int
    check_in: str    # YYYY-MM-DD
    check_out: str   # YYYY-MM-DD
    adults: int = 1
    children: int = 0