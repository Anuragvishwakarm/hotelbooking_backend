"""
Seed script — populates the DB with sample data for development.
Run: python seed_data.py
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.database import SessionLocal, init_db
from app.models.user import User, Guest, Staff, UserRole, StaffRole
from app.models.hotel import Hotel, RoomType, Room, BedType, RoomStatus
from app.models.booking import Booking, Folio, FolioItem, MealPlan, BookingSource
from app.utils.security import hash_password
from app.utils.helpers import generate_unique_slug, generate_booking_ref, generate_folio_number, calculate_num_nights, calculate_gst
from datetime import date, timedelta
from decimal import Decimal


def seed():
    init_db()
    db = SessionLocal()

    print("Seeding users...")

    super_admin = User(
        full_name="Super Admin",
        email="admin@hotelapp.com",
        phone="9000000001",
        hashed_password=hash_password("Admin@1234"),
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        is_verified=True,
    )

    hotel_admin = User(
        full_name="Rajesh Sharma",
        email="rajesh@grandhotel.com",
        phone="9000000002",
        hashed_password=hash_password("Admin@1234"),
        role=UserRole.HOTEL_ADMIN,
        is_active=True,
        is_verified=True,
    )

    staff_user = User(
        full_name="Priya Gupta",
        email="priya@grandhotel.com",
        phone="9000000003",
        hashed_password=hash_password("Staff@1234"),
        role=UserRole.STAFF,
        is_active=True,
        is_verified=True,
    )

    guest1 = User(
        full_name="Amit Kumar",
        email="amit@gmail.com",
        phone="9876543210",
        hashed_password=hash_password("Guest@1234"),
        role=UserRole.GUEST,
        is_active=True,
        is_verified=True,
        preferred_language="hi",
    )

    guest2 = User(
        full_name="Sunita Verma",
        email="sunita@gmail.com",
        phone="9876543211",
        hashed_password=hash_password("Guest@1234"),
        role=UserRole.GUEST,
        is_active=True,
        is_verified=True,
    )

    for u in [super_admin, hotel_admin, staff_user, guest1, guest2]:
        existing = db.query(User).filter(User.phone == u.phone).first()
        if not existing:
            db.add(u)

    db.flush()

    for u in [guest1, guest2]:
        existing_guest = db.query(Guest).filter(Guest.user_id == u.id).first()
        if not existing_guest:
            g = Guest(user_id=u.id, nationality="Indian", city="Delhi", state="Delhi")
            db.add(g)

    db.commit()
    print("  Users seeded.")

    print("Seeding hotel...")

    existing_hotel = db.query(Hotel).filter(Hotel.slug == "grand-palace-hotel-delhi").first()
    if not existing_hotel:
        hotel = Hotel(
            name="Grand Palace Hotel",
            slug="grand-palace-hotel-delhi",
            description="A luxury 5-star hotel in the heart of New Delhi with world-class amenities.",
            star_rating=5,
            address="12, Connaught Place",
            city="New Delhi",
            state="Delhi",
            pincode="110001",
            latitude=28.6315,
            longitude=77.2167,
            phone="01123456789",
            email="info@grandpalace.com",
            check_in_time="14:00",
            check_out_time="12:00",
            amenities=["WiFi", "Swimming Pool", "Gym", "Spa", "Restaurant", "Bar", "Parking", "24hr Room Service"],
            gst_number="07AABCU9603R1ZX",
            pan_number="AABCU9603R",
            created_by=hotel_admin.id,
            is_active=True,
            is_verified=True,
        )
        db.add(hotel)
        db.flush()

        staff = Staff(
            user_id=staff_user.id,
            hotel_id=hotel.id,
            staff_role=StaffRole.FRONT_DESK,
            employee_id="EMP001",
            shift="morning",
        )
        db.add(staff)

        rt_standard = RoomType(
            hotel_id=hotel.id,
            name="Standard Room",
            description="Comfortable room with city view, queen bed, AC.",
            bed_type=BedType.QUEEN,
            base_price=Decimal("2500"),
            max_occupancy=2,
            max_adults=2,
            max_children=1,
            area_sqft=250,
            amenities=["AC", "TV", "WiFi", "Hot Water", "Wardrobe"],
        )

        rt_deluxe = RoomType(
            hotel_id=hotel.id,
            name="Deluxe Room",
            description="Spacious room with pool view, king bed, mini bar.",
            bed_type=BedType.KING,
            base_price=Decimal("5000"),
            max_occupancy=3,
            max_adults=2,
            max_children=1,
            area_sqft=380,
            amenities=["AC", "TV", "WiFi", "Mini Bar", "Bathtub", "Pool View"],
        )

        rt_suite = RoomType(
            hotel_id=hotel.id,
            name="Premium Suite",
            description="Luxury suite with separate living area, king bed, jacuzzi, butler service.",
            bed_type=BedType.KING,
            base_price=Decimal("12000"),
            max_occupancy=4,
            max_adults=2,
            max_children=2,
            area_sqft=700,
            amenities=["AC", "65-inch TV", "WiFi", "Jacuzzi", "Butler", "Kitchenette", "Sofa Bed"],
        )

        for rt in [rt_standard, rt_deluxe, rt_suite]:
            db.add(rt)
        db.flush()

        rooms = []
        for floor in range(1, 5):
            for i in range(1, 6):
                rooms.append(Room(
                    hotel_id=hotel.id,
                    room_type_id=rt_standard.id,
                    room_number=f"{floor}0{i}",
                    floor=floor,
                    status=RoomStatus.AVAILABLE,
                ))
            for i in range(6, 9):
                rooms.append(Room(
                    hotel_id=hotel.id,
                    room_type_id=rt_deluxe.id,
                    room_number=f"{floor}0{i}",
                    floor=floor,
                    status=RoomStatus.AVAILABLE,
                ))

        for floor in range(5, 7):
            for i in range(1, 4):
                rooms.append(Room(
                    hotel_id=hotel.id,
                    room_type_id=rt_suite.id,
                    room_number=f"{floor}0{i}",
                    floor=floor,
                    status=RoomStatus.AVAILABLE,
                ))

        for r in rooms:
            db.add(r)

        hotel.total_rooms = len(rooms)
        db.commit()
        print(f"  Hotel '{hotel.name}' seeded with {len(rooms)} rooms.")

        print("Seeding sample booking...")
        db.refresh(guest1)
        db.refresh(rt_standard)
        sample_room = db.query(Room).filter(
            Room.hotel_id == hotel.id,
            Room.room_type_id == rt_standard.id,
        ).first()

        check_in = date.today() + timedelta(days=3)
        check_out = check_in + timedelta(days=2)
        num_nights = 2
        rate = Decimal("2500")
        subtotal = rate * num_nights
        gst = calculate_gst(subtotal, rate)
        total = subtotal + gst

        booking_ref = generate_booking_ref()
        booking = Booking(
            booking_ref=booking_ref,
            guest_user_id=guest1.id,
            hotel_id=hotel.id,
            room_id=sample_room.id,
            room_type_id=rt_standard.id,
            check_in_date=check_in,
            check_out_date=check_out,
            adults=2,
            children=0,
            meal_plan=MealPlan.CP,
            status="confirmed",
            source=BookingSource.ONLINE_WEB,
            room_rate_per_night=rate,
            num_nights=num_nights,
            subtotal=subtotal,
            gst_amount=gst,
            discount_amount=Decimal("0"),
            total_amount=total,
            special_requests="High floor room preferred.",
        )
        db.add(booking)
        db.flush()

        folio = Folio(
            booking_id=booking.id,
            folio_number=generate_folio_number(),
            subtotal=subtotal,
            gst_amount=gst,
            total=total,
            paid=Decimal("0"),
            balance=total,
        )
        db.add(folio)
        db.flush()

        for n in range(num_nights):
            item = FolioItem(
                folio_id=folio.id,
                description=f"Room charge: Standard Room",
                category="room",
                quantity=1,
                unit_price=rate,
                amount=rate,
                date=check_in + timedelta(days=n),
            )
            db.add(item)

        db.commit()
        print(f"  Sample booking {booking_ref} created for Amit Kumar.")

    print("\nSeed completed successfully!")
    print("\n--- Login Credentials ---")
    print("Super Admin : phone=9000000001  password=Admin@1234")
    print("Hotel Admin : phone=9000000002  password=Admin@1234")
    print("Staff       : phone=9000000003  password=Staff@1234")
    print("Guest 1     : phone=9876543210  password=Guest@1234")
    print("Guest 2     : phone=9876543211  password=Guest@1234")

    db.close()


if __name__ == "__main__":
    seed()
