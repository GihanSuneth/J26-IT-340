import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from auth_database import get_db
from auth_models import User, Customer
from auth_schemas import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
bearer = HTTPBearer(auto_error=False)
password_hasher = PasswordHash.recommended()

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
TOKEN_MINUTES = 60


class DevPasswordResetRequest(BaseModel):
    """Temporary request schema for local development only."""

    email: EmailStr
    new_password: str = Field(min_length=8, max_length=128)


def create_token(user: User) -> str:
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET is not configured.")

    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user.id),
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=TOKEN_MINUTES),
    }

    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Please log in.",
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired login. Please log in again.",
        )

    user = db.get(User, user_id)

    if not user or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Account is unavailable.",
        )

    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Administrator access required.",
        )
    return user



@router.post("/register", response_model=TokenResponse, status_code=201)
def register(
    body: RegisterRequest,
    db: Session = Depends(get_db),
):
    email = str(body.email).lower().strip()

    existing = db.scalar(
        select(User).where(func.lower(User.email) == email)
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists.",
        )

    # Generate the next user code using the highest existing ID.
    highest_user_id = db.scalar(
        select(func.max(User.id))
    ) or 0

    # Find the next unused customer ID.
    customer_number = 1

    while db.scalar(
        select(User.id).where(
            User.customer_id == f"C{customer_number:04d}"
        )
    ) is not None:
        customer_number += 1

    customer_id = f"C{customer_number:04d}"

    user = User(
        user_code=f"U{highest_user_id + 1:04d}",
        customer_id=customer_id,
        full_name=body.full_name.strip(),
        email=email,
        password_hash=password_hasher.hash(body.password),
        role="customer",
        is_active=True,
    )

    try:
        # Save both records in one transaction.
        db.add(user)
        db.flush()  # Generates user.id without committing yet.

        customer = Customer(
            user_id=user.id,
            customer_id=customer_id,
        )

        db.add(customer)
        db.commit()
        db.refresh(user)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Registration failed. Please try again.",
        )

    return TokenResponse(
        access_token=create_token(user),
        user=user,
    )



@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    db: Session = Depends(get_db),
):
    email = str(body.email).lower().strip()

    user = db.scalar(
        select(User).where(func.lower(User.email) == email)
    )

    if (
        not user
        or not user.is_active
        or not password_hasher.verify(
            body.password,
            user.password_hash,
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password.",
        )

    return TokenResponse(
        access_token=create_token(user),
        user=user,
    )


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(current_user)):
    return user


@router.get("/admin/users", response_model=list[UserResponse])
def list_users(
    _admin: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    return list(
        db.scalars(select(User).order_by(User.id)).all()
    )


# TEMPORARY: Local development only.
# Do not expose this unauthenticated endpoint in production.
@router.post("/dev/reset-password")
def dev_reset_password(
    body: DevPasswordResetRequest,
    db: Session = Depends(get_db),
):
    if os.getenv("APP_ENV", "development").lower() != "development":
        raise HTTPException(
            status_code=404,
            detail="Endpoint not found.",
        )

    email = str(body.email).lower().strip()

    user = db.scalar(
        select(User).where(func.lower(User.email) == email)
    )

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found.",
        )

    user.password_hash = password_hasher.hash(body.new_password)
    db.commit()

    return {
        "message": "Password updated successfully.",
        "email": user.email,
    }