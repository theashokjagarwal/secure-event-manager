import os
from flask import Blueprint, request, jsonify, send_from_directory, current_app
from app.database import get_db
from app.models import Event, Registration
from app.security import login_required, log_audit, log_security_alert
from app.config import Config

event_bp = Blueprint("events", __name__, url_prefix="/api")


@event_bp.route("/events", methods=["GET"])
def list_events():
    """
    Public Event Catalog
    SECURITY:
    - Search queries and filters are passed strictly through SQLAlchemy ORM parameters.
    - No SQL string concatenation is ever performed.
    - Safe for public consumption.
    """
    search_query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    with get_db() as db:
        # Base query using ORM parameterized query builder
        query = db.query(Event)

        # Sanitize and apply filters safely
        if search_query:
            # SQLAlchemy ilike with parameterized binding prevents SQL Injection
            search_pattern = f"%{search_query[:50]}%"
            query = query.filter(
                (Event.title.ilike(search_pattern)) | 
                (Event.description.ilike(search_pattern)) |
                (Event.location.ilike(search_pattern))
            )

        if category:
            query = query.filter(Event.category == category[:30])

        events = query.order_by(Event.event_date.asc()).all()
        return jsonify({
            "success": True,
            "count": len(events),
            "events": [event.to_dict() for event in events]
        })


@event_bp.route("/events/<int:event_id>", methods=["GET"])
def get_event(event_id: int):
    """
    Retrieve single event details by ID.
    Using type-casted integer path parameter prevents injection attacks.
    """
    with get_db() as db:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            return jsonify({"success": False, "error": "Event not found."}), 404
        return jsonify({
            "success": True,
            "event": event.to_dict()
        })


@event_bp.route("/events/<int:event_id>/register", methods=["POST"])
@login_required
def register_for_event(event_id: int):
    """
    Register authenticated user for an event.
    SECURITY:
    - Requires valid JWT authentication (@login_required).
    - Uses current_user identity from the token, preventing impersonation.
    - Uses database constraint to block duplicate registrations.
    """
    user_id = request.current_user["id"]

    with get_db() as db:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            return jsonify({"success": False, "error": "Event not found."}), 404

        existing = db.query(Registration).filter(
            Registration.event_id == event_id,
            Registration.user_id == user_id
        ).first()

        if existing:
            return jsonify({
                "success": False,
                "error": "You are already registered for this event."
            }), 409

        registration = Registration(
            event_id=event_id,
            user_id=user_id,
            status="confirmed"
        )
        db.add(registration)
        db.flush()

        log_audit("EVENT_REGISTRATION", user_id, request.remote_addr)

        return jsonify({
            "success": True,
            "message": f"Successfully registered for '{event.title}'!",
            "registration": registration.to_dict()
        }), 201


@event_bp.route("/my-registrations", methods=["GET"])
@login_required
def get_my_registrations():
    """
    Retrieve list of events registered by the authenticated user.
    """
    user_id = request.current_user["id"]
    with get_db() as db:
        registrations = db.query(Registration).filter(
            Registration.user_id == user_id
        ).order_by(Registration.registered_at.desc()).all()

        return jsonify({
            "success": True,
            "registrations": [r.to_dict() for r in registrations]
        })


@event_bp.route("/my-registrations/<int:event_id>", methods=["DELETE"])
@login_required
def cancel_registration(event_id: int):
    """
    Cancel an existing event registration.
    Uses DELETE HTTP verb for resource removal.
    """
    user_id = request.current_user["id"]
    with get_db() as db:
        registration = db.query(Registration).filter(
            Registration.event_id == event_id,
            Registration.user_id == user_id
        ).first()

        if not registration:
            return jsonify({"success": False, "error": "Registration not found."}), 404

        db.delete(registration)
        log_audit("CANCEL_REGISTRATION", user_id, request.remote_addr)

        return jsonify({
            "success": True,
            "message": "Registration successfully cancelled."
        })


@event_bp.route("/events/<int:event_id>/attachment", methods=["GET"])
def download_attachment(event_id: int):
    """
    Secure file download endpoint.
    SECURITY FEATURES:
    - Path Traversal Protection: Uses send_from_directory which enforces the file
      stays within the configured upload directory.
    - Prevents direct execution by setting safe download headers.
    - Sets 'X-Content-Type-Options: nosniff' to stop browser MIME confusion attacks.
    """
    with get_db() as db:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event or not event.attachment_filename:
            return jsonify({"success": False, "error": "Attachment not found."}), 404

        filename = event.attachment_filename
        download_name = event.attachment_original_name or "event-attachment"

        # Check if file actually exists on filesystem
        full_path = os.path.join(Config.UPLOAD_FOLDER, filename)
        if not os.path.isfile(full_path):
            log_security_alert("MISSING_ATTACHMENT_FILE", request.remote_addr, f"File {filename} missing on disk")
            return jsonify({"success": False, "error": "File is unavailable."}), 404

        response = send_from_directory(
            Config.UPLOAD_FOLDER,
            filename,
            as_attachment=True,
            download_name=download_name
        )
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
