import re
import random
import string
from datetime import datetime
from decimal import Decimal


def slugify(text: str) -> str:
    """Convert hotel name to URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text


def generate_unique_slug(db, model, name: str) -> str:
    """Generate a unique slug, appending a number if needed."""
    base_slug = slugify(name)
    slug = base_slug
    counter = 1
    while db.query(model).filter(model.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


def generate_booking_ref() -> str:
    """Generate a booking reference like HTL-20241201-A3B4C."""
    today = datetime.now().strftime("%Y%m%d")
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"HTL-{today}-{suffix}"


def generate_folio_number() -> str:
    """Generate a folio number like FLO-20241201-12345."""
    today = datetime.now().strftime("%Y%m%d")
    num = random.randint(10000, 99999)
    return f"FLO-{today}-{num}"


def calculate_gst(amount: Decimal, room_rate: Decimal) -> Decimal:
    """
    GST on hotel rooms (India):
    - Up to ₹1000/night  → 0%
    - ₹1001–₹7500/night  → 12%
    - Above ₹7500/night  → 18%
    """
    if room_rate <= Decimal("1000"):
        rate = Decimal("0")
    elif room_rate <= Decimal("7500"):
        rate = Decimal("0.12")
    else:
        rate = Decimal("0.18")
    return (amount * rate).quantize(Decimal("0.01"))


def calculate_num_nights(check_in, check_out) -> int:
    """Calculate number of nights between two dates."""
    delta = check_out - check_in
    return max(delta.days, 1)


def mask_phone(phone: str) -> str:
    """Return masked phone: 98*****01"""
    if len(phone) < 4:
        return phone
    return phone[:2] + "*" * (len(phone) - 4) + phone[-2:]


def mask_email(email: str) -> str:
    """Return masked email: us****@example.com"""
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    masked_local = local[:2] + "*" * max(len(local) - 2, 0)
    return f"{masked_local}@{domain}"
