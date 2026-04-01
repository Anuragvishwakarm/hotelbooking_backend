"""
app/utils/email.py — Email Service
HotelBook v2.0

Priority:
  1. SendGrid  — if SENDGRID_API_KEY is set in .env
  2. SMTP      — if SMTP_USER + SMTP_PASSWORD are set in .env (Gmail)
  3. Dev mode  — just logs to console, no email sent
"""

import logging
import smtplib
import asyncio
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional

import httpx
from app.config import settings

logger = logging.getLogger(__name__)
SENDGRID_URL = "https://api.sendgrid.com/v3/mail/send"


# ── HTML Templates ────────────────────────────────────────────────────────────

def _booking_html(booking, hotel, guest_name: str) -> str:
    try:
        total = f"{float(booking.total_amount):,.2f}"
    except:
        total = str(booking.total_amount)

    return f"""
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;max-width:620px;margin:auto;padding:20px;background:#f4f6f9;">

  <!-- Header -->
  <div style="background:#0f172a;padding:24px 28px;border-radius:10px 10px 0 0;">
    <h1 style="color:#ffffff;margin:0;font-size:22px;">🏨 HotelBook</h1>
    <p style="color:#94a3b8;margin:4px 0 0;font-size:13px;">Booking Confirmation</p>
  </div>

  <!-- Green bar -->
  <div style="background:#22c55e;padding:12px 28px;">
    <p style="margin:0;color:#ffffff;font-size:14px;font-weight:600;">✅ Your booking is confirmed!</p>
  </div>

  <!-- Body -->
  <div style="background:#ffffff;padding:28px;border-radius:0 0 10px 10px;">

    <p style="font-size:15px;color:#1e293b;">Dear <b>{guest_name}</b>,</p>
    <p style="color:#475569;font-size:14px;line-height:1.6;">
      Thank you for choosing <b>{hotel.name}</b>. Your reservation is confirmed.
    </p>

    <!-- Booking Ref -->
    <div style="background:#f0f9ff;border:2px solid #0ea5e9;border-radius:8px;padding:16px;text-align:center;margin:20px 0;">
      <p style="margin:0 0 4px;color:#0369a1;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:1px;">Booking Reference</p>
      <p style="margin:0;color:#0f172a;font-size:24px;font-weight:800;font-family:monospace;letter-spacing:2px;">{booking.booking_ref}</p>
    </div>

    <!-- Stay Details -->
    <table style="width:100%;border-collapse:collapse;margin-bottom:20px;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">
      <tr style="background:#f8fafc;">
        <td colspan="2" style="padding:12px 16px;font-weight:700;color:#0f172a;font-size:14px;">📅 Stay Details</td>
      </tr>
      <tr style="border-top:1px solid #f1f5f9;">
        <td style="padding:10px 16px;color:#64748b;font-size:13px;width:40%;">Check-in</td>
        <td style="padding:10px 16px;color:#16a34a;font-size:13px;font-weight:600;">{booking.check_in_date.strftime('%d %b %Y')} (from {hotel.check_in_time})</td>
      </tr>
      <tr style="border-top:1px solid #f1f5f9;background:#f8fafc;">
        <td style="padding:10px 16px;color:#64748b;font-size:13px;">Check-out</td>
        <td style="padding:10px 16px;color:#dc2626;font-size:13px;font-weight:600;">{booking.check_out_date.strftime('%d %b %Y')} (by {hotel.check_out_time})</td>
      </tr>
      <tr style="border-top:1px solid #f1f5f9;">
        <td style="padding:10px 16px;color:#64748b;font-size:13px;">Duration</td>
        <td style="padding:10px 16px;color:#0f172a;font-size:13px;font-weight:600;">{booking.num_nights} night(s)</td>
      </tr>
      <tr style="border-top:1px solid #f1f5f9;background:#f8fafc;">
        <td style="padding:10px 16px;color:#64748b;font-size:13px;">Guests</td>
        <td style="padding:10px 16px;color:#0f172a;font-size:13px;font-weight:600;">{booking.adults} Adults{f", {booking.children} Children" if booking.children else ""}</td>
      </tr>
    </table>

    <!-- Hotel Info -->
    <table style="width:100%;border-collapse:collapse;margin-bottom:20px;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">
      <tr style="background:#f8fafc;">
        <td colspan="2" style="padding:12px 16px;font-weight:700;color:#0f172a;font-size:14px;">🏨 Hotel Information</td>
      </tr>
      <tr style="border-top:1px solid #f1f5f9;">
        <td style="padding:10px 16px;color:#64748b;font-size:13px;width:40%;">Hotel</td>
        <td style="padding:10px 16px;color:#0f172a;font-size:13px;font-weight:600;">{hotel.name}</td>
      </tr>
      <tr style="border-top:1px solid #f1f5f9;background:#f8fafc;">
        <td style="padding:10px 16px;color:#64748b;font-size:13px;">Address</td>
        <td style="padding:10px 16px;color:#0f172a;font-size:13px;">{hotel.address}, {hotel.city}, {hotel.state}</td>
      </tr>
      <tr style="border-top:1px solid #f1f5f9;">
        <td style="padding:10px 16px;color:#64748b;font-size:13px;">Phone</td>
        <td style="padding:10px 16px;color:#0f172a;font-size:13px;">{hotel.phone}</td>
      </tr>
    </table>

    <!-- Amount -->
    <div style="background:#fef9f0;border:1px solid #fcd34d;border-radius:8px;padding:18px 20px;margin-bottom:20px;">
      <table style="width:100%;">
        <tr>
          <td style="color:#92400e;font-size:13px;">Room Charges</td>
          <td align="right" style="color:#1e293b;font-size:13px;font-weight:600;">Rs. {float(booking.subtotal):,.2f}</td>
        </tr>
        <tr>
          <td style="color:#92400e;font-size:13px;padding-top:6px;">GST</td>
          <td align="right" style="color:#1e293b;font-size:13px;font-weight:600;padding-top:6px;">Rs. {float(booking.gst_amount):,.2f}</td>
        </tr>
        <tr>
          <td style="padding-top:12px;border-top:1px solid #fcd34d;">
            <b style="color:#92400e;font-size:15px;">Total Amount</b>
          </td>
          <td align="right" style="padding-top:12px;border-top:1px solid #fcd34d;">
            <b style="color:#0f172a;font-size:20px;">Rs. {total}</b>
          </td>
        </tr>
      </table>
    </div>

    <!-- Note -->
    <div style="background:#f0fdf4;border-left:4px solid #22c55e;padding:12px 16px;border-radius:0 6px 6px 0;margin-bottom:20px;">
      <p style="margin:0;color:#166534;font-size:13px;">
        💡 <b>Payment at property.</b> Please carry a valid Government ID (Aadhaar / Passport / PAN) at check-in.
      </p>
    </div>

    <p style="color:#9ca3af;font-size:12px;text-align:center;margin:0;">
      © 2026 HotelBook · Thank you for your booking!
    </p>
  </div>

</body>
</html>"""


def _cancellation_html(booking, hotel, guest_name: str) -> str:
    return f"""
<!DOCTYPE html><html>
<body style="font-family:Arial,sans-serif;max-width:620px;margin:auto;padding:20px;">
  <div style="background:#dc2626;padding:24px 28px;border-radius:10px 10px 0 0;">
    <h1 style="color:white;margin:0;font-size:22px;">❌ Booking Cancelled</h1>
    <p style="color:#fca5a5;margin:4px 0 0;">{hotel.name}</p>
  </div>
  <div style="background:#fef2f2;padding:28px;border-radius:0 0 10px 10px;">
    <p>Dear <b>{guest_name}</b>,</p>
    <p>Your booking <b>{booking.booking_ref}</b> for <b>{hotel.name}</b>
      ({booking.check_in_date.strftime('%d %b %Y')} – {booking.check_out_date.strftime('%d %b %Y')})
      has been cancelled.</p>
    {"<p><b>Reason:</b> " + booking.cancellation_reason + "</p>" if booking.cancellation_reason else ""}
    <p style="color:#6b7280;font-size:13px;">
      Questions? Call us at {hotel.phone}.
    </p>
  </div>
</body></html>"""


# ── Core send logic ───────────────────────────────────────────────────────────

async def _send_via_sendgrid(
    to_email: str, to_name: str, subject: str, html_body: str,
    attachment_bytes: Optional[bytes] = None, attachment_name: str = "invoice.pdf"
) -> bool:
    payload = {
        "personalizations": [{"to": [{"email": to_email, "name": to_name}]}],
        "from": {"email": settings.FROM_EMAIL, "name": settings.SMTP_FROM_NAME},
        "subject": subject,
        "content": [{"type": "text/html", "value": html_body}],
    }
    if attachment_bytes:
        payload["attachments"] = [{
            "content":  base64.b64encode(attachment_bytes).decode(),
            "filename": attachment_name,
            "type":     "application/pdf",
        }]
    headers = {
        "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
        "Content-Type":  "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(SENDGRID_URL, json=payload, headers=headers)
            if r.status_code in (200, 202):
                logger.info(f"[SendGrid] Email sent to {to_email}: {subject}")
                return True
            logger.error(f"[SendGrid] Error {r.status_code}: {r.text}")
            return False
    except Exception as e:
        logger.error(f"[SendGrid] Failed: {e}")
        return False


def _send_via_smtp(
    to_email: str, to_name: str, subject: str, html_body: str,
    attachment_bytes: Optional[bytes] = None, attachment_name: str = "invoice.pdf"
) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USER}>"
        msg["To"]      = to_email

        msg.attach(MIMEText("Please view this email in an HTML-compatible email client.", "plain"))
        msg.attach(MIMEText(html_body, "html"))

        if attachment_bytes:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment_bytes)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{attachment_name}"')
            msg.attach(part)

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USER, to_email, msg.as_string())

        logger.info(f"[SMTP] Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"[SMTP] Failed: {e}")
        return False


async def _send_email(
    to_email: str, to_name: str, subject: str, html_body: str,
    attachment_bytes: Optional[bytes] = None, attachment_name: str = "invoice.pdf"
) -> bool:
    """
    Smart email sender:
    1. SendGrid  — if SENDGRID_API_KEY set
    2. SMTP      — if SMTP_USER + SMTP_PASSWORD set
    3. Dev log   — just log, no email
    """
    # Option 1: SendGrid
    if settings.SENDGRID_API_KEY:
        return await _send_via_sendgrid(to_email, to_name, subject, html_body, attachment_bytes, attachment_name)

    # Option 2: SMTP (Gmail)
    if settings.SMTP_USER and settings.SMTP_PASSWORD:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: _send_via_smtp(to_email, to_name, subject, html_body, attachment_bytes, attachment_name)
        )

    # Option 3: Dev mode
    logger.info(f"[DEV EMAIL] To: {to_email} | Subject: {subject}")
    return True


# ── Public functions ──────────────────────────────────────────────────────────

async def send_booking_confirmation(booking, hotel, guest_user) -> bool:
    if not guest_user.email:
        logger.info(f"No email for user {guest_user.id} — skipping confirmation email")
        return False
    return await _send_email(
        to_email  = guest_user.email,
        to_name   = guest_user.full_name,
        subject   = f"Booking Confirmed ✅ {booking.booking_ref} | {hotel.name}",
        html_body = _booking_html(booking, hotel, guest_user.full_name),
    )


async def send_booking_cancellation(booking, hotel, guest_user) -> bool:
    if not guest_user.email:
        return False
    return await _send_email(
        to_email  = guest_user.email,
        to_name   = guest_user.full_name,
        subject   = f"Booking Cancelled — {booking.booking_ref}",
        html_body = _cancellation_html(booking, hotel, guest_user.full_name),
    )


async def send_invoice_email(booking, hotel, guest_user, pdf_bytes: bytes) -> bool:
    if not guest_user.email:
        logger.info(f"[DEV] Invoice email skipped for user {guest_user.id}")
        return False
    return await _send_email(
        to_email         = guest_user.email,
        to_name          = guest_user.full_name,
        subject          = f"Invoice — {booking.booking_ref} | {hotel.name}",
        html_body        = f"<p>Dear {guest_user.full_name},<br/>Please find your invoice attached for booking <b>{booking.booking_ref}</b>.<br/><br/>Thank you for staying with {hotel.name}.</p>",
        attachment_bytes = pdf_bytes,
        attachment_name  = f"Invoice_{booking.booking_ref}.pdf",
    )