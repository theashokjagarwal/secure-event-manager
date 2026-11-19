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
    Initialize database schema and seed default administrative/demo data
    along with verified Indian College & Tech Events if empty.
    """
    from app.models import User, Event
    from app.ai_service import INDIAN_EVENTS_KNOWLEDGE_BASE
    import bcrypt
    from datetime import datetime, timedelta

    # Create tables if they do not exist
    Base.metadata.create_all(bind=engine)

    # Seed default users if database is empty
    with get_db() as db:
        admin_exists = db.query(User).filter_by(email="admin@example.com").first()
        if not admin_exists:
            salt = bcrypt.gensalt()
            admin_pwd_hash = bcrypt.hashpw(b"Admin@12345", salt).decode("utf-8")
            demo_admin = User(
                name="Security Administrator",
                email="admin@example.com",
                password_hash=admin_pwd_hash,
                role="admin"
            )
            db.add(demo_admin)
            db.flush()
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
            db.flush()
            logger.info("Default demo user created: user@example.com")

        # Seed rich Indian Tech Events & College Fests if empty
        if db.query(Event).count() == 0:
            admin_user = db.query(User).filter_by(email="admin@example.com").first()
            if admin_user:
                now = datetime.utcnow()
                events_to_seed = []

                for item in INDIAN_EVENTS_KNOWLEDGE_BASE:
                    ev = Event(
                        title=item["title"],
                        description=item["description"],
                        category=item["category"],
                        event_type=item["event_type"],
                        city=item["city"],
                        college_name=item["college_name"],
                        event_date=now + timedelta(days=item["days_from_now"]),
                        location=item["location"],
                        application_link=item["application_link"],
                        is_ai_discovered=False,
                        created_by=admin_user.id
                    )
                    events_to_seed.append(ev)

                db.add_all(events_to_seed)
                logger.info(f"Seeded {len(events_to_seed)} Indian college and tech events across cities.")
