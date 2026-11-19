from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    """
    User entity supporting Role-Based Access Control (RBAC).
    SECURITY NOTE: Passwords are NEVER stored in plain text.
    Only the strong bcrypt hash is stored in password_hash.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user", nullable=False)  # "user" or "admin"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    registrations = relationship("Registration", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        """
        SECURITY: Explicitly omit sensitive fields like password_hash from serializations!
        """
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class Event(Base):
    """
    Event entity representing community or company events.
    Created by an admin user. Can include secure attachments (flyers, schedules).
    """
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(150), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)
    event_date = Column(DateTime, nullable=False)
    location = Column(String(200), nullable=False)
    
    # Secure file attachment fields
    attachment_filename = Column(String(255), nullable=True)      # Stored unique UUID filename on disk
    attachment_original_name = Column(String(255), nullable=True)  # Safe original name for display
    
    created_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    creator = relationship("User")
    registrations = relationship("Registration", back_populates="event", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "location": self.location,
            "has_attachment": bool(self.attachment_filename),
            "attachment_name": self.attachment_original_name,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "registration_count": len(self.registrations) if self.registrations else 0
        }


class Registration(Base):
    """
    Event attendee registration linking users and events.
    Uses UniqueConstraint to prevent double-registration.
    """
    __tablename__ = "registrations"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), default="confirmed", nullable=False)
    registered_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Prevent a user from registering twice for the same event
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_user"),
    )

    # Relationships
    event = relationship("Event", back_populates="registrations")
    user = relationship("User", back_populates="registrations")

    def to_dict(self):
        return {
            "id": self.id,
            "event_id": self.event_id,
            "user_id": self.user_id,
            "status": self.status,
            "registered_at": self.registered_at.isoformat() if self.registered_at else None,
            "event": self.event.to_dict() if self.event else None,
            "user_name": self.user.name if self.user else None,
            "user_email": self.user.email if self.user else None
        }
