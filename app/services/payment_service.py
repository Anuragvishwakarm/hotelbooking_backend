from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import datetime, timezone
import logging

from app.models.booking import Booking, Folio, BookingStatus
from app.models.payment import Payment, Refund, PaymentMethod, PaymentStatus, RefundStatus
from app.models.user import User
from app.utils.razorpay import (
    create_razorpay_order, verify_razorpay_signature,
    fetch_payment_details, create_razorpay_refund, rupees_to_paise,
)

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    pass


async def initiate_online_payment(
    db: Session,
    booking: Booking,
) -> dict:
    """
    Step 1 of online payment: Create a Razorpay order.
    Returns order details to be used by the frontend Razorpay checkout.
    """
    if booking.status not in (BookingStatus.PENDING, BookingStatus.CONFIRMED):
        raise PaymentError(f"Cannot initiate payment for booking with status '{booking.status.value}'.")

    folio = db.query(Folio).filter(Folio.booking_id == booking.id).first()
    if not folio:
        raise PaymentError("Folio not found for this booking.")

    amount_paise = rupees_to_paise(float(folio.balance))
    if amount_paise <= 0:
        raise PaymentError("No outstanding balance to pay.")

    order = await create_razorpay_order(amount_paise, booking.booking_ref)

    payment = Payment(
        booking_id=booking.id,
        amount=folio.balance,
        method=PaymentMethod.RAZORPAY,
        status=PaymentStatus.INITIATED,
        razorpay_order_id=order["id"],
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    return {
        "razorpay_order_id": order["id"],
        "amount_paise": amount_paise,
        "currency": "INR",
        "booking_ref": booking.booking_ref,
        "payment_id": payment.id,
    }


async def verify_and_complete_payment(
    db: Session,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
    collected_by_user_id: int = None,
) -> Payment:
    """
    Step 2: Verify Razorpay signature and mark payment as successful.
    This is triggered after the user completes payment on the frontend.
    """
    is_valid = verify_razorpay_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature)
    if not is_valid:
        raise PaymentError("Payment signature verification failed. Possible fraud attempt.")

    payment = db.query(Payment).filter(Payment.razorpay_order_id == razorpay_order_id).first()
    if not payment:
        raise PaymentError("Payment record not found for this Razorpay order.")

    payment.razorpay_payment_id = razorpay_payment_id
    payment.razorpay_signature  = razorpay_signature
    payment.status    = PaymentStatus.SUCCESS
    payment.paid_at   = datetime.now(timezone.utc)
    if collected_by_user_id:
        payment.collected_by = collected_by_user_id

    folio = db.query(Folio).filter(Folio.booking_id == payment.booking_id).first()
    if folio:
        folio.paid    += payment.amount
        folio.balance  = folio.total - folio.paid

    booking = db.query(Booking).filter(Booking.id == payment.booking_id).first()
    if booking and booking.status == BookingStatus.PENDING:
        booking.status = BookingStatus.CONFIRMED

    db.commit()
    db.refresh(payment)
    logger.info(f"Payment {razorpay_payment_id} verified and completed for booking {booking.booking_ref if booking else '?'}")
    return payment


async def process_refund(
    db: Session,
    payment: Payment,
    refund_amount: Decimal,
    reason: str,
    processed_by: User,
) -> Refund:
    """Initiate a Razorpay refund and record it in the DB."""
    if payment.status != PaymentStatus.SUCCESS:
        raise PaymentError("Can only refund a successful payment.")
    if refund_amount > payment.amount:
        raise PaymentError(f"Refund amount Rs.{refund_amount} exceeds payment Rs.{payment.amount}.")

    amount_paise = rupees_to_paise(float(refund_amount))
    rzp_refund = await create_razorpay_refund(payment.razorpay_payment_id, amount_paise, reason)

    refund = Refund(
        payment_id=payment.id,
        amount=refund_amount,
        reason=reason,
        status=RefundStatus.PROCESSED,
        razorpay_refund_id=rzp_refund.get("id"),
        processed_at=datetime.now(timezone.utc),
        processed_by=processed_by.id,
    )
    db.add(refund)

    if refund_amount == payment.amount:
        payment.status = PaymentStatus.REFUNDED
    else:
        payment.status = PaymentStatus.PARTIALLY_REFUNDED

    db.commit()
    db.refresh(refund)
    logger.info(f"Refund Rs.{refund_amount} processed for payment {payment.id}")
    return refund
