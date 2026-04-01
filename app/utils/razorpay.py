import hmac
import hashlib
import httpx
import base64
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)
RAZORPAY_BASE_URL = "https://api.razorpay.com/v1"


def _get_auth_header() -> dict:
    credentials = f"{settings.RAZORPAY_KEY_ID}:{settings.RAZORPAY_KEY_SECRET}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return {"Authorization": f"Basic {encoded}", "Content-Type": "application/json"}


async def create_razorpay_order(amount_paise: int, booking_ref: str, currency: str = "INR") -> dict:
    """Create Razorpay order. amount_paise = INR * 100."""
    if not settings.RAZORPAY_KEY_ID:
        logger.info(f"[DEV] Mock Razorpay order for {booking_ref}: Rs.{amount_paise/100}")
        return {
            "id": f"order_DEV_{booking_ref}",
            "amount": amount_paise,
            "amount_paid": 0,
            "amount_due": amount_paise,
            "currency": currency,
            "receipt": booking_ref,
            "status": "created",
        }
    payload = {
        "amount": amount_paise,
        "currency": currency,
        "receipt": booking_ref,
        "notes": {"booking_ref": booking_ref},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{RAZORPAY_BASE_URL}/orders", json=payload, headers=_get_auth_header())
        r.raise_for_status()
        return r.json()


def verify_razorpay_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """HMAC-SHA256 signature verification. Always run before marking payment success."""
    if not settings.RAZORPAY_KEY_SECRET:
        logger.warning("[DEV] Skipping Razorpay signature verification.")
        return True
    message = f"{order_id}|{payment_id}"
    expected = hmac.new(settings.RAZORPAY_KEY_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def fetch_payment_details(payment_id: str) -> Optional[dict]:
    if not settings.RAZORPAY_KEY_ID:
        return {"id": payment_id, "status": "captured", "method": "upi"}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{RAZORPAY_BASE_URL}/payments/{payment_id}", headers=_get_auth_header())
        return r.json() if r.status_code == 200 else None


async def create_razorpay_refund(payment_id: str, amount_paise: int, reason: str = "") -> dict:
    if not settings.RAZORPAY_KEY_ID:
        return {"id": f"rfnd_DEV_{payment_id}", "status": "processed"}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            f"{RAZORPAY_BASE_URL}/payments/{payment_id}/refund",
            json={"amount": amount_paise, "notes": {"reason": reason}},
            headers=_get_auth_header(),
        )
        r.raise_for_status()
        return r.json()


def rupees_to_paise(rupees: float) -> int:
    return int(round(rupees * 100))

def paise_to_rupees(paise: int) -> float:
    return paise / 100
