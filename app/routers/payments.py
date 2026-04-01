from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.models.booking import Booking, Folio, BookingStatus
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.dependencies import get_current_user, require_staff

router = APIRouter(prefix="/payments", tags=["Payments"])


class CashPaymentRequest(BaseModel):
    booking_id: int
    amount: Decimal
    method: PaymentMethod = PaymentMethod.CASH
    notes: Optional[str] = None
    upi_transaction_id: Optional[str] = None


class PaymentResponse(BaseModel):
    id: int
    booking_id: int
    amount: Decimal
    method: PaymentMethod
    status: PaymentStatus
    paid_at: Optional[datetime] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


@router.post("/cash", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def record_cash_payment(
    payload: CashPaymentRequest,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """
    Record an offline cash / UPI / card payment.
    Used by the PyQt6 desktop at the front desk.
    """
    booking = db.query(Booking).filter(Booking.id == payload.booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")
    if booking.status not in (BookingStatus.CONFIRMED, BookingStatus.CHECKED_IN, BookingStatus.CHECKED_OUT):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot accept payment for booking with status '{booking.status.value}'.",
        )

    folio = db.query(Folio).filter(Folio.booking_id == payload.booking_id).first()
    if not folio:
        raise HTTPException(status_code=404, detail="Folio not found for this booking.")

    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be greater than zero.")
    if payload.amount > folio.balance:
        raise HTTPException(
            status_code=400,
            detail=f"Payment amount ₹{payload.amount} exceeds balance ₹{folio.balance}.",
        )

    payment = Payment(
        booking_id=payload.booking_id,
        amount=payload.amount,
        method=payload.method,
        status=PaymentStatus.SUCCESS,
        upi_transaction_id=payload.upi_transaction_id,
        notes=payload.notes,
        paid_at=datetime.now(timezone.utc),
        collected_by=current_user.id,
    )
    db.add(payment)

    folio.paid += payload.amount
    folio.balance = folio.total - folio.paid

    db.commit()
    db.refresh(payment)
    return payment


@router.get("/booking/{booking_id}", response_model=list[PaymentResponse])
def get_payments_for_booking(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all payments recorded for a booking."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")

    is_owner = booking.guest_user_id == current_user.id
    from app.models.user import UserRole
    is_staff = current_user.role in (UserRole.STAFF, UserRole.HOTEL_ADMIN, UserRole.SUPER_ADMIN)
    if not is_owner and not is_staff:
        raise HTTPException(status_code=403, detail="Access denied.")

    return db.query(Payment).filter(Payment.booking_id == booking_id).all()


@router.get("/summary/{booking_id}")
def payment_summary(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get payment summary — total, paid, balance — for a booking."""
    folio = db.query(Folio).filter(Folio.booking_id == booking_id).first()
    if not folio:
        raise HTTPException(status_code=404, detail="Folio not found.")

    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    is_owner = booking.guest_user_id == current_user.id
    from app.models.user import UserRole
    is_staff = current_user.role in (UserRole.STAFF, UserRole.HOTEL_ADMIN, UserRole.SUPER_ADMIN)
    if not is_owner and not is_staff:
        raise HTTPException(status_code=403, detail="Access denied.")

    return {
        "booking_id": booking_id,
        "folio_number": folio.folio_number,
        "subtotal": float(folio.subtotal),
        "gst_amount": float(folio.gst_amount),
        "total": float(folio.total),
        "paid": float(folio.paid),
        "balance": float(folio.balance),
        "is_settled": float(folio.balance) == 0,
    }
