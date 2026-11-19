from __future__ import annotations
import re
import os
import uuid
import time
import logging
from typing import Optional, Union, Tuple
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
import bcrypt
import jwt
from werkzeug.utils import secure_filename
from app.config import Config

# Configure logger for security events
logger = logging.getLogger("secure_event_manager")

# ------------------------------------------------------------------------------
# 1. PASSWORD HASHING (BCrypt)
# ------------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """
    SECURITY: Hash passwords with BCrypt.
    BCrypt automatically generates a cryptographic salt and uses a slow,
    one-way hashing algorithm. This protects passwords against rainbow table
    attacks and makes brute-forcing computationally prohibitive.
    Never store plain-text passwords!
    """
    salt = bcrypt.gensalt(rounds=12)
    hashed_bytes = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed_bytes.decode("utf-8")


def check_password(plain_password: str, hashed_password: str) -> bool:
    """
    SECURITY: Compare plain password against stored BCrypt hash.
    BCrypt's checkpw function performs constant-time comparison to protect
    against timing-attack vulnerabilities.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception as e:
        logger.error(f"Password verification error: {str(e)}")
        return False


# ------------------------------------------------------------------------------
# 2. JWT (JSON Web Token) AUTHENTICATION
# ------------------------------------------------------------------------------
def create_access_token(user_id: int, role: str, email: str) -> str:
    """
    SECURITY: Create signed JWT with expiration time.
    The payload carries user claims (id, role, email) and an expiration ('exp').
    The token is cryptographically signed using HMAC-SHA256 with the server's secret.
    """
    now = datetime.utcnow()
    payload = {
        "sub": str(user_id),
        "user_id": user_id,
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=Config.JWT_EXPIRATION_HOURS)
    }
    token = jwt.encode(payload, Config.JWT_SECRET, algorithm=Config.JWT_ALGORITHM)
    return token


def verify_access_token(token: str) -> dict:
    """
    SECURITY: Validate JWT token signature and expiration.
    Returns the decoded payload if valid, or raises an exception.
    """
    try:
        payload = jwt.decode(
            token,
            Config.JWT_SECRET,
            algorithms=[Config.JWT_ALGORITHM],
            options={"require": ["exp", "sub", "role"]}
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Session token has expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid authentication token.")


# ------------------------------------------------------------------------------
# 3. ROLE-BASED ACCESS CONTROL (RBAC) DECORATORS
# ------------------------------------------------------------------------------
def login_required(f):
    """
    SECURITY: Enforce authentication on protected routes.
    Extracts JWT from the 'Authorization: Bearer <token>' header or HttpOnly cookie.
    Attaches current user info to request.current_user.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None

        # Check Authorization header (Format: Bearer <token>)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1].strip()

        # Fallback to HttpOnly cookie for browser sessions
        if not token:
            token = request.cookies.get("access_token")

        if not token:
            log_security_alert("MISSING_TOKEN", request.remote_addr, f"Unauthorized access to {request.path}")
            return jsonify({"success": False, "error": "Authentication required. Please log in."}), 401

        try:
            payload = verify_access_token(token)
            request.current_user = {
                "id": int(payload["user_id"]),
                "email": payload["email"],
                "role": payload["role"]
            }
        except ValueError as e:
            log_security_alert("INVALID_TOKEN", request.remote_addr, str(e))
            return jsonify({"success": False, "error": str(e)}), 401

        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    """
    SECURITY: Enforce Role-Based Access Control (RBAC).
    Verifies that the authenticated user possesses the 'admin' role.
    Regular 'user' role accounts are rejected with 403 Forbidden.
    """
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        user = getattr(request, "current_user", None)
        if not user or user.get("role") != "admin":
            log_security_alert(
                "UNAUTHORIZED_ADMIN_ACCESS_ATTEMPT",
                request.remote_addr,
                f"User ID {user.get('id') if user else 'Unknown'} attempted to access admin endpoint {request.path}"
            )
            return jsonify({"success": False, "error": "Access denied. Administrator privileges required."}), 403

        return f(*args, **kwargs)

    return decorated_function


# ------------------------------------------------------------------------------
# 4. INPUT VALIDATION & SANITIZATION
# ------------------------------------------------------------------------------
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def validate_email(email: str) -> tuple[bool, str]:
    """
    SECURITY: Validate email format using RFC-compliant pattern and length check.
    Prevents abnormal input lengths and mail-injection patterns.
    """
    if not email or not isinstance(email, str):
        return False, "Email address is required."
    email = email.strip()
    if len(email) > 120:
        return False, "Email address cannot exceed 120 characters."
    if not EMAIL_REGEX.match(email):
        return False, "Please provide a valid email address (e.g. user@example.com)."
    return True, email.lower()


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    SECURITY: Enforce strong password complexity.
    Requirements:
    - At least 8 characters long
    - At least one uppercase letter (A-Z)
    - At least one lowercase letter (a-z)
    - At least one number (0-9)
    - At least one special character (!@#$%^&*...)
    """
    if not password or not isinstance(password, str):
        return False, "Password is required."
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if len(password) > 128:
        return False, "Password cannot exceed 128 characters."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter (A-Z)."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter (a-z)."
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one number (0-9)."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>\-_]", password):
        return False, "Password must contain at least one special character (!@#$%^&* etc.)."
    return True, ""


def validate_text(text: str, field_name: str, min_len: int = 2, max_len: int = 500) -> tuple[bool, str]:
    """
    SECURITY: Generic input sanitization checking length bounds and stripping whitespace.
    Prevents empty payloads and buffer overflow / oversized payloads.
    """
    if text is None or not isinstance(text, str):
        return False, f"{field_name} is required."
    trimmed = text.strip()
    if len(trimmed) < min_len:
        return False, f"{field_name} must be at least {min_len} characters long."
    if len(trimmed) > max_len:
        return False, f"{field_name} cannot exceed {max_len} characters."
    return True, trimmed


def validate_event_date(date_str: str) -> tuple[bool, datetime | None, str]:
    """
    SECURITY: Validate event date format (ISO 8601 / YYYY-MM-DDTHH:MM)
    and verify that event date is in the future.
    """
    if not date_str or not isinstance(date_str, str):
        return False, None, "Event date is required."

    formats_to_try = [
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d"
    ]
    parsed_date = None
    for fmt in formats_to_try:
        try:
            parsed_date = datetime.strptime(date_str.strip(), fmt)
            break
        except ValueError:
            continue

    if not parsed_date:
        return False, None, "Invalid date format. Please use YYYY-MM-DD or YYYY-MM-DDTHH:MM."

    # Validate date is not in the past
    if parsed_date < datetime.utcnow() - timedelta(minutes=5):
        return False, None, "Event date cannot be in the past."

    return True, parsed_date, ""


# ------------------------------------------------------------------------------
# 5. FILE UPLOAD SECURITY
# ------------------------------------------------------------------------------
# Signatures (magic bytes) of safe file types for content verification
FILE_SIGNATURES = {
    "png": b"\x89PNG\r\n\x1a\n",
    "jpg": b"\xff\xd8\xff",
    "jpeg": b"\xff\xd8\xff",
    "pdf": b"%PDF",
    "docx": b"PK\x03\x04"  # DOCX is a zip-based OpenXML container
}


def validate_file_upload(file_storage) -> tuple[bool, str]:
    """
    SECURITY: Multi-layered file upload validation:
    1. Check if a filename is provided.
    2. Check extension against strict whitelist (PDF, DOCX, PNG, JPG).
    3. Check extension against explicit blacklist of executables (.exe, .sh, .bat).
    4. Inspect magic bytes (file signature) to prevent extension spoofing.
    """
    if not file_storage or not file_storage.filename:
        return False, "No file was selected for upload."

    original_filename = file_storage.filename
    if "." not in original_filename:
        return False, "Uploaded file must have a valid file extension."

    ext = original_filename.rsplit(".", 1)[1].lower()

    # Reject dangerous executable files explicitly
    if ext in Config.BLOCKED_EXTENSIONS:
        log_security_alert("EXECUTABLE_UPLOAD_BLOCKED", request.remote_addr, f"Blocked file attempt: {original_filename}")
        return False, "Executable and script files (.exe, .sh, .bat, etc.) are strictly prohibited."

    # Validate against allowed whitelist
    if ext not in Config.ALLOWED_EXTENSIONS:
        return False, f"File type not allowed. Permitted types: {', '.join(Config.ALLOWED_EXTENSIONS).upper()}."

    # Inspect file header (magic bytes) to verify actual file format
    header = file_storage.stream.read(16)
    file_storage.stream.seek(0)  # Reset stream position after reading

    expected_sig = FILE_SIGNATURES.get(ext)
    if expected_sig and not header.startswith(expected_sig):
        log_security_alert("SPOOFED_FILE_HEADER", request.remote_addr, f"File {original_filename} header mismatch for {ext}")
        return False, "Uploaded file content does not match its file extension."

    return True, ""


def save_secure_file(file_storage, target_folder) -> tuple[str, str]:
    """
    SECURITY: Secure file storage:
    1. Sanitize original filename using secure_filename to prevent directory traversal (e.g., ../../).
    2. Generate a random UUID prefix so files cannot overwrite existing files or execute path attacks.
    3. Save outside the web-accessible root in an isolated uploads folder.
    Returns: (stored_uuid_filename, sanitized_original_filename)
    """
    safe_original = secure_filename(file_storage.filename)
    ext = safe_original.rsplit(".", 1)[1].lower() if "." in safe_original else "bin"
    unique_stored_name = f"{uuid.uuid4().hex}.{ext}"

    os.makedirs(target_folder, exist_ok=True)
    full_path = os.path.join(target_folder, unique_stored_name)
    file_storage.save(full_path)

    return unique_stored_name, safe_original


# ------------------------------------------------------------------------------
# 6. RATE LIMITING (Brute-Force & Denial of Service Protection)
# ------------------------------------------------------------------------------
class SimpleRateLimiter:
    """
    SECURITY: In-memory sliding window rate limiter per client IP address.
    Protects login and registration APIs against automated credential stuffing
    and brute-force attacks.
    """
    def __init__(self):
        self.requests = {}  # Format: {ip: [timestamp1, timestamp2, ...]}

    def is_allowed(self, client_ip: str, max_attempts: int, window_seconds: int) -> bool:
        now = time.time()
        cutoff = now - window_seconds

        # Clean old timestamps for this IP
        if client_ip in self.requests:
            self.requests[client_ip] = [t for t in self.requests[client_ip] if t > cutoff]
        else:
            self.requests[client_ip] = []

        if len(self.requests[client_ip]) >= max_attempts:
            return False

        self.requests[client_ip].append(now)
        return True


rate_limiter = SimpleRateLimiter()


def rate_limit(max_attempts=Config.RATE_LIMIT_ATTEMPTS, window_seconds=Config.RATE_LIMIT_WINDOW_SECONDS):
    """
    Decorator to apply rate limiting to sensitive routes.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            client_ip = request.remote_addr or "unknown"
            if not rate_limiter.is_allowed(client_ip, max_attempts, window_seconds):
                log_security_alert("RATE_LIMIT_EXCEEDED", client_ip, f"Exceeded {max_attempts} requests on {request.path}")
                return jsonify({
                    "success": False,
                    "error": f"Too many requests. Please wait {window_seconds} seconds before trying again."
                }), 429
            return f(*args, **kwargs)
        return wrapped
    return decorator


# ------------------------------------------------------------------------------
# 7. LOGGING & AUDITING (No Passwords or Tokens Logged)
# ------------------------------------------------------------------------------
def log_failed_login(ip: str, email_attempt: str):
    """
    SECURITY: Log failed authentication attempts for intrusion detection.
    IMPORTANT: We log the attempted email and IP, but NEVER log passwords or raw secrets!
    """
    # Sanitize email string for logging to prevent log injection
    clean_email = email_attempt.replace("\n", "").replace("\r", "")[:80]
    logger.warning(f"[AUDIT:FAILED_LOGIN] IP={ip} AttemptedEmail={clean_email}")


def log_security_alert(alert_type: str, ip: str, details: str):
    """
    SECURITY: Log high-priority security exceptions and rejected inputs.
    """
    clean_details = str(details).replace("\n", " ").replace("\r", "")[:200]
    logger.warning(f"[SECURITY_ALERT:{alert_type}] IP={ip} Details={clean_details}")


def log_audit(action: str, user_id: int | str, ip: str):
    """
    SECURITY: Audit trail for important state changes (event created, registration, etc.).
    """
    logger.info(f"[AUDIT:{action}] UserID={user_id} IP={ip}")
