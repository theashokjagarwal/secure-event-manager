import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import Config

logger = logging.getLogger("secure_event_manager")

# Configure database engine based on DB_TYPE
# SECURITY: Using SQLAlchemy ORM ensures all queries use parameterized statements,
# completely eliminating SQL injection vulnerabilities.
if Config.DB_TYPE == "sqlite":
    # SQLite requires check_same_thread=False for multi-threaded Flask apps
    engine = create_engine(
        Config.SQLALCHEMY_DATABASE_URI,
        connect_args={"check_same_thread": False},
        echo=False
    )

    # SQLite does not enforce foreign keys by default; enable foreign keys pragma
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

else:
    # MySQL / Production configuration with connection pooling and auto-reconnect
    engine = create_engine(
        Config.SQLALCHEMY_DATABASE_URI,
        pool_pre_ping=True,       # Auto-detect disconnected connections
        pool_recycle=3600,        # Recycle connections after 1 hour
        pool_size=10,             # Keep up to 10 connections alive
        max_overflow=20,
        echo=False
    )

# Session factory for handling transactional scopes
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative Base for models
Base = declarative_base()


@contextmanager
def get_db():
    """
    Provide a transactional database session scope.
    Ensures sessions are closed properly to prevent connection leaks.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """
    Initialize database schema and seed default administrative/demo data if empty.
    Runs locally with minimal setup!
    """
    # Import models here so Base knows about all model classes before create_all
    from app.models import User, Event
    import bcrypt
    from datetime import datetime, timedelta

    # Create tables if they do not exist
    Base.metadata.create_all(bind=engine)

    # Seed default users if database is empty
    with get_db() as db:
        admin_exists = db.query(User).filter_by(email="admin@example.com").first()
        if not admin_exists:
            # SECURITY: Hash default password with bcrypt before storing
            salt = bcrypt.gensalt()
            admin_pwd_hash = bcrypt.hashpw(b"Admin@12345", salt).decode("utf-8")
            demo_admin = User(
                name="Security Administrator",
                email="admin@example.com",
                password_hash=admin_pwd_hash,
                role="admin"
            )
            db.add(demo_admin)
            logger.info("Default admin user created: admin@example.com")

        user_exists = db.query(User).filter_by(email="user@example.com").first()
        if not user_exists:
            salt = bcrypt.gensalt()
            user_pwd_hash = bcrypt.hashpw(b"User@12345", salt).decode("utf-8")
            demo_user = User(
                name="Demo Attendee",
                email="user@example.com",
                password_hash=user_pwd_hash,
                role="user"
            )
            db.add(demo_user)
            logger.info("Default demo user created: user@example.com")

        # Seed sample events if none exist
        if db.query(Event).count() == 0:
            admin_user = db.query(User).filter_by(email="admin@example.com").first()
            if admin_user:
                sample_event1 = Event(
                    title="Cybersecurity Fundamentals Workshop 2026",
                    description="Hands-on workshop covering OWASP Top 10 vulnerabilities, secure coding practices, and defensive architecture for modern web applications.",
                    category="Security",
                    event_date=datetime.utcnow() + timedelta(days=14),
                    location="Online - Zoom Webinar",
                    created_by=admin_user.id
                )
                sample_event2 = Event(
                    title="Full-Stack Python & Database Architecture",
                    description="Learn how to architect clean database abstraction layers supporting both SQLite and MySQL, preventing SQL injection and managing migrations.",
                    category="Development",
                    event_date=datetime.utcnow() + timedelta(days=28),
                    location="Tech Innovation Center, Hall A",
                    created_by=admin_user.id
                )
                db.add_all([sample_event1, sample_event2])
                logger.info("Sample events seeded successfully.")
