import os
from pathlib import Path
from flask import Flask, render_template, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

def create_app():
    load_dotenv()
    
    from .db import init_db
    init_db()
    
    app = Flask(__name__, static_folder=None, template_folder="../templates")
    app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")
    
    # Trust reverse proxy headers (Traefik) so url_for() generates https:// URLs
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    # Allow OAuth over plain http for local dev (APP_DOMAIN starts with http://)
    _app_domain = os.environ.get("APP_DOMAIN", "")
    if _app_domain.startswith("http://"):
        os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

    # Register Blueprints
    from .auth import auth_bp
    from .drive import drive_bp
    from .jobs import jobs_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(drive_bp)
    app.register_blueprint(jobs_bp)

    # ─── Frontend Serving ──────────────────────────────────────────────────────────
    FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

    @app.route("/")
    @app.route("/login")
    @app.route("/duplicates")
    def index():
        index_file = FRONTEND_DIST / "index.html"
        if index_file.exists():
            return index_file.read_text(), 200, {"Content-Type": "text/html"}
        return render_template("index.html", password_required=False)

    @app.route("/assets/<path:filename>")
    def vue_assets(filename):
        return send_from_directory(FRONTEND_DIST / "assets", filename)

    return app
