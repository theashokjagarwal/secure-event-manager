import os
from flask import Blueprint, request, jsonify
from app.database import get_db
from app.models import Event, User, Registration
from app.security import (
    admin_required,
    validate_text,
    validate_event_date,
    validate_file_upload,
    save_secure_file,
    log_audit,
    log_security_alert
)
from app.config import Config

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.route("/events", methods=["POST"])
@admin_required
def create_event():
    """
    Create a new event with optional secure file attachment.
    SECURITY FEATURES:
    - Protected by Role-Based Access Control (@admin_required).
    - Strict validation on text fields (title, description, category, location).
    - Date parsing ensures dates are valid and in the future.
    - File upload security:
      * Whitelist checking (PDF, DOCX, PNG, JPG).
      * Blacklist rejection of executables (.exe, .sh, .bat).
      * Content magic bytes inspection.
      * UUID filename renaming to stop path traversal and collisions.
    """
    # Support both multipart/form-data (when uploading files) and application/json
    if request.content_type and "multipart/form-data" in request.content_type:
        title = request.form.get("title")
        description = request.form.get("description")
        category = request.form.get("category")
        event_date_str = request.form.get("event_date")
        location = request.form.get("location")
        file_obj = request.files.get("attachment")
    else:
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        description = data.get("description")
        category = data.get("category")
        event_date_str = data.get("event_date")
        location = data.get("location")
        file_obj = None

    # 1. Validate Title
    v_title, title_val = validate_text(title, "Title", min_len=3, max_len=120)
    if not v_title:
        return jsonify({"success": False, "error": title_val}), 400

    # 2. Validate Description
    v_desc, desc_val = validate_text(description, "Description", min_len=10, max_len=2000)
    if not v_desc:
        return jsonify({"success": False, "error": desc_val}), 400

    # 3. Validate Category
    v_cat, cat_val = validate_text(category, "Category", min_len=2, max_len=50)
    if not v_cat:
        return jsonify({"success": False, "error": cat_val}), 400

    # 4. Validate Location
    v_loc, loc_val = validate_text(location, "Location", min_len=3, max_len=150)
    if not v_loc:
        return jsonify({"success": False, "error": loc_val}), 400

    # 5. Validate Event Date
    v_date, parsed_date, date_err = validate_event_date(event_date_str)
    if not v_date:
        return jsonify({"success": False, "error": date_err}), 400

    stored_filename = None
    original_filename = None

    # 6. Validate File Attachment if provided
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
            event_date=parsed_date,
            location=loc_val,
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


@admin_bp.route("/events/<int:event_id>", methods=["PUT"])
@admin_required
def update_event(event_id: int):
    """
    Update existing event details.
    """
    data = request.get_json(silent=True) or {}
    with get_db() as db:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            return jsonify({"success": False, "error": "Event not found."}), 404

        if "title" in data:
            v_t, t_val = validate_text(data["title"], "Title", 3, 120)
            if not v_t:
                return jsonify({"success": False, "error": t_val}), 400
            event.title = t_val

        if "description" in data:
            v_d, d_val = validate_text(data["description"], "Description", 10, 2000)
            if not v_d:
                return jsonify({"success": False, "error": d_val}), 400
            event.description = d_val

        if "category" in data:
            v_c, c_val = validate_text(data["category"], "Category", 2, 50)
            if not v_c:
                return jsonify({"success": False, "error": c_val}), 400
            event.category = c_val

        if "location" in data:
            v_l, l_val = validate_text(data["location"], "Location", 3, 150)
            if not v_l:
                return jsonify({"success": False, "error": l_val}), 400
            event.location = l_val

        if "event_date" in data:
            v_date, parsed_date, date_err = validate_event_date(data["event_date"])
            if not v_date:
                return jsonify({"success": False, "error": date_err}), 400
            event.event_date = parsed_date

        log_audit("EVENT_UPDATED", request.current_user["id"], request.remote_addr)

        return jsonify({
            "success": True,
            "message": "Event updated successfully.",
            "event": event.to_dict()
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

        # Clean up file from disk if present
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
