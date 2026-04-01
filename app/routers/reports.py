from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import date, timedelta, datetime
from decimal import Decimal
from typing import Optional
import io

from app.database import get_db
from app.models.user import User
from app.models.hotel import Hotel, Room, RoomType, RoomStatus
from app.models.booking import Booking, BookingStatus, BookingSource
from app.models.payment import Payment, PaymentStatus
from app.dependencies import require_hotel_admin, require_staff

router = APIRouter(prefix="/reports", tags=["Reports"])


def _date_range(from_date: Optional[date], to_date: Optional[date]):
    if not from_date:
        from_date = date.today().replace(day=1)
    if not to_date:
        to_date = date.today()
    return from_date, to_date


@router.get("/daily-summary")
def daily_summary(
    hotel_id: int,
    report_date: Optional[date] = None,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Today's arrivals, departures, occupancy, revenue — for the night audit."""
    if not report_date:
        report_date = date.today()

    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found.")

    arrivals = db.query(Booking).filter(
        Booking.hotel_id == hotel_id,
        Booking.check_in_date == report_date,
        Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.CHECKED_IN]),
    ).all()

    departures = db.query(Booking).filter(
        Booking.hotel_id == hotel_id,
        Booking.check_out_date == report_date,
        Booking.status.in_([BookingStatus.CHECKED_IN, BookingStatus.CHECKED_OUT]),
    ).all()

    currently_in = db.query(Booking).filter(
        Booking.hotel_id == hotel_id,
        Booking.check_in_date <= report_date,
        Booking.check_out_date > report_date,
        Booking.status == BookingStatus.CHECKED_IN,
    ).count()

    total_rooms = db.query(Room).filter(Room.hotel_id == hotel_id).count()
    occupancy_pct = round((currently_in / total_rooms * 100), 1) if total_rooms > 0 else 0

    revenue_result = db.query(func.sum(Payment.amount)).join(
        Booking, Payment.booking_id == Booking.id
    ).filter(
        Booking.hotel_id == hotel_id,
        Payment.status == PaymentStatus.SUCCESS,
        func.date(Payment.paid_at) == report_date,
    ).scalar()
    revenue = float(revenue_result or 0)

    room_status_counts = {}
    for status in RoomStatus:
        count = db.query(Room).filter(Room.hotel_id == hotel_id, Room.status == status).count()
        room_status_counts[status.value] = count

    return {
        "hotel_id": hotel_id,
        "hotel_name": hotel.name,
        "report_date": report_date,
        "arrivals_count": len(arrivals),
        "arrivals": [{"booking_ref": b.booking_ref, "guest_name": b.guest_user.full_name if b.guest_user else "—", "check_in": b.check_in_date, "room_type": b.room_type.name if b.room_type else "—"} for b in arrivals],
        "departures_count": len(departures),
        "departures": [{"booking_ref": b.booking_ref, "guest_name": b.guest_user.full_name if b.guest_user else "—", "check_out": b.check_out_date} for b in departures],
        "currently_occupied": currently_in,
        "total_rooms": total_rooms,
        "occupancy_pct": occupancy_pct,
        "revenue_today": revenue,
        "room_status": room_status_counts,
    }


@router.get("/occupancy")
def occupancy_report(
    hotel_id: int,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    current_user: User = Depends(require_hotel_admin),
    db: Session = Depends(get_db),
):
    """Daily occupancy % for a date range — used to draw calendar heatmap."""
    from_date, to_date = _date_range(from_date, to_date)
    if (to_date - from_date).days > 365:
        raise HTTPException(status_code=400, detail="Date range cannot exceed 365 days.")

    total_rooms = db.query(Room).filter(Room.hotel_id == hotel_id).count()
    if total_rooms == 0:
        raise HTTPException(status_code=400, detail="No rooms found for this hotel.")

    results = []
    current = from_date
    while current <= to_date:
        occupied = db.query(Booking).filter(
            Booking.hotel_id == hotel_id,
            Booking.check_in_date <= current,
            Booking.check_out_date > current,
            Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.CHECKED_IN, BookingStatus.CHECKED_OUT]),
        ).count()
        results.append({
            "date": current,
            "occupied": occupied,
            "available": total_rooms - occupied,
            "occupancy_pct": round(occupied / total_rooms * 100, 1),
        })
        current += timedelta(days=1)

    avg_occ = round(sum(r["occupancy_pct"] for r in results) / len(results), 1) if results else 0

    return {
        "hotel_id": hotel_id,
        "from_date": from_date,
        "to_date": to_date,
        "total_rooms": total_rooms,
        "average_occupancy_pct": avg_occ,
        "daily": results,
    }


@router.get("/revenue")
def revenue_report(
    hotel_id: int,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    current_user: User = Depends(require_hotel_admin),
    db: Session = Depends(get_db),
):
    """Revenue breakdown by date — for the revenue trend chart."""
    from_date, to_date = _date_range(from_date, to_date)

    payments = db.query(
        func.date(Payment.paid_at).label("pay_date"),
        func.sum(Payment.amount).label("total"),
        func.count(Payment.id).label("count"),
    ).join(Booking, Payment.booking_id == Booking.id).filter(
        Booking.hotel_id == hotel_id,
        Payment.status == PaymentStatus.SUCCESS,
        func.date(Payment.paid_at) >= from_date,
        func.date(Payment.paid_at) <= to_date,
    ).group_by(func.date(Payment.paid_at)).all()

    daily_map = {str(row.pay_date): {"revenue": float(row.total), "transactions": row.count} for row in payments}

    results = []
    current = from_date
    while current <= to_date:
        key = str(current)
        results.append({"date": current, **daily_map.get(key, {"revenue": 0, "transactions": 0})})
        current += timedelta(days=1)

    total_revenue = sum(r["revenue"] for r in results)
    total_txns    = sum(r["transactions"] for r in results)

    booking_sources = db.query(
        Booking.source, func.count(Booking.id).label("count")
    ).filter(
        Booking.hotel_id == hotel_id,
        Booking.check_in_date >= from_date,
        Booking.check_in_date <= to_date,
        Booking.status != BookingStatus.CANCELLED,
    ).group_by(Booking.source).all()

    return {
        "hotel_id": hotel_id,
        "from_date": from_date,
        "to_date": to_date,
        "total_revenue": total_revenue,
        "total_transactions": total_txns,
        "booking_sources": {row.source.value: row.count for row in booking_sources},
        "daily": results,
    }


@router.get("/kpi")
def kpi_dashboard(
    hotel_id: int,
    period_days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_hotel_admin),
    db: Session = Depends(get_db),
):
    """
    KPI summary card data — Occupancy%, ADR, RevPAR, total bookings.
    Used by the admin dashboard.
    """
    to_date   = date.today()
    from_date = to_date - timedelta(days=period_days)

    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found.")

    total_rooms = db.query(Room).filter(Room.hotel_id == hotel_id).count()

    bookings = db.query(Booking).filter(
        Booking.hotel_id == hotel_id,
        Booking.check_in_date >= from_date,
        Booking.check_in_date <= to_date,
        Booking.status != BookingStatus.CANCELLED,
    ).all()

    confirmed = [b for b in bookings if b.status != BookingStatus.CANCELLED]
    cancelled = [b for b in db.query(Booking).filter(
        Booking.hotel_id == hotel_id,
        Booking.created_at >= datetime.combine(from_date, datetime.min.time()),
        Booking.status == BookingStatus.CANCELLED,
    ).all()]

    total_room_nights = sum(b.num_nights for b in confirmed)
    total_revenue = float(db.query(func.sum(Payment.amount)).join(
        Booking, Payment.booking_id == Booking.id
    ).filter(
        Booking.hotel_id == hotel_id,
        Payment.status == PaymentStatus.SUCCESS,
        func.date(Payment.paid_at) >= from_date,
    ).scalar() or 0)

    adr     = round(total_revenue / total_room_nights, 2) if total_room_nights > 0 else 0
    revpar  = round(total_revenue / (total_rooms * period_days), 2) if total_rooms > 0 else 0
    avg_occ = round(total_room_nights / (total_rooms * period_days) * 100, 1) if total_rooms > 0 else 0

    return {
        "hotel_id": hotel_id,
        "hotel_name": hotel.name,
        "period_days": period_days,
        "from_date": from_date,
        "to_date": to_date,
        "total_rooms": total_rooms,
        "kpi": {
            "occupancy_pct": avg_occ,
            "adr": adr,
            "revpar": revpar,
            "total_bookings": len(confirmed),
            "cancelled_bookings": len(cancelled),
            "total_revenue": total_revenue,
            "total_room_nights": total_room_nights,
        },
    }


@router.get("/arrivals-departures")
def arrivals_departures_report(
    hotel_id: int,
    report_date: Optional[date] = None,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Guest registry list for police report compliance (mandatory in India)."""
    if not report_date:
        report_date = date.today()

    arrivals = db.query(Booking).filter(
        Booking.hotel_id == hotel_id,
        Booking.check_in_date == report_date,
        Booking.status != BookingStatus.CANCELLED,
    ).all()

    departures = db.query(Booking).filter(
        Booking.hotel_id == hotel_id,
        Booking.check_out_date == report_date,
        Booking.status != BookingStatus.CANCELLED,
    ).all()

    def _format(b):
        guest = b.guest_user
        return {
            "booking_ref": b.booking_ref,
            "guest_name":  guest.full_name if guest else "—",
            "phone":       guest.phone if guest else "—",
            "room_type":   b.room_type.name if b.room_type else "—",
            "room_number": b.room.room_number if b.room else "Unassigned",
            "nights":      b.num_nights,
            "adults":      b.adults,
            "children":    b.children,
            "total_amount": float(b.total_amount),
            "status":      b.status.value,
        }

    return {
        "report_date": report_date,
        "hotel_id": hotel_id,
        "arrivals":   [_format(b) for b in arrivals],
        "departures": [_format(b) for b in departures],
    }
