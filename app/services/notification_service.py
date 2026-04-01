import logging
from sqlalchemy.orm import Session
from app.models.user import User, Guest
from app.utils.email import (
    send_booking_confirmation, send_booking_cancellation, send_invoice_email,
)
from app.utils.fcm import (
    send_booking_confirmed_push, send_cancellation_push,
    send_payment_success_push, send_checkin_reminder_push,
)
from app.utils.otp import send_otp_msg91

logger = logging.getLogger(__name__)


async def notify_booking_confirmed(db: Session, booking, hotel, guest_user: User) -> None:
    """Send booking confirmation email + push notification."""
    try:
        await send_booking_confirmation(booking, hotel, guest_user)
        logger.info(f"Confirmation email sent for {booking.booking_ref}")
    except Exception as e:
        logger.error(f"Failed to send confirmation email for {booking.booking_ref}: {e}")

    guest = db.query(Guest).filter(Guest.user_id == guest_user.id).first()
    fcm_token = getattr(guest, "fcm_token", None) if guest else None
    if fcm_token:
        try:
            await send_booking_confirmed_push(
                fcm_token,
                booking.booking_ref,
                hotel.name,
                booking.check_in_date.strftime("%d %b %Y"),
            )
        except Exception as e:
            logger.error(f"FCM push failed for {booking.booking_ref}: {e}")


async def notify_booking_cancelled(db: Session, booking, hotel, guest_user: User) -> None:
    """Send cancellation email + push notification."""
    try:
        await send_booking_cancellation(booking, hotel, guest_user)
    except Exception as e:
        logger.error(f"Cancellation email failed for {booking.booking_ref}: {e}")

    guest = db.query(Guest).filter(Guest.user_id == guest_user.id).first()
    fcm_token = getattr(guest, "fcm_token", None) if guest else None
    if fcm_token:
        try:
            await send_cancellation_push(fcm_token, booking.booking_ref)
        except Exception as e:
            logger.error(f"FCM cancellation push failed: {e}")


async def notify_payment_success(db: Session, payment, booking, guest_user: User) -> None:
    """Push notification for successful payment."""
    guest = db.query(Guest).filter(Guest.user_id == guest_user.id).first()
    fcm_token = getattr(guest, "fcm_token", None) if guest else None
    if fcm_token:
        try:
            await send_payment_success_push(fcm_token, float(payment.amount), booking.booking_ref)
        except Exception as e:
            logger.error(f"Payment push failed: {e}")


async def send_invoice(booking, hotel, guest_user: User, folio, payments: list) -> None:
    """Generate and send PDF invoice via email."""
    try:
        from app.utils.pdf_invoice import generate_invoice_pdf
        pdf_bytes = generate_invoice_pdf(booking, hotel, guest_user, folio, payments)
        await send_invoice_email(booking, hotel, guest_user, pdf_bytes)
        logger.info(f"Invoice emailed for {booking.booking_ref}")
    except Exception as e:
        logger.error(f"Invoice email failed for {booking.booking_ref}: {e}")
