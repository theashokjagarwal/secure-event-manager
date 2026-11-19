import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
# SECURITY: Never commit secrets to version control. .env is listed in .gitignore.
load_dotenv(BASE_DIR / ".env")


class Config:
    """
    Central application configuration loaded from environment variables.
    Provides safe defaults for development, but enforces strong security standards.
    """
    BASE_DIR = BASE_DIR

    # Environment & Debugging
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = os.getenv("FLASK_DEBUG", "False").lower() in ("true", "1", "yes")
    PORT = int(os.getenv("PORT", 5050))
    HOST = os.getenv("HOST", "127.0.0.1")

    # SECURITY: Secret key for signing JWT tokens.
    # In production, must be a cryptographically strong random string (32+ chars).
    JWT_SECRET = os.getenv("JWT_SECRET", "dev-insecure-key-change-in-production-1234567890")
    JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", 2))
    JWT_ALGORITHM = "HS256"

    # --------------------------------------------------------------------------
    # Database Configuration (Switch between SQLite and MySQL with ZERO code changes)
    # --------------------------------------------------------------------------
    DB_TYPE = os.getenv("DB_TYPE", "sqlite").lower()

    if DB_TYPE == "mysql":
        # MySQL Connection parameters
        DB_USER = os.getenv("DB_USER", "root")
        DB_PASSWORD = os.getenv("DB_PASSWORD", "")
        DB_HOST = os.getenv("DB_HOST", "localhost")
        DB_PORT = os.getenv("DB_PORT", "3306")
        DB_NAME = os.getenv("DB_NAME", "secure_events")
        # PyMySQL driver string
        SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    else:
        # SQLite Connection (Default for easy zero-setup local running)
        # On Vercel serverless environment, local directory is read-only; store in /tmp
        if os.getenv("VERCEL"):
            db_file = Path("/tmp/events.db")
        else:
            SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "events.db")
            db_file = BASE_DIR / SQLITE_DB_PATH
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_file}"

    # --------------------------------------------------------------------------
    # CORS (Cross-Origin Resource Sharing) Configuration
    # --------------------------------------------------------------------------
    # SECURITY: Only allow trusted origins to make API requests to this backend.
    CORS_ORIGIN = os.getenv("CORS_ORIGIN", "*")

    # --------------------------------------------------------------------------
    # File Upload Security Settings
    # --------------------------------------------------------------------------
    # SECURITY: Limit maximum file size (5MB default) to prevent Denial of Service (DoS) attacks
    MAX_CONTENT_LENGTH_MB = int(os.getenv("MAX_CONTENT_LENGTH_MB", 5))
    MAX_CONTENT_LENGTH = MAX_CONTENT_LENGTH_MB * 1024 * 1024

    if os.getenv("VERCEL"):
        UPLOAD_FOLDER = Path("/tmp/uploads")
    else:
        UPLOAD_FOLDER = BASE_DIR / os.getenv("UPLOAD_FOLDER", "app/uploads")

    # SECURITY: Strict whitelist of permitted file extensions
    ALLOWED_EXTENSIONS = {"pdf", "docx", "png", "jpg", "jpeg"}

    # SECURITY: Explicit blacklist of dangerous executable extensions
    BLOCKED_EXTENSIONS = {
        "exe", "bat", "sh", "cmd", "bin", "msi", "com", "pif", "scr",
        "vbs", "js", "jar", "py", "php", "pl", "cgi", "dll", "wsf"
    }

    # --------------------------------------------------------------------------
    # Rate Limiting Configuration
    # --------------------------------------------------------------------------
    # SECURITY: Prevent brute-force password guessing by throttling auth requests
    RATE_LIMIT_ATTEMPTS = int(os.getenv("RATE_LIMIT_ATTEMPTS", 5))
    RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", 60))
