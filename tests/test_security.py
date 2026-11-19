import io
import os
import unittest
import json
from datetime import datetime, timedelta
import bcrypt
import jwt

# Set test environment
os.environ["FLASK_ENV"] = "testing"
os.environ["DB_TYPE"] = "sqlite"
os.environ["SQLITE_DB_PATH"] = "test_events.db"
os.environ["JWT_SECRET"] = "test-secret-key-for-automated-security-testing-32chars!"

from app import create_app
from app.config import Config
from app.database import Base, engine, get_db
from app.models import User, Event, Registration
from app.security import (
    hash_password,
    check_password,
    create_access_token,
    verify_access_token,
    validate_email,
    validate_password_strength,
    validate_event_date,
    rate_limiter
)


class SecurityTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def setUp(self):
        # Reset rate limiter memory before each test
        rate_limiter.requests.clear()

        # Re-create fresh database tables for test isolation
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        with get_db() as db:
            # Seed test admin
            salt = bcrypt.gensalt()
            admin_pwd = bcrypt.hashpw(b"Admin@12345", salt).decode("utf-8")
            self.admin_user = User(
                name="Security Admin",
                email="admin@example.com",
                password_hash=admin_pwd,
                role="admin"
            )
            # Seed test regular user
            user_pwd = bcrypt.hashpw(b"User@12345", salt).decode("utf-8")
            self.regular_user = User(
                name="Regular Attendee",
                email="user@example.com",
                password_hash=user_pwd,
                role="user"
            )
            db.add_all([self.admin_user, self.regular_user])
            db.flush()

            self.admin_id = self.admin_user.id
            self.user_id = self.regular_user.id

            # Create sample event
            self.sample_event = Event(
                title="Secure Coding Summit",
                description="Comprehensive hands-on defensive programming tutorial.",
                category="Security",
                event_date=datetime.utcnow() + timedelta(days=7),
                location="Room 101",
                created_by=self.admin_id
            )
            db.add(self.sample_event)
            db.flush()
            self.event_id = self.sample_event.id

        # Generate tokens
        self.admin_token = create_access_token(self.admin_id, "admin", "admin@example.com")
        self.user_token = create_access_token(self.user_id, "user", "user@example.com")

    def tearDown(self):
        Base.metadata.drop_all(bind=engine)

    # --------------------------------------------------------------------------
    # 1. SQL INJECTION PREVENTION TESTS
    # --------------------------------------------------------------------------
    def test_sql_injection_in_login_email(self):
        """
        SECURITY: Verify that classic SQL injection payloads like ' OR '1'='1
        cannot bypass login or alter query logic.
        """
        malicious_emails = [
            "' OR '1'='1",
            "admin@example.com' --",
            "' UNION SELECT * FROM users --",
            "admin@example.com'/*"
        ]
        for payload in malicious_emails:
            res = self.client.post("/api/auth/login", json={
                "email": payload,
                "password": "wrong_password"
            })
            self.assertEqual(res.status_code, 401)
            data = res.get_json()
            self.assertFalse(data["success"])
            self.assertEqual(data["error"], "Invalid email or password.")

    def test_sql_injection_in_search_events(self):
        """
        SECURITY: Verify that SQL injection attempts in event search queries are safely escaped.
        """
        res = self.client.get("/api/events?q=' UNION SELECT id, name, password_hash FROM users --")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        # Should return 0 events, not leak database schemas or user passwords
        self.assertEqual(data["count"], 0)

    # --------------------------------------------------------------------------
    # 2. PASSWORD HASHING (BCrypt) TESTS
    # --------------------------------------------------------------------------
    def test_bcrypt_password_hashing(self):
        """
        SECURITY: Passwords must be hashed with BCrypt.
        Plain text must never equal stored hash.
        Hashes for the same password must differ due to unique salts.
        """
        raw_password = "SecurePassword@123"
        hash1 = hash_password(raw_password)
        hash2 = hash_password(raw_password)

        self.assertNotEqual(raw_password, hash1)
        self.assertTrue(hash1.startswith("$2b$") or hash1.startswith("$2a$"))
        # Due to random salt, two hashes of the same password are not equal
        self.assertNotEqual(hash1, hash2)
        # But both verify correctly
        self.assertTrue(check_password(raw_password, hash1))
        self.assertTrue(check_password(raw_password, hash2))
        self.assertFalse(check_password("WrongPassword@123", hash1))

    # --------------------------------------------------------------------------
    # 3. JWT AUTHENTICATION & EXPIRATION TESTS
    # --------------------------------------------------------------------------
    def test_jwt_tampering_rejected(self):
        """
        SECURITY: Tokens signed with an invalid key or modified claims must be rejected.
        """
        tampered_token = self.user_token[:-5] + "abcde"
        with self.assertRaises(ValueError):
            verify_access_token(tampered_token)

    def test_jwt_expiration(self):
        """
        SECURITY: Expired JWTs must be strictly rejected.
        """
        expired_payload = {
            "sub": str(self.user_id),
            "user_id": self.user_id,
            "email": "user@example.com",
            "role": "user",
            "iat": datetime.utcnow() - timedelta(hours=5),
            "exp": datetime.utcnow() - timedelta(hours=3)  # Expired 3 hours ago
        }
        expired_token = jwt.encode(expired_payload, Config.JWT_SECRET, algorithm="HS256")
        with self.assertRaises(ValueError) as ctx:
            verify_access_token(expired_token)
        self.assertIn("expired", str(ctx.exception).lower())

    # --------------------------------------------------------------------------
    # 4. ROLE-BASED ACCESS CONTROL (RBAC) TESTS
    # --------------------------------------------------------------------------
    def test_regular_user_cannot_access_admin_api(self):
        """
        SECURITY: Regular 'user' role accounts must receive 403 Forbidden
        when accessing admin-only endpoints.
        """
        res = self.client.post("/api/admin/events", json={
            "title": "Hacker Convention",
            "description": "Unauthorized event creation attempt.",
            "category": "Security",
            "event_date": (datetime.utcnow() + timedelta(days=2)).isoformat(),
            "location": "Unauthorized Location"
        }, headers={"Authorization": f"Bearer {self.user_token}"})

        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("denied", data["error"].lower())

    def test_admin_can_access_admin_api(self):
        """
        SECURITY: Admin users with valid token should successfully access admin endpoints.
        """
        future_date = (datetime.utcnow() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M")
        res = self.client.post("/api/admin/events", json={
            "title": "Authorized Security Summit",
            "description": "Legitimate admin event creation with strong parameters.",
            "category": "Security",
            "event_date": future_date,
            "location": "Main Conference Hall"
        }, headers={"Authorization": f"Bearer {self.admin_token}"})

        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["event"]["title"], "Authorized Security Summit")

    # --------------------------------------------------------------------------
    # 5. RATE LIMITING TESTS
    # --------------------------------------------------------------------------
    def test_auth_rate_limiting(self):
        """
        SECURITY: Rapid repeated login attempts must be throttled with HTTP 429 Too Many Requests.
        """
        # Execute 5 allowed attempts
        for _ in range(5):
            res = self.client.post("/api/auth/login", json={
                "email": "user@example.com",
                "password": "WrongPassword123!"
            })
            self.assertEqual(res.status_code, 401)

        # 6th attempt should be blocked by rate limiter
        blocked_res = self.client.post("/api/auth/login", json={
            "email": "user@example.com",
            "password": "WrongPassword123!"
        })
        self.assertEqual(blocked_res.status_code, 429)
        data = blocked_res.get_json()
        self.assertIn("too many requests", data["error"].lower())

    # --------------------------------------------------------------------------
    # 6. FILE UPLOAD SECURITY TESTS
    # --------------------------------------------------------------------------
    def test_blocked_executable_upload(self):
        """
        SECURITY: Dangerous file extensions like .exe, .sh, .bat must be strictly rejected.
        """
        future_date = (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")

        executable_payload = (io.BytesIO(b"#!/bin/bash\nrm -rf /"), "malicious.sh")
        res = self.client.post(
            "/api/admin/events",
            data={
                "title": "Malicious Script Event",
                "description": "Attempting to upload executable script.",
                "category": "Security",
                "event_date": future_date,
                "location": "Server",
                "attachment": executable_payload
            },
            content_type="multipart/form-data",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("prohibited", data["error"].lower())

    def test_allowed_pdf_upload(self):
        """
        SECURITY: Safe document formats (.pdf) with correct header must be accepted.
        """
        future_date = (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")

        # Valid PDF header
        pdf_payload = (io.BytesIO(b"%PDF-1.4 sample secure document content"), "event-guide.pdf")
        res = self.client.post(
            "/api/admin/events",
            data={
                "title": "Cyber Guidelines Event",
                "description": "Event with safe PDF guide attachment.",
                "category": "Security",
                "event_date": future_date,
                "location": "Auditorium",
                "attachment": pdf_payload
            },
            content_type="multipart/form-data",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data["event"]["has_attachment"])

    # --------------------------------------------------------------------------
    # 7. INPUT VALIDATION TESTS
    # --------------------------------------------------------------------------
    def test_weak_password_rejected(self):
        """
        SECURITY: Password complexity rules (length, uppercase, lowercase, digit, special char).
        """
        weak_passwords = [
            "short",              # Too short
            "alllowercase123!",   # No uppercase
            "ALLUPPERCASE123!",   # No lowercase
            "NoNumbersHere!@",    # No numbers
            "NoSpecialChar1234"   # No special char
        ]
        for pwd in weak_passwords:
            valid, err = validate_password_strength(pwd)
            self.assertFalse(valid, f"Weak password '{pwd}' should have failed validation.")

    def test_past_event_date_rejected(self):
        """
        SECURITY & BUSINESS LOGIC: Event dates in the past must be rejected.
        """
        past_date = (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
        valid, dt, err = validate_event_date(past_date)
        self.assertFalse(valid)
        self.assertIn("past", err.lower())

    # --------------------------------------------------------------------------
    # 8. SECURITY HEADERS TESTS
    # --------------------------------------------------------------------------
    def test_security_headers_present(self):
        """
        SECURITY: Key defensive HTTP headers must be present on responses.
        """
        res = self.client.get("/")
        self.assertIn("Content-Security-Policy", res.headers)
        self.assertIn("X-Content-Type-Options", res.headers)
        self.assertEqual(res.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(res.headers["X-Frame-Options"], "DENY")


if __name__ == "__main__":
    unittest.main()
