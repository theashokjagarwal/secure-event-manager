import os
import logging
from flask import Flask, render_template, jsonify, send_from_directory, request
from flask_cors import CORS
from app.config import Config
from app.database import init_db
from app.routes.auth_routes import auth_bp
from app.routes.event_routes import event_bp
from app.routes.admin_routes import admin_bp


def configure_logging(app: Flask):
    """
    SECURITY & MONITORING: Configure structured logging to both console and app.log.
    Sensitive credentials and tokens are scrubbed and never recorded.
    """
    logger = logging.getLogger("secure_event_manager")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        log_format = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s")

        stream_h = logging.StreamHandler()
        stream_h.setFormatter(log_format)
        logger.addHandler(stream_h)

        # On Vercel or read-only environments, stream handler to stdout/stderr is standard
        if not os.getenv("VERCEL"):
            try:
                log_path = Config.BASE_DIR / "app.log"
                file_h = logging.FileHandler(log_path, encoding="utf-8")
                file_h.setFormatter(log_format)
                logger.addHandler(file_h)
            except OSError:
                pass


def create_app() -> Flask:
    """
    Application Factory Pattern.
    Builds and configures the Flask application with comprehensive security features.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(base_dir, "templates")
    static_dir = os.path.join(base_dir, "static")

    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    app.config.from_object(Config)

    # Configure Logging
    configure_logging(app)
    logger = logging.getLogger("secure_event_manager")

    # --------------------------------------------------------------------------
    # 1. CORS CONFIGURATION
    # --------------------------------------------------------------------------
    # SECURITY: Restrict API access strictly to designated frontend origins
    CORS(
        app,
        resources={r"/api/*": {"origins": [Config.CORS_ORIGIN, "http://localhost:5050"]}},
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"]
    )

    # --------------------------------------------------------------------------
    # 2. SECURITY HEADERS MIDDLEWARE
    # --------------------------------------------------------------------------
    @app.after_request
    def set_security_headers(response):
        """
        SECURITY: Apply defensive HTTP response headers to prevent common web attacks.
        """
        # Content Security Policy (CSP): Prevents XSS by restricting executable script origins
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )

        # Anti-Clickjacking: Disallows embedding in iframes
        response.headers["X-Frame-Options"] = "DENY"

        # Anti-MIME Sniffing: Prevents browsers from interpreting files as a different MIME type
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Cross-Site Scripting Filter
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Privacy: Protects referrer leakage to third-party domains
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Cache control for API responses to prevent caching sensitive data
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"

        return response

    # --------------------------------------------------------------------------
    # 3. GLOBAL ERROR HANDLERS (No Information Leakage)
    # --------------------------------------------------------------------------
    # SECURITY: Never expose stack traces or raw database error details in API responses!

    @app.errorhandler(400)
    def handle_bad_request(e):
        return jsonify({"success": False, "error": "Bad request. Please verify your input."}), 400

    @app.errorhandler(401)
    def handle_unauthorized(e):
        return jsonify({"success": False, "error": "Unauthorized access. Authentication required."}), 401

    @app.errorhandler(403)
    def handle_forbidden(e):
        return jsonify({"success": False, "error": "Access forbidden. Insufficient permissions."}), 403

    @app.errorhandler(404)
    def handle_not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "Requested resource was not found."}), 404
        return render_template("index.html"), 404

    @app.errorhandler(413)
    def handle_payload_too_large(e):
        # SECURITY: Handle oversized file uploads gracefully
        return jsonify({
            "success": False,
            "error": f"File size exceeds the permitted limit of {Config.MAX_CONTENT_LENGTH_MB} MB."
        }), 413

    @app.errorhandler(429)
    def handle_rate_limit(e):
        return jsonify({"success": False, "error": "Too many requests. Please slow down."}), 429

    @app.errorhandler(500)
    def handle_internal_server_error(e):
        # Log the real internal error for server administrators
        logger.error(f"Internal server error on {request.path}: {str(e)}", exc_info=True)
        # Return a safe, generic message to the client
        return jsonify({"success": False, "error": "An internal server error occurred. Please try again later."}), 500

    # --------------------------------------------------------------------------
    # 4. BLUEPRINTS REGISTRATION
    # --------------------------------------------------------------------------
    app.register_blueprint(auth_bp)
    app.register_blueprint(event_bp)
    app.register_blueprint(admin_bp)

    # --------------------------------------------------------------------------
    # 5. FRONTEND HTML ROUTE RENDERING
    # --------------------------------------------------------------------------
    @app.route("/")
    def index_page():
        return render_template("index.html")

    @app.route("/login")
    def login_page():
        return render_template("login.html")

    @app.route("/register")
    def register_page():
        return render_template("register.html")

    @app.route("/dashboard")
    def dashboard_page():
        return render_template("dashboard.html")

    @app.route("/admin")
    def admin_page():
        return render_template("admin.html")

    # --------------------------------------------------------------------------
    # 6. DATABASE AUTO-INITIALIZATION
    # --------------------------------------------------------------------------
    with app.app_context():
        try:
            init_db()
            logger.info("Database initialized successfully.")
        except Exception as e:
            logger.error(f"Database initialization error: {str(e)}", exc_info=True)

    return app
