
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from auth_database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )

    user_code: Mapped[str] = mapped_column(
        String(20), unique=True, index=True
    )

    customer_id: Mapped[str | None] = mapped_column(
        String(30), unique=True, nullable=True, index=True
    )

    full_name: Mapped[str] = mapped_column(String(120))

    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True
    )

    password_hash: Mapped[str] = mapped_column(String(255))

    role: Mapped[str] = mapped_column(
        String(20), default="customer", nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
