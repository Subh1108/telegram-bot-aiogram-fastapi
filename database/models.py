"""
Database models shared by the bot and the dashboard API.
"""
import datetime
import secrets
import enum

from sqlalchemy import (
    BigInteger, String, Boolean, DateTime, ForeignKey, Text, Integer, Enum
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def utcnow():
    return datetime.datetime.utcnow()


def gen_referral_code():
    return secrets.token_urlsafe(6)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)

    referral_code: Mapped[str] = mapped_column(String(16), unique=True, default=gen_referral_code)
    referred_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    joined_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)
    last_active_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)

    referred_by = relationship("User", remote_side=[id])

    @property
    def display_name(self) -> str:
        if self.username:
            return f"@{self.username}"
        return " ".join(filter(None, [self.first_name, self.last_name])) or str(self.telegram_id)


class TicketStatus(str, enum.Enum):
    OPEN = "open"
    ANSWERED = "answered"
    CLOSED = "closed"


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    subject: Mapped[str] = mapped_column(String(255), default="Support request")
    status: Mapped[TicketStatus] = mapped_column(Enum(TicketStatus), default=TicketStatus.OPEN)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)

    user = relationship("User")
    messages = relationship("TicketMessage", back_populates="ticket", order_by="TicketMessage.created_at")


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("support_tickets.id"))
    from_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)

    ticket = relationship("SupportTicket", back_populates="messages")


class BroadcastLog(Base):
    __tablename__ = "broadcast_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    body: Mapped[str] = mapped_column(Text)
    segment: Mapped[str] = mapped_column(String(32), default="all")  # all / active_7d / new_30d
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    scheduled_for: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class ActivityEvent(Base):
    """Powers the live activity feed on the dashboard."""
    __tablename__ = "activity_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(32))  # new_user, broadcast, ticket, ban, etc.
    description: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)


class FAQItem(Base):
    __tablename__ = "faq_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    question: Mapped[str] = mapped_column(String(255))
    answer: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
