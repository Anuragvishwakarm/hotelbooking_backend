import asyncio
from app.utils.email import send_booking_confirmation

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import Optional, List
from datetime import date

from app.database import get_db
from app.models.user import User, UserRole
from app.models.booking import Booking, BookingStatus, BookingSource
from app.models.hotel import Hotel, RoomType, Room
from app.schemas.booking import (
    BookingCreate, BookingUpdate, BookingCancelRequest,
    BookingResponse, BookingListResponse,
    FolioItemCreate, FolioResponse,
    PaginatedResponse,
)
from app.dependencies import get_current_user, require_hotel_admin, require_staff
from app.services.booking_service import (
    create_booking, cancel_booking,
    check_in_booking, check_out_booking,
    check_room_type_availability,
    BookingConflictError, RoomNotAvailableError, InvalidBookingError,
)

router = APIRouter(prefix="/bookings", tags=["Bookings"])

@router.post("/", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def make_booking(
    payload: BookingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a booking for the current user."""
    try:
        booking = create_booking(
            db=db,
            guest_user=current_user,
            hotel_id=payload.hotel_id,
            room_type_id=payload.room_type_id,
            check_in=payload.check_in_date,
            check_out=payload.check_out_date,
            adults=payload.adults,
            children=payload.children,
            meal_plan=payload.meal_plan,
            special_requests=payload.special_requests,
            source=BookingSource.ONLINE_WEB,
            preferred_room_id=payload.preferred_room_id,
        )
    except RoomNotAvailableError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except InvalidBookingError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # ── Send booking confirmation email (background thread) ───────────────
    try:
        import threading
        import asyncio

        hotel = db.query(Hotel).filter(Hotel.id == booking.hotel_id).first()

        def _send_email_sync():
            """Run async email function in a new event loop (background thread)."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    send_booking_confirmation(booking, hotel, current_user)
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Email send failed: {e}")
            finally:
                loop.close()

        threading.Thread(target=_send_email_sync, daemon=True).start()

    except Exception as _e:
        pass  # Email failure should never break booking creation
    # ── Email block end ───────────────────────────────────────────────────

    return booking

@router.get("/my", response_model=List[BookingListResponse])
def my_bookings(
    booking_status: Optional[BookingStatus] = None,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all bookings for the current guest user."""
    query = db.query(Booking).filter(Booking.guest_user_id == current_user.id)
    if booking_status:
        query = query.filter(Booking.status == booking_status)
    offset = (page - 1) * size
    return query.order_by(Booking.created_at.desc()).offset(offset).limit(size).all()


@router.get("/availability")
def check_availability(
    hotel_id: int,
    room_type_id: int,
    check_in: date,
    check_out: date,
    adults: int = 1,
    children: int = 0,
    db: Session = Depends(get_db),
):
    """Check if a room type is available for given dates."""
    if check_out <= check_in:
        raise HTTPException(status_code=400, detail="Check-out must be after check-in.")

    rt = db.query(RoomType).filter(RoomType.id == room_type_id).first()
    if not rt:
        raise HTTPException(status_code=404, detail="Room type not found.")

    # Get all active rooms of this type
    from app.models.hotel import RoomStatus
    all_rooms = db.query(Room).filter(
        Room.hotel_id == hotel_id,
        Room.room_type_id == room_type_id,
        Room.status.in_([RoomStatus.AVAILABLE, RoomStatus.CLEANING]),
    ).all()

    # Find which rooms are already booked for these dates
    from app.models.booking import BookingStatus as BS
    booked_ids = {
        r[0] for r in db.query(Booking.room_id).filter(
            Booking.hotel_id == hotel_id,
            Booking.room_type_id == room_type_id,
            Booking.status.in_([BS.CONFIRMED, BS.CHECKED_IN]),
            Booking.check_in_date < check_out,
            Booking.check_out_date > check_in,
        ).all()
        if r[0] is not None
    }

    free_rooms = [r for r in all_rooms if r.id not in booked_ids]
    available  = len(free_rooms) > 0

    # Build enriched room list: id + number + floor, sorted by room number
    available_rooms = sorted(
        [{"room_id": r.id, "room_number": r.room_number, "floor": r.floor} for r in free_rooms],
        key=lambda x: x["room_number"],
    )

    from app.utils.helpers import calculate_num_nights, calculate_gst
    from decimal import Decimal
    num_nights = calculate_num_nights(check_in, check_out)
    rate       = Decimal(str(rt.base_price))
    subtotal   = rate * num_nights
    gst        = calculate_gst(subtotal, rate)

    return {
        "available":            available,
        "available_rooms_count": len(available_rooms),
        "available_rooms":      available_rooms,   # list of {room_id, room_number, floor}
        "hotel_id":             hotel_id,
        "room_type_id":         room_type_id,
        "check_in":             check_in,
        "check_out":            check_out,
        "num_nights":           num_nights,
        "rate_per_night":       float(rate),
        "subtotal":             float(subtotal),
        "gst_amount":           float(gst),
        "total_amount":         float(subtotal + gst),
    }


@router.get("/admin/all", response_model=List[BookingResponse])
def list_all_bookings(
    hotel_id: Optional[int] = None,
    booking_status: Optional[BookingStatus] = None,
    check_in_from: Optional[date] = None,
    check_in_to: Optional[date] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """List all bookings. Staff+ only with filters."""
    query = db.query(Booking)

    if hotel_id:
        query = query.filter(Booking.hotel_id == hotel_id)
    if booking_status:
        query = query.filter(Booking.status == booking_status)
    if check_in_from:
        query = query.filter(Booking.check_in_date >= check_in_from)
    if check_in_to:
        query = query.filter(Booking.check_in_date <= check_in_to)

    if search:
        query = query.join(User, Booking.guest_user_id == User.id).filter(
            User.full_name.ilike(f"%{search}%")
            | User.phone.ilike(f"%{search}%")
            | Booking.booking_ref.ilike(f"%{search}%")
        )

    offset = (page - 1) * size
    return query.order_by(Booking.created_at.desc()).offset(offset).limit(size).all()


@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get booking by ID. Users can only see their own bookings; staff see all."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")

    is_owner = booking.guest_user_id == current_user.id
    is_staff = current_user.role in (UserRole.STAFF, UserRole.HOTEL_ADMIN, UserRole.SUPER_ADMIN)
    if not is_owner and not is_staff:
        raise HTTPException(status_code=403, detail="Access denied.")

    return booking


@router.get("/ref/{booking_ref}", response_model=BookingResponse)
def get_booking_by_ref(
    booking_ref: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get booking by booking reference code."""
    booking = db.query(Booking).filter(Booking.booking_ref == booking_ref).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")
    is_owner = booking.guest_user_id == current_user.id
    is_staff = current_user.role in (UserRole.STAFF, UserRole.HOTEL_ADMIN, UserRole.SUPER_ADMIN)
    if not is_owner and not is_staff:
        raise HTTPException(status_code=403, detail="Access denied.")
    return booking


@router.post("/{booking_id}/cancel", response_model=BookingResponse)
def cancel_my_booking(
    booking_id: int,
    payload: BookingCancelRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel a booking. Users cancel their own; staff can cancel any."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")

    is_owner = booking.guest_user_id == current_user.id
    is_staff = current_user.role in (UserRole.STAFF, UserRole.HOTEL_ADMIN, UserRole.SUPER_ADMIN)
    if not is_owner and not is_staff:
        raise HTTPException(status_code=403, detail="Access denied.")

    try:
        return cancel_booking(db, booking, current_user, reason=payload.reason)
    except InvalidBookingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{booking_id}/checkin", response_model=BookingResponse)
def perform_checkin(
    booking_id: int,
    room_id: Optional[int] = None,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Check in a guest. Staff only. Optionally assign a specific room."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")
    try:
        return check_in_booking(db, booking, current_user, room_id=room_id)
    except (InvalidBookingError, RoomNotAvailableError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{booking_id}/checkout", response_model=BookingResponse)
def perform_checkout(
    booking_id: int,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Check out a guest. Staff only. Marks room for cleaning."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")
    try:
        return check_out_booking(db, booking, current_user)
    except InvalidBookingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{booking_id}/folio", response_model=FolioResponse)
def get_folio(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the folio (bill) for a booking."""
    from app.models.booking import Folio
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")

    is_owner = booking.guest_user_id == current_user.id
    is_staff = current_user.role in (UserRole.STAFF, UserRole.HOTEL_ADMIN, UserRole.SUPER_ADMIN)
    if not is_owner and not is_staff:
        raise HTTPException(status_code=403, detail="Access denied.")

    folio = db.query(Folio).filter(Folio.booking_id == booking_id).first()
    if not folio:
        raise HTTPException(status_code=404, detail="Folio not found.")
    return folio


@router.post("/{booking_id}/folio/add-charge", response_model=FolioResponse)
def add_folio_charge(
    booking_id: int,
    payload: FolioItemCreate,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Add an extra charge to a booking folio. Staff only."""
    from app.models.booking import Folio, FolioItem
    from decimal import Decimal

    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")
    if booking.status not in (BookingStatus.CONFIRMED, BookingStatus.CHECKED_IN):
        raise HTTPException(status_code=400, detail="Cannot add charges to this booking.")

    folio = db.query(Folio).filter(Folio.booking_id == booking_id).first()
    if not folio:
        raise HTTPException(status_code=404, detail="Folio not found.")
    if folio.is_closed:
        raise HTTPException(status_code=400, detail="Folio is already closed.")

    amount = Decimal(str(payload.unit_price)) * payload.quantity
    item = FolioItem(
        folio_id=folio.id,
        description=payload.description,
        category=payload.category,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        amount=amount,
        date=payload.date,
        added_by=current_user.id,
    )
    db.add(item)

    folio.subtotal += amount
    gst = calculate_gst_for_item(payload.category, amount)
    folio.gst_amount += gst
    folio.total += amount + gst
    folio.balance = folio.total - folio.paid

    db.commit()
    db.refresh(folio)
    return folio


def calculate_gst_for_item(category, amount):
    from decimal import Decimal
    from app.models.booking import FolioItemCategory
    gst_rates = {
        FolioItemCategory.ROOM: Decimal("0.18"),
        FolioItemCategory.FOOD_BEVERAGE: Decimal("0.05"),
        FolioItemCategory.LAUNDRY: Decimal("0.18"),
        FolioItemCategory.SPA: Decimal("0.18"),
        FolioItemCategory.MINIBAR: Decimal("0.18"),
    }
    rate = gst_rates.get(category, Decimal("0.18"))
    return (Decimal(str(amount)) * rate).quantize(Decimal("0.01"))