from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database import get_db
from app.models.user import User
from app.models.hotel import Hotel, RoomType, Room, RoomStatus
from app.schemas.hotel import (
    HotelCreate, HotelUpdate, HotelResponse, HotelListResponse,
    RoomTypeCreate, RoomTypeUpdate, RoomTypeResponse,
    RoomCreate, RoomUpdate, RoomResponse,
)
from app.dependencies import get_current_user, require_hotel_admin, require_super_admin, get_optional_user
from app.utils.helpers import generate_unique_slug

router = APIRouter(prefix="/hotels", tags=["Hotels"])


# ─── Helper ──────────────────────────────────────────────────────────────────

# Fields frontend sends that are NOT columns in Hotel model
# → stored inside the `policies` JSON column
_POLICY_KEYS = {'cancellation_policy', 'pet_policy', 'maps_link', 'category'}


def _apply_hotel_payload(hotel: Hotel, data: dict) -> Hotel:
    """
    Safely map frontend payload onto Hotel SQLAlchemy model.

    Two special cases:
    1. 'gstin'  → saved as 'gst_number'  (column name mismatch)
    2. policy fields  → merged into hotel.policies JSON column
    """
    # 1. gstin → gst_number
    if 'gstin' in data:
        val = data.pop('gstin')
        if val is not None:
            hotel.gst_number = val

    # 2. policy-like fields → policies JSON
    policy_data = dict(hotel.policies or {})
    for key in _POLICY_KEYS:
        if key in data:
            val = data.pop(key)
            if val is not None:
                policy_data[key] = val
    if policy_data:
        hotel.policies = policy_data

    # 3. remaining fields — only set if column actually exists on model
    for field, value in data.items():
        if hasattr(hotel, field):
            setattr(hotel, field, value)

    return hotel


# ─── Hotel Endpoints ──────────────────────────────────────────────────────────

@router.get("/", response_model=List[HotelListResponse])
def list_hotels(
    city: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    star_rating: Optional[int] = Query(None, ge=1, le=5),
    search: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None, description="Min room price per night"),
    max_price: Optional[float] = Query(None, description="Max room price per night"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """Public endpoint — list hotels with optional filters including price range."""
    from decimal import Decimal
    from sqlalchemy import func

    query = db.query(Hotel).filter(Hotel.is_active == True)

    if city:
        query = query.filter(Hotel.city.ilike(f"%{city}%"))
    if state:
        query = query.filter(Hotel.state.ilike(f"%{state}%"))
    if star_rating:
        query = query.filter(Hotel.star_rating == star_rating)
    if search:
        query = query.filter(
            Hotel.name.ilike(f"%{search}%") | Hotel.city.ilike(f"%{search}%")
        )

    if min_price is not None or max_price is not None:
        from sqlalchemy import select
        subq = (
            select(RoomType.hotel_id, func.min(RoomType.base_price).label("cheapest"))
            .group_by(RoomType.hotel_id)
            .subquery()
        )
        query = query.join(subq, Hotel.id == subq.c.hotel_id)
        if min_price is not None:
            query = query.filter(subq.c.cheapest >= Decimal(str(min_price)))
        if max_price is not None:
            query = query.filter(subq.c.cheapest <= Decimal(str(max_price)))

    offset = (page - 1) * size
    hotels = query.order_by(Hotel.name).offset(offset).limit(size).all()

    hotel_ids = [h.id for h in hotels]
    if hotel_ids:
        cheapest_map = dict(
            db.query(RoomType.hotel_id, func.min(RoomType.base_price))
            .filter(RoomType.hotel_id.in_(hotel_ids))
            .group_by(RoomType.hotel_id)
            .all()
        )
        for h in hotels:
            h.min_price = cheapest_map.get(h.id)

    return hotels


@router.get("/{hotel_id}", response_model=HotelResponse)
def get_hotel(
    hotel_id: int,
    db: Session = Depends(get_db),
):
    """Get full hotel details by ID."""
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id, Hotel.is_active == True).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found.")
    return hotel


@router.post("/", response_model=HotelResponse, status_code=status.HTTP_201_CREATED)
def create_hotel(
    payload: HotelCreate,
    current_user: User = Depends(require_hotel_admin),
    db: Session = Depends(get_db),
):
    """Create a new hotel. Hotel admin or super admin only."""
    slug  = generate_unique_slug(db, Hotel, payload.name)
    hotel = Hotel(slug=slug, created_by=current_user.id)
    data  = payload.model_dump(exclude_unset=True)
    hotel = _apply_hotel_payload(hotel, data)
    db.add(hotel)
    db.commit()
    db.refresh(hotel)
    return hotel


@router.patch("/{hotel_id}", response_model=HotelResponse)
def update_hotel(
    hotel_id: int,
    payload: HotelUpdate,
    current_user: User = Depends(require_hotel_admin),
    db: Session = Depends(get_db),
):
    """Update hotel details."""
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found.")

    data  = payload.model_dump(exclude_unset=True)
    hotel = _apply_hotel_payload(hotel, data)
    db.commit()
    db.refresh(hotel)
    return hotel


@router.delete("/{hotel_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_hotel(
    hotel_id: int,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Soft-delete (deactivate) a hotel. Super admin only."""
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found.")
    hotel.is_active = False
    db.commit()


# ─── Room Type Endpoints ──────────────────────────────────────────────────────

@router.get("/{hotel_id}/room-types", response_model=List[RoomTypeResponse])
def list_room_types(
    hotel_id: int,
    db: Session = Depends(get_db),
):
    """Get all room types for a hotel."""
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found.")
    return (
        db.query(RoomType)
        .filter(RoomType.hotel_id == hotel_id, RoomType.is_active == True)
        .all()
    )


@router.post("/{hotel_id}/room-types", response_model=RoomTypeResponse, status_code=201)
def create_room_type(
    hotel_id: int,
    payload: RoomTypeCreate,
    current_user: User = Depends(require_hotel_admin),
    db: Session = Depends(get_db),
):
    """Create a new room type under a hotel."""
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found.")

    # exclude hotel_id — comes from URL path, not body
    data = payload.model_dump(exclude={'hotel_id'})

    # only set fields that exist on RoomType model
    room_type = RoomType(hotel_id=hotel_id)
    for field, value in data.items():
        if hasattr(room_type, field):
            setattr(room_type, field, value)

    db.add(room_type)
    db.commit()
    db.refresh(room_type)
    return room_type


@router.patch("/room-types/{room_type_id}", response_model=RoomTypeResponse)
def update_room_type(
    room_type_id: int,
    payload: RoomTypeUpdate,
    current_user: User = Depends(require_hotel_admin),
    db: Session = Depends(get_db),
):
    """Update a room type."""
    rt = db.query(RoomType).filter(RoomType.id == room_type_id).first()
    if not rt:
        raise HTTPException(status_code=404, detail="Room type not found.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        if hasattr(rt, field):
            setattr(rt, field, value)

    db.commit()
    db.refresh(rt)
    return rt


# ─── Room Endpoints ───────────────────────────────────────────────────────────

@router.get("/{hotel_id}/rooms", response_model=List[RoomResponse])
def list_rooms(
    hotel_id: int,
    status: Optional[RoomStatus] = None,
    floor: Optional[int] = None,
    current_user: User = Depends(require_hotel_admin),
    db: Session = Depends(get_db),
):
    """List all rooms in a hotel with optional filters. Staff+ only."""
    query = db.query(Room).filter(Room.hotel_id == hotel_id)
    if status:
        query = query.filter(Room.status == status)
    if floor is not None:
        query = query.filter(Room.floor == floor)
    return query.order_by(Room.room_number).all()


@router.post("/{hotel_id}/rooms", response_model=RoomResponse, status_code=201)
def create_room(
    hotel_id: int,
    payload: RoomCreate,
    current_user: User = Depends(require_hotel_admin),
    db: Session = Depends(get_db),
):
    """Add a new room to a hotel."""
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found.")

    existing = db.query(Room).filter(
        Room.hotel_id == hotel_id,
        Room.room_number == payload.room_number,
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Room number '{payload.room_number}' already exists in this hotel.",
        )

    # exclude hotel_id — comes from URL path, not body
    room = Room(hotel_id=hotel_id)
    for field, value in payload.model_dump(exclude={'hotel_id'}).items():
        if hasattr(room, field):
            setattr(room, field, value)

    db.add(room)
    hotel.total_rooms = db.query(Room).filter(Room.hotel_id == hotel_id).count() + 1
    db.commit()
    db.refresh(room)
    return room


@router.patch("/rooms/{room_id}", response_model=RoomResponse)
def update_room(
    room_id: int,
    payload: RoomUpdate,
    current_user: User = Depends(require_hotel_admin),
    db: Session = Depends(get_db),
):
    """Update a room's details — room number, floor, type, status."""
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        if hasattr(room, field):
            setattr(room, field, value)

    db.commit()
    db.refresh(room)
    return room


@router.patch("/rooms/{room_id}/status")
def update_room_status(
    room_id: int,
    new_status: RoomStatus,
    current_user: User = Depends(require_hotel_admin),
    db: Session = Depends(get_db),
):
    """Quick update for room status — used by housekeeping."""
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found.")
    room.status = new_status
    db.commit()
    return {"room_id": room_id, "room_number": room.room_number, "status": new_status}