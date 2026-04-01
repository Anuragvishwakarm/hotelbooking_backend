import httpx
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)
SENDGRID_URL = "https://api.sendgrid.com/v3/mail/send"


async def _send_email(to_email: str, to_name: str, subject: str, html_body: str) -> bool:
    if not settings.SENDGRID_API_KEY:
        logger.info(f"[DEV EMAIL] To: {to_email} | Subject: {subject}")
        return True
    payload = {
        "personalizations": [{"to": [{"email": to_email, "name": to_name}]}],
        "from": {"email": settings.FROM_EMAIL, "name": "Hotel Booking App"},
        "subject": subject,
        "content": [{"type": "text/html", "value": html_body}],
    }
    headers = {
        "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(SENDGRID_URL, json=payload, headers=headers)
            if r.status_code in (200, 202):
                logger.info(f"Email sent to {to_email}: {subject}")
                return True
            logger.error(f"SendGrid error {r.status_code}: {r.text}")
            return False
    except httpx.HTTPError as e:
        logger.error(f"Email send failed: {e}")
        return False


def _booking_html(booking, hotel, guest_name: str) -> str:
    return f"""
<!DOCTYPE html><html><body style="font-family:sans-serif;max-width:600px;margin:auto;padding:20px">
<div style="background:#1A3C5E;padding:20px;border-radius:8px 8px 0 0">
  <h1 style="color:white;margin:0;font-size:20px">{hotel.name}</h1>
  <p style="color:#B0C4DE;margin:4px 0 0">Booking Confirmation</p>
</div>
<div style="background:#F4F7FA;padding:24px;border-radius:0 0 8px 8px">
  <p style="font-size:16px">Dear <b>{guest_name}</b>,</p>
  <p>Your booking has been confirmed. Here are your details:</p>
  <table style="width:100%;border-collapse:collapse;margin:16px 0">
    <tr style="background:#1A3C5E;color:white">
      <th style="padding:10px;text-align:left;border-radius:4px 0 0 0">Detail</th>
      <th style="padding:10px;text-align:left;border-radius:0 4px 0 0">Value</th>
    </tr>
    <tr style="background:white"><td style="padding:10px;border-bottom:1px solid #E5E7EB">Booking Reference</td><td style="padding:10px;border-bottom:1px solid #E5E7EB"><b style="color:#1A3C5E;font-size:18px">{booking.booking_ref}</b></td></tr>
    <tr style="background:#F9FAFB"><td style="padding:10px;border-bottom:1px solid #E5E7EB">Hotel</td><td style="padding:10px;border-bottom:1px solid #E5E7EB">{hotel.name}, {hotel.city}</td></tr>
    <tr style="background:white"><td style="padding:10px;border-bottom:1px solid #E5E7EB">Check-in</td><td style="padding:10px;border-bottom:1px solid #E5E7EB">{booking.check_in_date.strftime('%d %b %Y')} (from {hotel.check_in_time})</td></tr>
    <tr style="background:#F9FAFB"><td style="padding:10px;border-bottom:1px solid #E5E7EB">Check-out</td><td style="padding:10px;border-bottom:1px solid #E5E7EB">{booking.check_out_date.strftime('%d %b %Y')} (by {hotel.check_out_time})</td></tr>
    <tr style="background:white"><td style="padding:10px;border-bottom:1px solid #E5E7EB">Nights</td><td style="padding:10px;border-bottom:1px solid #E5E7EB">{booking.num_nights}</td></tr>
    <tr style="background:#F9FAFB"><td style="padding:10px">Total Amount</td><td style="padding:10px"><b>Rs. {booking.total_amount:,.2f}</b> (incl. GST)</td></tr>
  </table>
  <div style="background:#D1FAE5;border-radius:6px;padding:12px;margin:16px 0">
    <p style="margin:0;color:#065F46">Show your <b>Booking Reference: {booking.booking_ref}</b> at check-in.</p>
  </div>
  <p style="color:#6B7280;font-size:13px">If you have any questions, call us at {hotel.phone}.</p>
  <p style="color:#9CA3AF;font-size:12px;margin-top:24px">Thank you for booking with {hotel.name}.</p>
</div>
</body></html>"""


def _cancellation_html(booking, hotel, guest_name: str) -> str:
    return f"""
<!DOCTYPE html><html><body style="font-family:sans-serif;max-width:600px;margin:auto;padding:20px">
<div style="background:#DC2626;padding:20px;border-radius:8px 8px 0 0">
  <h1 style="color:white;margin:0;font-size:20px">Booking Cancelled</h1>
  <p style="color:#FCA5A5;margin:4px 0 0">{hotel.name}</p>
</div>
<div style="background:#FEF2F2;padding:24px;border-radius:0 0 8px 8px">
  <p>Dear <b>{guest_name}</b>,</p>
  <p>Your booking <b>{booking.booking_ref}</b> for {hotel.name} ({booking.check_in_date.strftime('%d %b %Y')} – {booking.check_out_date.strftime('%d %b %Y')}) has been cancelled.</p>
  {"<p>Reason: " + booking.cancellation_reason + "</p>" if booking.cancellation_reason else ""}
  <p style="color:#6B7280;font-size:13px">If you did not request this cancellation, please contact us immediately at {hotel.phone}.</p>
</div>
</body></html>"""


async def send_booking_confirmation(booking, hotel, guest_user) -> bool:
    html = _booking_html(booking, hotel, guest_user.full_name)
    if not guest_user.email:
        logger.info(f"No email for user {guest_user.id} — skipping confirmation email")
        return False
    return await _send_email(
        to_email=guest_user.email,
        to_name=guest_user.full_name,
        subject=f"Booking Confirmed — {booking.booking_ref} | {hotel.name}",
        html_body=html,
    )


async def send_booking_cancellation(booking, hotel, guest_user) -> bool:
    if not guest_user.email:
        return False
    html = _cancellation_html(booking, hotel, guest_user.full_name)
    return await _send_email(
        to_email=guest_user.email,
        to_name=guest_user.full_name,
        subject=f"Booking Cancelled — {booking.booking_ref}",
        html_body=html,
    )


async def send_invoice_email(booking, hotel, guest_user, pdf_bytes: bytes) -> bool:
    """Send invoice as base64 attachment via SendGrid."""
    if not guest_user.email or not settings.SENDGRID_API_KEY:
        logger.info(f"[DEV] Invoice email skipped for user {guest_user.id}")
        return False
    import base64
    payload = {
        "personalizations": [{"to": [{"email": guest_user.email, "name": guest_user.full_name}]}],
        "from": {"email": settings.FROM_EMAIL, "name": hotel.name},
        "subject": f"Invoice — {booking.booking_ref} | {hotel.name}",
        "content": [{
            "type": "text/html",
            "value": f"<p>Dear {guest_user.full_name},<br/>Please find your invoice attached for booking <b>{booking.booking_ref}</b>.<br/><br/>Thank you for staying with us.</p>",
        }],
        "attachments": [{
            "content": base64.b64encode(pdf_bytes).decode(),
            "filename": f"Invoice_{booking.booking_ref}.pdf",
            "type": "application/pdf",
        }],
    }
    headers = {"Authorization": f"Bearer {settings.SENDGRID_API_KEY}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(SENDGRID_URL, json=payload, headers=headers)
        return r.status_code in (200, 202)
