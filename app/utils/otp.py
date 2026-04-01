import random
import string
import httpx
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.config import settings
from app.models.user import OTPSession

logger = logging.getLogger(__name__)

OTP_EXPIRY_MINUTES = 5
MAX_OTP_ATTEMPTS = 3


def generate_otp(length: int = 6) -> str:
    """Generate a numeric OTP."""
    return "".join(random.choices(string.digits, k=length))


def create_otp_session(db: Session, phone: str, user_id: int = None) -> OTPSession:
    """Create a new OTP session and invalidate previous ones."""
    db.query(OTPSession).filter(
        OTPSession.phone == phone,
        OTPSession.is_used == False,
    ).update({"is_used": True})
    db.flush()

    otp_code = generate_otp()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)

    session = OTPSession(
        user_id=user_id,
        phone=phone,
        otp_code=otp_code,
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def verify_otp_session(db: Session, phone: str, otp: str) -> bool:
    """Verify OTP and mark as used. Returns True if valid."""
    session = (
        db.query(OTPSession)
        .filter(
            OTPSession.phone == phone,
            OTPSession.is_used == False,
        )
        .order_by(OTPSession.created_at.desc())
        .first()
    )

    if not session:
        logger.warning(f"No active OTP session for phone: {phone}")
        return False

    session.attempts += 1

    if session.attempts > MAX_OTP_ATTEMPTS:
        session.is_used = True
        db.commit()
        raise ValueError("Too many OTP attempts. Please request a new OTP.")

    if datetime.now(timezone.utc) > session.expires_at.replace(tzinfo=timezone.utc):
        session.is_used = True
        db.commit()
        raise ValueError("OTP has expired. Please request a new one.")

    if session.otp_code != otp:
        db.commit()
        return False

    session.is_used = True
    db.commit()
    return True


async def send_otp_msg91(phone: str, otp: str) -> bool:
    """Send OTP via Msg91 API."""
    if not settings.MSG91_AUTH_KEY:
        logger.info(f"[DEV MODE] OTP for {phone}: {otp}")
        return True

    url = "https://api.msg91.com/api/v5/otp"
    payload = {
        "template_id": settings.MSG91_TEMPLATE_ID,
        "mobile": f"91{phone}",
        "authkey": settings.MSG91_AUTH_KEY,
        "otp": otp,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            if data.get("type") == "success":
                logger.info(f"OTP sent successfully to {phone}")
                return True
            logger.error(f"Msg91 error: {data}")
            return False
    except httpx.HTTPError as e:
        logger.error(f"Failed to send OTP via Msg91: {e}")
        return False


def send_otp_sms_sync(phone: str, otp: str) -> bool:
    """Synchronous version — just log in dev mode."""
    if not settings.MSG91_AUTH_KEY:
        logger.info(f"[DEV MODE] OTP for +91{phone}: {otp}")
        return True
    return True
