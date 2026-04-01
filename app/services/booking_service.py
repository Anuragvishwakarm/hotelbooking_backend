from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import date
from decimal import Decimal
from typing import Optional

from app.models.booking import Booking, Folio, FolioItem, BookingStatus, BookingSource, MealPlan
from app.models.hotel import Hotel, Room, RoomType, RoomStatus
from app.models.user import User, Guest
from app.utils.helpers import (
    generate_booking_ref, generate_folio_number,
    calculate_num_nights, calculate_gst,
)


class BookingConflictError(Exception):
    pass


class RoomNotAvailableError(Exception):
    pass


class InvalidBookingError(Exception):
    pass


def check_room_type_availability(
    db: Session,
    hotel_id: int,
    room_type_id: int,
    check_in: date,
    check_out: date,
) -> bool:
    """Check if at least one room of the given type is free for the date range."""
    all_rooms = db.query(Room).filter(
        Room.hotel_id == hotel_id,
        Room.room_type_id == room_type_id,
        Room.status.in_([RoomStatus.AVAILABLE, RoomStatus.CLEANING]),
    ).all()

    for room in all_rooms:
        if _is_room_free(db, room.id, check_in, check_out):
            return True
    return False


def _is_room_free(db: Session, room_id: int, check_in: date, check_out: date) -> bool:
    """Return True if no confirmed/checked-in booking overlaps this room and date range."""
    conflict = db.query(Booking).filter(
        Booking.room_id == room_id,
        Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.CHECKED_IN]),
        Booking.check_in_date < check_out,
        Booking.check_out_date > check_in,
    ).first()
    return conflict is None


def get_available_room(
    db: Session,
    hotel_id: int,
    room_type_id: int,
    check_in: date,
    check_out: date,
) -> Optional[Room]:
    """Return the first available room for the room type and dates."""
    rooms = db.query(Room).filter(
        Room.hotel_id == hotel_id,
        Room.room_type_id == room_type_id,
        Room.status.in_([RoomStatus.AVAILABLE, RoomStatus.CLEANING]),
    ).all()

    for room in rooms:
        if _is_room_free(db, room.id, check_in, check_out):
            return room
    return None


def calculate_booking_totals(
    room_type: RoomType,
    check_in: date,
    check_out: date,
) -> dict:
    """Calculate subtotal, GST and total for a booking."""
    num_nights = calculate_num_nights(check_in, check_out)
    rate = Decimal(str(room_type.base_price))
    subtotal = rate * num_nights
    gst = calculate_gst(subtotal, rate)
    total = subtotal + gst

    return {
        "room_rate_per_night": rate,
        "num_nights": num_nights,
        "subtotal": subtotal,
        "gst_amount": gst,
        "discount_amount": Decimal("0"),
        "total_amount": total,
    }


def create_booking(
    db: Session,
    guest_user: User,
    hotel_id: int,
    room_type_id: int,
    check_in: date,
    check_out: date,
    adults: int = 1,
    children: int = 0,
    meal_plan: MealPlan = MealPlan.EP,
    special_requests: str = None,
    source: BookingSource = BookingSource.ONLINE_WEB,
    preferred_room_id: int = None,
) -> Booking:
    """
    Full booking creation:
    1. Validate hotel and room type
    2. Check availability
    3. Calculate totals (with GST)
    4. Create Booking + Folio
    5. Add initial FolioItem for room charges
    """
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id, Hotel.is_active == True).first()
    if not hotel:
        raise InvalidBookingError("Hotel not found or inactive.")

    room_type = db.query(RoomType).filter(
        RoomType.id == room_type_id,
        RoomType.hotel_id == hotel_id,
        RoomType.is_active == True,
    ).first()
    if not room_type:
        raise InvalidBookingError("Room type not found or inactive.")

    if adults + children > room_type.max_occupancy:
        raise InvalidBookingError(
            f"Too many guests. Max occupancy for this room type is {room_type.max_occupancy}."
        )

    # Use preferred room if specified, else auto-assign
    if preferred_room_id:
        preferred = db.query(Room).filter(
            Room.id == preferred_room_id,
            Room.hotel_id == hotel_id,
            Room.room_type_id == room_type_id,
        ).first()
        if preferred and _is_room_free(db, preferred_room_id, check_in, check_out):
            available_room = preferred
        else:
            # Preferred room not free — fall back to auto-assign
            available_room = get_available_room(db, hotel_id, room_type_id, check_in, check_out)
    else:
        available_room = get_available_room(db, hotel_id, room_type_id, check_in, check_out)

    if not available_room:
        raise RoomNotAvailableError(
            "No rooms of this type are available for the selected dates."
        )

    totals = calculate_booking_totals(room_type, check_in, check_out)

    booking_ref = generate_booking_ref()
    while db.query(Booking).filter(Booking.booking_ref == booking_ref).first():
        booking_ref = generate_booking_ref()

    booking = Booking(
        booking_ref=booking_ref,
        guest_user_id=guest_user.id,
        hotel_id=hotel_id,
        room_id=available_room.id,
        room_type_id=room_type_id,
        check_in_date=check_in,
        check_out_date=check_out,
        adults=adults,
        children=children,
        meal_plan=meal_plan,
        status=BookingStatus.CONFIRMED,
        source=source,
        special_requests=special_requests,
        **totals,
    )
    db.add(booking)
    db.flush()

    folio_number = generate_folio_number()
    folio = Folio(
        booking_id=booking.id,
        folio_number=folio_number,
        subtotal=totals["subtotal"],
        gst_amount=totals["gst_amount"],
        total=totals["total_amount"],
        paid=Decimal("0"),
        balance=totals["total_amount"],
    )
    db.add(folio)
    db.flush()

    for night in range(totals["num_nights"]):
        from datetime import timedelta
        night_date = check_in + timedelta(days=night)
        item = FolioItem(
            folio_id=folio.id,
            description=f"Room charge: {room_type.name}",
            category="room",
            quantity=1,
            unit_price=totals["room_rate_per_night"],
            amount=totals["room_rate_per_night"],
            date=night_date,
        )
        db.add(item)

    guest = db.query(Guest).filter(Guest.user_id == guest_user.id).first()
    if guest:
        guest.total_stays = (guest.total_stays or 0) + 1

    db.commit()
    db.refresh(booking)
    return booking


def cancel_booking(
    db: Session,
    booking: Booking,
    cancelled_by: User,
    reason: str = None,
) -> Booking:
    """Cancel a booking. Only PENDING or CONFIRMED bookings can be cancelled."""
    if booking.status not in (BookingStatus.PENDING, BookingStatus.CONFIRMED):
        raise InvalidBookingError(
            f"Cannot cancel a booking with status '{booking.status.value}'."
        )

    from datetime import datetime, timezone
    booking.status = BookingStatus.CANCELLED
    booking.cancelled_at = datetime.now(timezone.utc)
    booking.cancellation_reason = reason
    booking.cancelled_by = cancelled_by.id

    if booking.room_id:
        room = db.query(Room).filter(Room.id == booking.room_id).first()
        if room and room.status == RoomStatus.OCCUPIED:
            room.status = RoomStatus.AVAILABLE

    db.commit()
    db.refresh(booking)
    return booking


def check_in_booking(
    db: Session,
    booking: Booking,
    checked_in_by: User,
    room_id: int = None,
) -> Booking:
    """Perform check-in. Optionally assign a specific room."""
    if booking.status != BookingStatus.CONFIRMED:
        raise InvalidBookingError(
            f"Cannot check in a booking with status '{booking.status.value}'."
        )

    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date()
    if booking.check_in_date > today:
        raise InvalidBookingError(
            f"Check-in date is {booking.check_in_date}. Cannot check in early."
        )

    if room_id:
        room = db.query(Room).filter(Room.id == room_id).first()
        if not room or room.hotel_id != booking.hotel_id:
            raise InvalidBookingError("Invalid room for this hotel.")
        if not _is_room_free(db, room_id, booking.check_in_date, booking.check_out_date):
            raise RoomNotAvailableError("Selected room is not available.")
        booking.room_id = room_id

    if booking.room_id:
        room = db.query(Room).filter(Room.id == booking.room_id).first()
        if room:
            room.status = RoomStatus.OCCUPIED

    booking.status = BookingStatus.CHECKED_IN
    booking.actual_check_in = datetime.now(timezone.utc)
    booking.checked_in_by = checked_in_by.id

    db.commit()
    db.refresh(booking)
    return booking


def check_out_booking(
    db: Session,
    booking: Booking,
    checked_out_by: User,
) -> Booking:
    """Perform check-out and release the room."""
    if booking.status != BookingStatus.CHECKED_IN:
        raise InvalidBookingError(
            f"Cannot check out a booking with status '{booking.status.value}'."
        )

    from datetime import datetime, timezone
    booking.status = BookingStatus.CHECKED_OUT
    booking.actual_check_out = datetime.now(timezone.utc)
    booking.checked_out_by = checked_out_by.id

    if booking.room_id:
        room = db.query(Room).filter(Room.id == booking.room_id).first()
        if room:
            room.status = RoomStatus.CLEANING

    if booking.folio:
        booking.folio.is_closed = True
        booking.folio.closed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(booking)
    return booking