"""Pydantic models for the authentication system."""
from pydantic import BaseModel, Field
from typing import Optional


class User(BaseModel):
    id: str
    email: str
    role: str = "user"
    is_active: bool = True
    created_at: str = ""
    last_login: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, description="Minimum 8 characters")


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)
