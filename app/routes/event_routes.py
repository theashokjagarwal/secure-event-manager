import os
from flask import Blueprint, request, jsonify, send_from_directory
from app.database import get_db
from app.models import Event, Registration
from app.security import login_required, log_audit, log_security_alert
from app.ai_service import AIEventResearcher
from app.config import Config

event_bp = Blueprint("events", __name__, url_prefix="/api")


@event_bp.route("/events", methods=["GET"])
def list_events():
    """
    Public Events Catalog supporting City, College, Event Type & Search Filters.
    SECURITY:
    - Search queries and filters are passed strictly through SQLAlchemy ORM parameters.
    - No SQL string concatenation is ever performed.
    """
    search_query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    city = request.args.get("city", "").strip()
    college = request.args.get("college", "").strip()
    event_type = request.args.get("event_type", "").strip()

    with get_db() as db:
        query = db.query(Event)

        # Sanitize and apply filters safely
        if search_query:
            search_pattern = f"%{search_query[:50]}%"
            query = query.filter(
                (Event.title.ilike(search_pattern)) | 
                (Event.description.ilike(search_pattern)) |
                (Event.location.ilike(search_pattern)) |
                (Event.city.ilike(search_pattern)) |
                (Event.college_name.ilike(search_pattern))
            )

        if category and category.lower() != "all":
            query = query.filter(Event.category == category[:40])

        if city and city.lower() != "all":
            query = query.filter(Event.city.ilike(f"%{city[:40]}%"))

        if college and college.lower() != "all":
            query = query.filter(Event.college_name.ilike(f"%{college[:50]}%"))

        if event_type and event_type.lower() != "all":
            query = query.filter(Event.event_type.ilike(f"%{event_type[:40]}%"))

        events = query.order_by(Event.event_date.asc()).all()

        # Collect distinct cities and event types for UI filters
        distinct_cities = [c[0] for c in db.query(Event.city).distinct().all() if c[0]]

        return jsonify({
            "success": True,
            "count": len(events),
            "cities": distinct_cities,
            "events": [event.to_dict() for event in events]
        })


@event_bp.route("/events/<int:event_id>", methods=["GET"])
def get_event(event_id: int):
    """
    Retrieve single event details by ID.
    """
    with get_db() as db:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            return jsonify({"success": False, "error": "Event not found."}), 404
        return jsonify({
            "success": True,
            "event": event.to_dict()
        })


@event_bp.route("/events/<int:event_id>/ai-guide", methods=["GET"])
def get_event_ai_guide(event_id: int):
    """
    AI Feature: Generate instant preparation roadmap, required tech stack,
    and team strategy for an event or hackathon.
    """
    with get_db() as db:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            return jsonify({"success": False, "error": "Event not found."}), 404

        ai_guide = AIEventResearcher.generate_preparation_roadmap(event)
        return jsonify({
            "success": True,
            "ai_guide": ai_guide
        })


@event_bp.route("/events/<int:event_id>/register", methods=["POST"])
@login_required
def register_for_event(event_id: int):
    """
    Register authenticated user for an event.
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
    """
    with get_db() as db:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event or not event.attachment_filename:
            return jsonify({"success": False, "error": "Attachment not found."}), 404

        filename = event.attachment_filename
        download_name = event.attachment_original_name or "event-attachment"

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
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
