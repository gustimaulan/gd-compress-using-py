import os
import json
import hashlib
import secrets
from pathlib import Path
from flask import request, jsonify
from functools import wraps
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ─── Paths ───────────────────────────────────────────────────────────────────────────
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
TOKENS_DIR = DATA_DIR / "tokens"
TOKENS_DIR.mkdir(exist_ok=True)
CONFIGS_DIR = DATA_DIR / "configs"
CONFIGS_DIR.mkdir(exist_ok=True)
SESSIONS_DIR = DATA_DIR / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/drive",
]

IMAGE_MIME_TYPES = [
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/bmp",
    "image/tiff",
]

# ─── Token Session Store ──────────────────────────────────────────────────────

def create_session_token(email: str, name: str = "", picture: str = "") -> str:
    """Create a new session token and persist session data to disk."""
    token = secrets.token_hex(32)
    session_file = SESSIONS_DIR / f"{token}.json"
    session_file.write_text(json.dumps({
        "email": email,
        "name": name,
        "picture": picture,
    }))
    return token

def get_session_data(token: str) -> dict | None:
    """Read session data for a given token. Returns None if invalid."""
    if not token:
        return None
    session_file = SESSIONS_DIR / f"{token}.json"
    if not session_file.exists():
        return None
    try:
        return json.loads(session_file.read_text())
    except Exception:
        return None

def delete_session_token(token: str):
    """Delete a session token file."""
    session_file = SESSIONS_DIR / f"{token}.json"
    if session_file.exists():
        session_file.unlink()

def _get_current_token() -> str | None:
    """Extract Bearer token from the Authorization header or query param (for SSE)."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    # Fallback: token as query param (needed for EventSource which can't set headers)
    return request.args.get("token")

def get_current_user_email() -> str | None:
    """Get the email of the currently authenticated user from the Bearer token."""
    token = _get_current_token()
    data = get_session_data(token)
    return data["email"] if data else None

# ─── Config (per-user) ────────────────────────────────────────────────────────

def _user_config_path(email: str) -> Path:
    safe = hashlib.sha256(email.encode()).hexdigest()[:16]
    return CONFIGS_DIR / f"{safe}.json"

def load_config() -> dict:
    email = get_current_user_email()
    if email:
        config_file = _user_config_path(email)
        if config_file.exists():
            try:
                return json.loads(config_file.read_text())
            except Exception:
                pass
    return {
        "folder_id": "",
        "quality": 80,
        "min_size_kb": 0,
        "max_width": None,
        "max_height": None,
        "delete_original": False,
        "output_folder_id": "",
    }

def save_config(data: dict):
    email = get_current_user_email()
    if not email:
        return
    config_file = _user_config_path(email)
    config_file.write_text(json.dumps(data, indent=2))

# ─── Drive ────────────────────────────────────────────────────────────────────

def _user_token_path(email: str) -> Path:
    """Get the token file path for a specific user."""
    safe = hashlib.sha256(email.encode()).hexdigest()[:16]
    return TOKENS_DIR / f"{safe}.json"

def get_drive_service(user_email: str = None):
    """Build a Drive service from the current user's stored token."""
    email = user_email or get_current_user_email()
    if not email:
        return None
    token_file = _user_token_path(email)
    if not token_file.exists():
        return None
    try:
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_file.write_text(creds.to_json())
        if creds and creds.valid:
            return build("drive", "v3", credentials=creds)
    except Exception:
        pass
    return None

# ─── Auth Decorator ───────────────────────────────────────────────────────────

def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        email = get_current_user_email()
        if not email:
            return jsonify({"error": "Unauthorized"}), 401
        # Attach email to request context for downstream use
        request.user_email = email
        return f(*args, **kwargs)
    return decorated
