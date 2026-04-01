import httpx
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)
FCM_URL = "https://fcm.googleapis.com/fcm/send"


async def send_push_notification(
    fcm_token: str,
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> bool:
    """Send FCM push notification to a specific device token."""
    if not settings.FIREBASE_SERVER_KEY:
        logger.info(f"[DEV FCM] To: {fcm_token[:20]}... | {title}: {body}")
        return True

    payload = {
        "to": fcm_token,
        "notification": {"title": title, "body": body, "sound": "default"},
        "data": data or {},
        "priority": "high",
    }
    headers = {
        "Authorization": f"key={settings.FIREBASE_SERVER_KEY}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(FCM_URL, json=payload, headers=headers)
            result = r.json()
            if result.get("success") == 1:
                logger.info(f"FCM push sent successfully to {fcm_token[:20]}...")
                return True
            logger.warning(f"FCM push failed: {result}")
            return False
    except httpx.HTTPError as e:
        logger.error(f"FCM request failed: {e}")
        return False


async def send_booking_confirmed_push(fcm_token: str, booking_ref: str, hotel_name: str, check_in: str) -> bool:
    return await send_push_notification(
        fcm_token=fcm_token,
        title="Booking Confirmed!",
        body=f"{hotel_name} — Check-in on {check_in}",
        data={"type": "booking_confirmed", "booking_ref": booking_ref},
    )


async def send_checkin_reminder_push(fcm_token: str, booking_ref: str, hotel_name: str) -> bool:
    return await send_push_notification(
        fcm_token=fcm_token,
        title="Check-in Reminder",
        body=f"Your stay at {hotel_name} starts tomorrow. Ready?",
        data={"type": "checkin_reminder", "booking_ref": booking_ref},
    )


async def send_cancellation_push(fcm_token: str, booking_ref: str) -> bool:
    return await send_push_notification(
        fcm_token=fcm_token,
        title="Booking Cancelled",
        body=f"Your booking {booking_ref} has been cancelled.",
        data={"type": "booking_cancelled", "booking_ref": booking_ref},
    )


async def send_payment_success_push(fcm_token: str, amount: float, booking_ref: str) -> bool:
    return await send_push_notification(
        fcm_token=fcm_token,
        title="Payment Received",
        body=f"Rs. {amount:,.0f} paid for booking {booking_ref}.",
        data={"type": "payment_success", "booking_ref": booking_ref},
    )
