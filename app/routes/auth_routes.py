from flask import Blueprint, request, jsonify, make_response
from app.database import get_db
from app.models import User
from app.security import (
    hash_password,
    check_password,
    create_access_token,
    login_required,
    validate_email,
    validate_password_strength,
    validate_text,
    rate_limit,
    log_failed_login,
    log_audit,
    log_security_alert
)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
@rate_limit(max_attempts=5, window_seconds=60)
def register():
    """
    User Registration Endpoint
    SECURITY FEATURES:
    - Rate-limited to prevent mass automated account creation.
    - Dual input validation on server (email format, password complexity, string bounds).
    - Password is encrypted using salted BCrypt hash before database persistence.
    - Role is strictly defaulted to 'user' so clients cannot self-promote to admin.
    """
    data = request.get_json(silent=True) or {}

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    # 1. Validate Full Name
    valid_name, name_val = validate_text(name, "Full Name", min_len=2, max_len=80)
    if not valid_name:
        return jsonify({"success": False, "error": name_val}), 400

    # 2. Validate Email Format
    valid_email, email_val = validate_email(email)
    if not valid_email:
        return jsonify({"success": False, "error": email_val}), 400

    # 3. Validate Password Strength
    valid_pwd, pwd_error = validate_password_strength(password)
    if not valid_pwd:
        return jsonify({"success": False, "error": pwd_error}), 400

    with get_db() as db:
        # Parameterized query - prevents SQL Injection
        existing_user = db.query(User).filter(User.email == email_val).first()
        if existing_user:
            # SECURITY: Generic error message prevents disclosing whether email is registered
            log_security_alert("REGISTRATION_EMAIL_EXISTS", request.remote_addr, f"Attempted duplicate email: {email_val}")
            return jsonify({"success": False, "error": "An account with this email already exists or is unavailable."}), 409

        # Hash password using BCrypt
        pwd_hash = hash_password(password)

        new_user = User(
            name=name_val,
            email=email_val,
            password_hash=pwd_hash,
            role="user"  # Default role is always standard user
        )
        db.add(new_user)
        db.flush()

        log_audit("USER_REGISTERED", new_user.id, request.remote_addr)

        return jsonify({
            "success": True,
            "message": "Account registered successfully! You can now log in.",
            "user": new_user.to_dict()
        }), 201


@auth_bp.route("/login", methods=["POST"])
@rate_limit(max_attempts=5, window_seconds=60)
def login():
    """
    User Authentication Endpoint
    SECURITY FEATURES:
    - Rate limited to mitigate brute-force password guessing.
    - Parameterized query to prevent SQL injection.
    - Constant-time bcrypt password verification.
    - Generic error message "Invalid email or password" to prevent User Enumeration.
    - Returns JWT token and sets an HttpOnly, SameSite cookie for defense-in-depth.
    """
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"success": False, "error": "Please provide both email and password."}), 400

    with get_db() as db:
        # Parameterized query via SQLAlchemy
        user = db.query(User).filter(User.email == email).first()

        # SECURITY: Always execute check_password or use identical response
        # to prevent timing differences between existing and non-existing accounts
        if not user or not check_password(password, user.password_hash):
            log_failed_login(request.remote_addr, email)
            # SECURITY: Never say "User not found" or "Wrong password" — use generic message!
            return jsonify({"success": False, "error": "Invalid email or password."}), 401

        # Generate JWT token
        token = create_access_token(user_id=user.id, role=user.role, email=user.email)
        log_audit("USER_LOGIN_SUCCESS", user.id, request.remote_addr)

        response = make_response(jsonify({
            "success": True,
            "message": "Login successful.",
            "token": token,
            "user": user.to_dict()
        }))

        # SECURITY: Set HttpOnly, SameSite cookie for secure session handling
        response.set_cookie(
            "access_token",
            token,
            httponly=True,        # Cannot be accessed by JavaScript (XSS mitigation)
            samesite="Lax",       # Mitigates Cross-Site Request Forgery (CSRF)
            secure=False,         # Set to True in production HTTPS
            max_age=7200          # 2 hours lifetime matching JWT expiration
        )

        return response


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """
    User Logout Endpoint
    Clears the HttpOnly authentication cookie.
    Frontend will also clear its stored token from memory / session storage.
    """
    response = make_response(jsonify({
        "success": True,
        "message": "Logged out successfully."
    }))
    response.delete_cookie("access_token")
    return response


@auth_bp.route("/me", methods=["GET"])
@login_required
def get_current_user():
    """
    Retrieve current authenticated user profile.
    Protected by @login_required decorator.
    """
    user_info = request.current_user
    with get_db() as db:
        user = db.query(User).filter(User.id == user_info["id"]).first()
        if not user:
            return jsonify({"success": False, "error": "User record not found."}), 404
        return jsonify({
            "success": True,
            "user": user.to_dict()
        })
