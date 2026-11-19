import os
from flask import Blueprint, request, jsonify
from app.database import get_db
from app.models import Event, User, Registration
from app.security import (
    admin_required,
    validate_text,
    validate_url,
    validate_event_date,
    validate_file_upload,
    save_secure_file,
    log_audit,
    log_security_alert
)
from app.ai_service import AIEventResearcher
from app.config import Config

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.route("/events", methods=["POST"])
@admin_required
def create_event():
    """
    Create a new event with optional city, college name, application link, and secure file attachment.
    """
    if request.content_type and "multipart/form-data" in request.content_type:
        title = request.form.get("title")
        description = request.form.get("description")
        category = request.form.get("category", "General")
        event_type = request.form.get("event_type", "Tech Fest")
        city = request.form.get("city", "Online")
        college_name = request.form.get("college_name", "")
        application_link = request.form.get("application_link", "")
        event_date_str = request.form.get("event_date")
        location = request.form.get("location")
        file_obj = request.files.get("attachment")
    else:
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        description = data.get("description")
        category = data.get("category", "General")
        event_type = data.get("event_type", "Tech Fest")
        city = data.get("city", "Online")
        college_name = data.get("college_name", "")
        application_link = data.get("application_link", "")
        event_date_str = data.get("event_date")
        location = data.get("location")
        file_obj = None

    # 1. Validate Title
    v_title, title_val = validate_text(title, "Title", min_len=3, max_len=180)
    if not v_title:
        return jsonify({"success": False, "error": title_val}), 400

    # 2. Validate Description
    v_desc, desc_val = validate_text(description, "Description", min_len=10, max_len=2500)
    if not v_desc:
        return jsonify({"success": False, "error": desc_val}), 400

    # 3. Validate Category & Event Type
    v_cat, cat_val = validate_text(category, "Category", min_len=2, max_len=50)
    if not v_cat:
        cat_val = "General"

    v_type, type_val = validate_text(event_type, "Event Type", min_len=2, max_len=50)
    if not v_type:
        type_val = "Tech Fest"

    # 4. Validate City & College
    v_city, city_val = validate_text(city, "City", min_len=2, max_len=100)
    if not v_city:
        city_val = "Online"

    clean_college = college_name.strip()[:150] if college_name else None

    # 5. Validate Application URL to prevent javascript: XSS
    valid_url, clean_url, url_err = validate_url(application_link)
    if not valid_url:
        return jsonify({"success": False, "error": url_err}), 400

    # 6. Validate Location
    v_loc, loc_val = validate_text(location, "Location", min_len=3, max_len=200)
    if not v_loc:
        return jsonify({"success": False, "error": loc_val}), 400

    # 7. Validate Event Date
    v_date, parsed_date, date_err = validate_event_date(event_date_str)
    if not v_date:
        return jsonify({"success": False, "error": date_err}), 400

    stored_filename = None
    original_filename = None

    # 8. Validate File Attachment if provided
    if file_obj and file_obj.filename:
        is_valid_file, file_err = validate_file_upload(file_obj)
        if not is_valid_file:
            return jsonify({"success": False, "error": file_err}), 400

        try:
            stored_filename, original_filename = save_secure_file(file_obj, Config.UPLOAD_FOLDER)
        except Exception as e:
            log_security_alert("FILE_SAVE_ERROR", request.remote_addr, str(e))
            return jsonify({"success": False, "error": "Failed to safely store file attachment."}), 500

    with get_db() as db:
        new_event = Event(
            title=title_val,
            description=desc_val,
            category=cat_val,
            event_type=type_val,
            city=city_val,
            college_name=clean_college,
            event_date=parsed_date,
            location=loc_val,
            application_link=clean_url,
            is_ai_discovered=False,
            attachment_filename=stored_filename,
            attachment_original_name=original_filename,
            created_by=request.current_user["id"]
        )
        db.add(new_event)
        db.flush()

        log_audit("EVENT_CREATED", request.current_user["id"], request.remote_addr)

        return jsonify({
            "success": True,
            "message": "Event created successfully!",
            "event": new_event.to_dict()
        }), 201


@admin_bp.route("/ai/auto-discover", methods=["POST"])
@admin_required
def ai_auto_discover_events():
    """
    AI Feature: Automatically research and ingest real-time tech events,
    college fests, and hackathons across India into the database.
    """
    data = request.get_json(silent=True) or {}
    city = data.get("city")
    event_type = data.get("event_type")
    count = min(int(data.get("count", 5)), 15)  # Cap at 15 events per batch

    with get_db() as db:
        added_count, new_events = AIEventResearcher.auto_ingest_events(
            db_session=db,
            admin_user_id=request.current_user["id"],
            city=city,
            event_type=event_type,
            count=count
        )

        log_audit("AI_AUTO_DISCOVERED_EVENTS", request.current_user["id"], request.remote_addr)

        return jsonify({
            "success": True,
            "message": f"AI Researcher successfully discovered and added {added_count} new events!",
            "added_count": added_count,
            "events": new_events
        })


@admin_bp.route("/events/<int:event_id>", methods=["DELETE"])
@admin_required
def delete_event(event_id: int):
    """
    Delete event and its associated file attachment.
    """
    with get_db() as db:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            return jsonify({"success": False, "error": "Event not found."}), 404

        if event.attachment_filename:
            file_path = os.path.join(Config.UPLOAD_FOLDER, event.attachment_filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError as e:
                    log_security_alert("FILE_CLEANUP_FAILED", request.remote_addr, str(e))

        db.delete(event)
        log_audit("EVENT_DELETED", request.current_user["id"], request.remote_addr)

        return jsonify({
            "success": True,
            "message": "Event deleted successfully."
        })


@admin_bp.route("/events/<int:event_id>/attendees", methods=["GET"])
@admin_required
def get_event_attendees(event_id: int):
    """
    List all attendees registered for a specific event.
    """
    with get_db() as db:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            return jsonify({"success": False, "error": "Event not found."}), 404

        registrations = db.query(Registration).filter(
            Registration.event_id == event_id
        ).order_by(Registration.registered_at.asc()).all()

        return jsonify({
            "success": True,
            "event_title": event.title,
            "count": len(registrations),
            "attendees": [r.to_dict() for r in registrations]
        })


@admin_bp.route("/stats", methods=["GET"])
@admin_required
def get_system_stats():
    """
    System Statistics for Admin Dashboard.
    """
    with get_db() as db:
        total_events = db.query(Event).count()
        total_users = db.query(User).count()
        total_registrations = db.query(Registration).count()

        return jsonify({
            "success": True,
            "stats": {
                "total_events": total_events,
                "total_users": total_users,
                "total_registrations": total_registrations
            }
        })
