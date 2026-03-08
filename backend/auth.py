import os
import traceback
from flask import Blueprint, jsonify, request, session, redirect, url_for, current_app
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token as id_token_module
from google.auth.transport import requests as google_requests

from .utils import (
    SCOPES,
    create_session_token,
    get_session_data,
    delete_session_token,
    _get_current_token,
)

auth_bp = Blueprint("auth", __name__)

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

def _build_redirect_uri():
    """Build the OAuth callback redirect URI, using APP_DOMAIN env if set."""
    app_domain = os.environ.get("APP_DOMAIN", "").strip()
    if app_domain:
        domain = app_domain.rstrip("/")
        if not domain.startswith("http://") and not domain.startswith("https://"):
            domain = f"https://{domain}"
        return f"{domain}/api/oauth/callback"
    return url_for("auth.oauth_callback", _external=True)

def _build_flow(state=None) -> Flow:
    """Build an OAuth Flow with combined sign-in + Drive scopes."""
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
        raise RuntimeError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set.")
    redirect_uri = _build_redirect_uri()
    client_config = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }
    return Flow.from_client_config(
        client_config, scopes=SCOPES, state=state,
        redirect_uri=redirect_uri,
    )

@auth_bp.route("/api/auth/login")
def auth_login():
    try:
        flow = _build_flow()
        auth_url, state = flow.authorization_url(
            access_type="offline",
            prompt="select_account consent"
        )
        # We still need Flask session briefly to store OAuth state across the redirect
        session["oauth_state"] = state
        session["oauth_code_verifier"] = getattr(flow, "code_verifier", None)
        return jsonify({"url": auth_url})
    except Exception as e:
        current_app.logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 400

@auth_bp.route("/api/oauth/callback")
def oauth_callback():
    try:
        flow = _build_flow(state=session.get("oauth_state"))
        code_verifier = session.pop("oauth_code_verifier", None)
        redirect_uri = _build_redirect_uri()
        query = request.query_string.decode()
        authorization_response = f"{redirect_uri}?{query}"

        flow.fetch_token(
            authorization_response=authorization_response,
            code_verifier=code_verifier,
        )
        creds = flow.credentials

        idinfo = id_token_module.verify_oauth2_token(
            creds.id_token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
        email = idinfo.get("email", "")
        name = idinfo.get("name", "")
        picture = idinfo.get("picture", "")

        # Store Google Drive token for this user
        from .db import save_token
        save_token(email, creds.to_json())

        # Create a session token (replaces Flask cookie session)
        auth_token = create_session_token(email, name, picture)

        # Clear the temporary Flask session used for OAuth state
        session.clear()

    except Exception as e:
        current_app.logger.error(traceback.format_exc())
        return f"OAuth failed: {e}", 400

    # Redirect with token in URL — frontend will capture it in sessionStorage
    frontend_url = os.environ.get("FRONTEND_URL", "").strip().rstrip("/")
    if frontend_url:
        return redirect(f"{frontend_url}/?token={auth_token}")
    return redirect(f"/?token={auth_token}")

@auth_bp.route("/api/auth/me")
def auth_me():
    token = _get_current_token()
    data = get_session_data(token)
    if data:
        from .db import get_token
        has_drive = get_token(data["email"]) is not None
        return jsonify({
            "authenticated": True,
            "drive_connected": has_drive,
            "email": data["email"],
            "name": data.get("name", ""),
            "picture": data.get("picture", ""),
        })
    return jsonify({"authenticated": False})

@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    token = _get_current_token()
    if token:
        delete_session_token(token)
    return jsonify({"ok": True})
