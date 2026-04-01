from pydantic import BaseModel, field_validator
from typing import Optional
import re


class SendOTPRequest(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        phone = re.sub(r"\D", "", v)
        if phone.startswith("91") and len(phone) == 12:
            phone = phone[2:]
        if not re.match(r"^[6-9]\d{9}$", phone):
            raise ValueError("Invalid Indian phone number. Must be 10 digits starting with 6-9.")
        return phone


class VerifyOTPRequest(BaseModel):
    phone: str
    otp: str
    full_name: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        phone = re.sub(r"\D", "", v)
        if phone.startswith("91") and len(phone) == 12:
            phone = phone[2:]
        if not re.match(r"^[6-9]\d{9}$", phone):
            raise ValueError("Invalid Indian phone number.")
        return phone

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, v: str) -> str:
        if not re.match(r"^\d{6}$", v):
            raise ValueError("OTP must be exactly 6 digits.")
        return v


class RegisterRequest(BaseModel):
    full_name: str
    email: Optional[str] = None
    phone: str
    password: str
    preferred_language: str = "en"

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        phone = re.sub(r"\D", "", v)
        if phone.startswith("91") and len(phone) == 12:
            phone = phone[2:]
        if not re.match(r"^[6-9]\d{9}$", phone):
            raise ValueError("Invalid Indian phone number.")
        return phone

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v

    @field_validator("preferred_language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in ("en", "hi"):
            raise ValueError("Language must be 'en' or 'hi'.")
        return v


class LoginRequest(BaseModel):
    phone: str
    password: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        phone = re.sub(r"\D", "", v)
        if phone.startswith("91") and len(phone) == 12:
            phone = phone[2:]
        if not re.match(r"^[6-9]\d{9}$", phone):
            raise ValueError("Invalid Indian phone number.")
        return phone


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

    class Config:
        from_attributes = True


class OTPResponse(BaseModel):
    message: str
    phone: str
    expires_in_seconds: int = 300

    class Config:
        from_attributes = True
