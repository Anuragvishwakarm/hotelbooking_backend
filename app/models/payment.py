from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    Text, Enum, ForeignKey, DECIMAL
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class PaymentMethod(str, enum.Enum):
    CASH = "cash"
    CARD = "card"
    UPI = "upi"
    NET_BANKING = "net_banking"
    WALLET = "wallet"
    RAZORPAY = "razorpay"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    INITIATED = "initiated"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class RefundStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False, index=True)
    amount = Column(DECIMAL(10, 2), nullable=False)
    method = Column(Enum(PaymentMethod), nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)

    razorpay_order_id = Column(String(100), unique=True, nullable=True, index=True)
    razorpay_payment_id = Column(String(100), unique=True, nullable=True)
    razorpay_signature = Column(String(255), nullable=True)

    upi_transaction_id = Column(String(100), nullable=True)
    card_last_four = Column(String(4), nullable=True)
    bank_reference = Column(String(100), nullable=True)

    paid_at = Column(DateTime(timezone=True), nullable=True)
    collected_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    booking = relationship("Booking", back_populates="payments")
    refunds = relationship("Refund", back_populates="payment")


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False, index=True)
    amount = Column(DECIMAL(10, 2), nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(Enum(RefundStatus), default=RefundStatus.PENDING)
    razorpay_refund_id = Column(String(100), nullable=True, unique=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    processed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    payment = relationship("Payment", back_populates="refunds")
