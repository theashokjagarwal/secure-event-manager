import io
import os
import unittest
from datetime import datetime, timedelta

os.environ["FLASK_ENV"] = "testing"
os.environ["DB_TYPE"] = "sqlite"
os.environ["SQLITE_DB_PATH"] = "test_e2e_events.db"
os.environ["JWT_SECRET"] = "test-secret-key-for-e2e-workflow-testing-32chars!"

from app import create_app
from app.database import Base, engine, get_db, init_db
from app.models import User, Event, Registration
from app.security import rate_limiter


class E2EWorkflowTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def setUp(self):
        rate_limiter.requests.clear()
        Base.metadata.drop_all(bind=engine)
        init_db()

    def tearDown(self):
        Base.metadata.drop_all(bind=engine)

    def test_full_application_lifecycle(self):
        # 1. Register a new user
        reg_res = self.client.post("/api/auth/register", json={
            "name": "Alice Security",
            "email": "alice@company.com",
            "password": "StrongPassword@2026"
        })
        self.assertEqual(reg_res.status_code, 201)
        self.assertTrue(reg_res.get_json()["success"])

        # 2. Login as the newly created user
        login_res = self.client.post("/api/auth/login", json={
            "email": "alice@company.com",
            "password": "StrongPassword@2026"
        })
        self.assertEqual(login_res.status_code, 200)
        alice_data = login_res.get_json()
        self.assertTrue(alice_data["success"])
        alice_token = alice_data["token"]
        alice_id = alice_data["user"]["id"]

        # 3. Login as Admin
        admin_login_res = self.client.post("/api/auth/login", json={
            "email": "admin@example.com",
            "password": "Admin@12345"
        })
        self.assertEqual(admin_login_res.status_code, 200)
        admin_token = admin_login_res.get_json()["token"]

        # 4. Admin creates an event with an image/flyer attachment
        future_date = (datetime.utcnow() + timedelta(days=10)).strftime("%Y-%m-%dT%H:%M")
        png_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
        create_res = self.client.post(
            "/api/admin/events",
            data={
                "title": "Annual Security Conclave",
                "description": "Exclusive corporate gathering discussing cloud resilience and secure SDLC.",
                "category": "Security",
                "event_date": future_date,
                "location": "Convention Center Hall B",
                "attachment": (io.BytesIO(png_data), "event_banner.png")
            },
            content_type="multipart/form-data",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        self.assertEqual(create_res.status_code, 201)
        event_info = create_res.get_json()["event"]
        event_id = event_info["id"]
        self.assertTrue(event_info["has_attachment"])

        # 5. Alice views public event list
        events_res = self.client.get("/api/events")
        self.assertEqual(events_res.status_code, 200)
        events_list = events_res.get_json()["events"]
        self.assertTrue(any(e["id"] == event_id for e in events_list))

        # 6. Alice registers for the event
        rsvp_res = self.client.post(
            f"/api/events/{event_id}/register",
            headers={"Authorization": f"Bearer {alice_token}"}
        )
        self.assertEqual(rsvp_res.status_code, 201)

        # 7. Alice checks her personal registrations
        my_regs_res = self.client.get(
            "/api/my-registrations",
            headers={"Authorization": f"Bearer {alice_token}"}
        )
        self.assertEqual(my_regs_res.status_code, 200)
        regs = my_regs_res.get_json()["registrations"]
        self.assertEqual(len(regs), 1)
        self.assertEqual(regs[0]["event_id"], event_id)

        # 8. Admin checks attendees for the event
        attendees_res = self.client.get(
            f"/api/admin/events/{event_id}/attendees",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        self.assertEqual(attendees_res.status_code, 200)
        attendees_data = attendees_res.get_json()
        self.assertEqual(attendees_data["count"], 1)
        self.assertEqual(attendees_data["attendees"][0]["user_email"], "alice@company.com")

        # 9. Admin checks platform stats
        stats_res = self.client.get(
            "/api/admin/stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        self.assertEqual(stats_res.status_code, 200)
        stats = stats_res.get_json()["stats"]
        self.assertGreaterEqual(stats["total_users"], 3)  # admin, demo user, alice
        self.assertGreaterEqual(stats["total_events"], 1)
        self.assertGreaterEqual(stats["total_registrations"], 1)

        # 10. Alice cancels her registration
        cancel_res = self.client.delete(
            f"/api/my-registrations/{event_id}",
            headers={"Authorization": f"Bearer {alice_token}"}
        )
        self.assertEqual(cancel_res.status_code, 200)

        # 11. Verify registration is gone
        my_regs_after = self.client.get(
            "/api/my-registrations",
            headers={"Authorization": f"Bearer {alice_token}"}
        )
        self.assertEqual(len(my_regs_after.get_json()["registrations"]), 0)


if __name__ == "__main__":
    unittest.main()
