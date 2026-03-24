# Hotel Booking Platform — Phase 1: FastAPI Backend

## Tech Stack
- **Framework:** FastAPI + Python 3.11+
- **ORM:** SQLAlchemy 2.0 + Alembic migrations
- **Database:** MySQL (via PyMySQL)
- **Auth:** JWT (access + refresh tokens) + Phone OTP
- **Validation:** Pydantic v2
- **Indian Payment:** Razorpay (Phase 2) | Cash/UPI recording (Phase 1)

---

## Project Structure

```
hotel_backend/
├── app/
│   ├── main.py               # FastAPI app, middleware, routers
│   ├── config.py             # Settings from .env
│   ├── database.py           # SQLAlchemy engine + session
│   ├── dependencies.py       # JWT auth, RBAC dependencies
│   ├── models/
│   │   ├── user.py           # User, Guest, Staff, OTPSession
│   │   ├── hotel.py          # Hotel, RoomType, Room
│   │   ├── booking.py        # Booking, Folio, FolioItem
│   │   └── payment.py        # Payment, Refund
│   ├── schemas/
│   │   ├── auth.py           # Login, OTP, token schemas
│   │   ├── user.py           # User/Guest Pydantic schemas
│   │   ├── hotel.py          # Hotel/Room schemas
│   │   └── booking.py        # Booking/Folio schemas
│   ├── routers/
│   │   ├── auth.py           # /api/v1/auth/*
│   │   ├── users.py          # /api/v1/users/*
│   │   ├── hotels.py         # /api/v1/hotels/*
│   │   ├── bookings.py       # /api/v1/bookings/*
│   │   └── payments.py       # /api/v1/payments/*
│   ├── services/
│   │   └── booking_service.py # Core booking business logic + GST
│   └── utils/
│       ├── jwt.py            # Token create/verify
│       ├── security.py       # bcrypt password hashing
│       ├── otp.py            # OTP generate/verify/Msg91
│       └── helpers.py        # Slug, booking ref, GST calc
├── alembic/                  # DB migrations
├── seed_data.py              # Dev seed data
├── requirements.txt
├── alembic.ini
└── .env.example
```

---

## Quick Start

### 1. Setup Python environment

```bash
cd hotel_backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set your DATABASE_URL, SECRET_KEY, etc.
```

### 3. Create MySQL database

```sql
CREATE DATABASE hotel_booking_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 4. Run migrations

```bash
# Auto-create all tables from models (dev mode)
python -c "from app.database import init_db; init_db()"

# OR use Alembic for proper migrations
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

### 5. Seed sample data

```bash
python seed_data.py
```

### 6. Run the server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## API Endpoints

### Authentication
| Method | URL | Description |
|--------|-----|-------------|
| POST | `/api/v1/auth/register` | Register with phone + password |
| POST | `/api/v1/auth/login` | Login with phone + password |
| POST | `/api/v1/auth/send-otp` | Send OTP to phone |
| POST | `/api/v1/auth/verify-otp` | Verify OTP → returns tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET  | `/api/v1/auth/me` | Get current user |
| POST | `/api/v1/auth/logout` | Logout (client deletes tokens) |

### Users
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/v1/users/me` | Get full profile |
| PATCH | `/api/v1/users/me` | Update profile |
| GET | `/api/v1/users/me/guest-profile` | Get guest profile |
| PUT | `/api/v1/users/me/guest-profile` | Upsert guest profile |

### Hotels
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/v1/hotels/` | Search hotels |
| GET | `/api/v1/hotels/{id}` | Hotel detail |
| POST | `/api/v1/hotels/` | Create hotel (admin) |
| PATCH | `/api/v1/hotels/{id}` | Update hotel (admin) |
| GET | `/api/v1/hotels/{id}/room-types` | List room types |
| POST | `/api/v1/hotels/{id}/room-types` | Create room type (admin) |
| GET | `/api/v1/hotels/{id}/rooms` | List rooms (staff) |
| POST | `/api/v1/hotels/{id}/rooms` | Add room (admin) |
| PATCH | `/api/v1/hotels/rooms/{id}/status` | Update room status |

### Bookings
| Method | URL | Description |
|--------|-----|-------------|
| POST | `/api/v1/bookings/` | Create booking |
| GET | `/api/v1/bookings/my` | My bookings |
| GET | `/api/v1/bookings/availability` | Check availability |
| GET | `/api/v1/bookings/admin/all` | All bookings (staff) |
| GET | `/api/v1/bookings/{id}` | Booking detail |
| GET | `/api/v1/bookings/ref/{ref}` | By booking reference |
| POST | `/api/v1/bookings/{id}/cancel` | Cancel booking |
| POST | `/api/v1/bookings/{id}/checkin` | Check in (staff) |
| POST | `/api/v1/bookings/{id}/checkout` | Check out (staff) |
| GET | `/api/v1/bookings/{id}/folio` | Get folio/bill |
| POST | `/api/v1/bookings/{id}/folio/add-charge` | Add charge (staff) |

### Payments
| Method | URL | Description |
|--------|-----|-------------|
| POST | `/api/v1/payments/cash` | Record cash/UPI payment |
| GET | `/api/v1/payments/booking/{id}` | Payment history |
| GET | `/api/v1/payments/summary/{id}` | Payment summary |

---

## User Roles & Access

| Role | Access |
|------|--------|
| `guest` | Own bookings, own profile, search hotels |
| `staff` | All bookings, check-in/out, add charges, room status |
| `hotel_admin` | All staff actions + manage hotel, rooms, room types |
| `super_admin` | Full access, manage users, activate/deactivate |

---

## GST Calculation (India)

| Room Rate / Night | GST Rate |
|-------------------|----------|
| Up to ₹1,000 | 0% |
| ₹1,001 – ₹7,500 | 12% |
| Above ₹7,500 | 18% |

---

## Seeded Test Users

| Role | Phone | Password |
|------|-------|----------|
| Super Admin | 9000000001 | Admin@1234 |
| Hotel Admin | 9000000002 | Admin@1234 |
| Front Desk Staff | 9000000003 | Staff@1234 |
| Guest 1 (Hindi) | 9876543210 | Guest@1234 |
| Guest 2 | 9876543211 | Guest@1234 |

---

## What's Next — Phase 2

- Razorpay order creation + webhook verification
- GST invoice PDF generation (ReportLab)
- Email confirmations (SendGrid)
- Push notifications (Firebase FCM)
- Booking modification endpoint
