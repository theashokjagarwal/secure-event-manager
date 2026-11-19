import os
import unittest
from datetime import datetime, timedelta

os.environ["FLASK_ENV"] = "testing"
os.environ["DB_TYPE"] = "sqlite"
os.environ["SQLITE_DB_PATH"] = "test_ai_events.db"
os.environ["JWT_SECRET"] = "test-secret-key-for-ai-testing-32chars-long!"

from app import create_app
from app.database import Base, engine, get_db, init_db
from app.models import Event
from app.security import create_access_token, validate_url, rate_limiter
from app.ai_service import AIEventResearcher


class AIFeaturesTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def setUp(self):
        rate_limiter.requests.clear()
        Base.metadata.drop_all(bind=engine)
        init_db()

        with get_db() as db:
            from app.models import User
            admin = db.query(User).filter_by(email="admin@example.com").first()
            user = db.query(User).filter_by(email="user@example.com").first()
            self.admin_id = admin.id
            self.user_id = user.id

        self.admin_token = create_access_token(self.admin_id, "admin", "admin@example.com")
        self.user_token = create_access_token(self.user_id, "user", "user@example.com")

    def tearDown(self):
        Base.metadata.drop_all(bind=engine)

    def test_indian_events_seeded(self):
        """Verify Indian college fests & tech events are seeded with application links."""
        res = self.client.get("/api/events")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertGreaterEqual(data["count"], 10)

        # Check that top Indian events exist
        titles = [e["title"] for e in data["events"]]
        self.assertTrue(any("ETHIndia" in t for t in titles))
        self.assertTrue(any("Techfest" in t or "IIT" in t for t in titles))

        # Check that application links are valid URLs
        for e in data["events"]:
            if e["application_link"]:
                self.assertTrue(e["application_link"].startswith("http"))

    def test_city_filter(self):
        """Verify events can be filtered by Indian cities."""
        res = self.client.get("/api/events?city=Bengaluru")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        for e in data["events"]:
            self.assertIn("bengaluru", e["city"].lower())

    def test_application_url_security_validation(self):
        """SECURITY: Reject javascript: URI and pseudo-protocol XSS payloads."""
        valid, url, err = validate_url("javascript:alert(document.cookie)")
        self.assertFalse(valid)
        self.assertIn("must start with", err.lower())

        valid_https, clean_url, _ = validate_url("https://sih.gov.in")
        self.assertTrue(valid_https)
        self.assertEqual(clean_url, "https://sih.gov.in")

    def test_ai_roadmap_generation(self):
        """Verify AI roadmap generation for an event."""
        with get_db() as db:
            event = db.query(Event).first()
            event_id = event.id

        res = self.client.get(f"/api/events/{event_id}/ai-guide")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        guide = data["ai_guide"]
        self.assertIn("recommended_skills", guide)
        self.assertIn("team_strategy", guide)
        self.assertIn("ai_tip", guide)

    def test_ai_auto_discovery_rbac(self):
        """SECURITY: Regular users cannot trigger AI mass auto-discovery; Admin can."""
        # Regular user attempt - should be 403 Forbidden
        user_res = self.client.post("/api/admin/ai/auto-discover", json={
            "city": "Bengaluru",
            "count": 3
        }, headers={"Authorization": f"Bearer {self.user_token}"})
        self.assertEqual(user_res.status_code, 403)

        # Admin attempt - should be 200 OK
        admin_res = self.client.post("/api/admin/ai/auto-discover", json={
            "city": "Hyderabad",
            "count": 3
        }, headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(admin_res.status_code, 200)
        data = admin_res.get_json()
        self.assertTrue(data["success"])


if __name__ == "__main__":
    unittest.main()
