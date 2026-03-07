#!/usr/bin/env python3
"""
Google Drive Image Compressor — Web App
Runs on a VPS, controlled via browser UI.
"""

import io
import json
import os
import queue
import threading
import time
import uuid
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.middleware.proxy_fix import ProxyFix
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from PIL import Image

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")
# Trust reverse proxy headers (Traefik) so url_for() generates https:// URLs
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# ─── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
CREDENTIALS_FILE = DATA_DIR / "credentials.json"
TOKEN_FILE = DATA_DIR / "token.json"
CONFIG_FILE = DATA_DIR / "config.json"

SCOPES = ["https://www.googleapis.com/auth/drive"]

APP_PASSWORD = os.environ.get("APP_PASSWORD", "")  # empty = no auth

# Google OAuth credentials — can be provided either via env vars OR credentials.json
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

IMAGE_MIME_TYPES = [
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/bmp",
    "image/tiff",
]

# ─── In-memory job store ────────────────────────────────────────────────────────
jobs: dict[str, dict] = {}  # job_id -> { status, log_queue, result, ... }


# ─── Helpers ───────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
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
    CONFIG_FILE.write_text(json.dumps(data, indent=2))


def get_drive_service():
    if not TOKEN_FILE.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())
    if creds and creds.valid:
        return build("drive", "v3", credentials=creds)
    return None


def auth_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_email"):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# ─── Auth (Google ID Token) ────────────────────────────────────────────────────

ALLOWED_EMAILS = [
    e.strip() for e in os.environ.get("ALLOWED_EMAILS", "").split(",") if e.strip()
]


@app.route("/api/auth/google", methods=["POST"])
def google_login():
    """Verify a Google ID token and create a session."""
    from google.oauth2 import id_token as id_token_module
    from google.auth.transport import requests as google_requests

    token = (request.json or {}).get("credential", "")
    if not token:
        return jsonify({"error": "No credential provided"}), 400

    try:
        idinfo = id_token_module.verify_oauth2_token(
            token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID or None,
        )
        email = idinfo.get("email", "")
        name = idinfo.get("name", "")

        # If ALLOWED_EMAILS is set, restrict access
        if ALLOWED_EMAILS and email not in ALLOWED_EMAILS:
            return jsonify({"error": f"Access denied for {email}"}), 403

        session["user_email"] = email
        session["user_name"] = name
        session["user_picture"] = idinfo.get("picture", "")
        return jsonify({
            "ok": True,
            "email": email,
            "name": name,
            "picture": idinfo.get("picture", ""),
        })
    except Exception as e:
        return jsonify({"error": f"Invalid token: {e}"}), 401


@app.route("/api/auth/me")
def auth_me():
    """Check if the user is logged in."""
    if session.get("user_email"):
        return jsonify({
            "authenticated": True,
            "email": session["user_email"],
            "name": session.get("user_name", ""),
            "picture": session.get("user_picture", ""),
        })
    return jsonify({"authenticated": False})


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


# ─── Pages ─────────────────────────────────────────────────────────────────────

FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"


@app.route("/")
def index():
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return index_file.read_text(), 200, {"Content-Type": "text/html"}
    # Fallback to legacy template
    return render_template("index.html", password_required=bool(APP_PASSWORD))


@app.route("/assets/<path:filename>")
def vue_assets(filename):
    from flask import send_from_directory
    return send_from_directory(FRONTEND_DIST / "assets", filename)


# Catch-all for Vue Router history mode
@app.route("/login")
@app.route("/duplicates")
def vue_catch_all():
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return index_file.read_text(), 200, {"Content-Type": "text/html"}
    return render_template("index.html", password_required=False)


# ─── API: Status ───────────────────────────────────────────────────────────────

@app.route("/api/status")
def api_status():
    authed = TOKEN_FILE.exists()
    creds_uploaded = CREDENTIALS_FILE.exists()
    env_creds = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
    config = load_config()
    return jsonify({
        "authenticated": authed,
        "creds_uploaded": creds_uploaded,
        "env_creds": env_creds,
        "oauth_ready": creds_uploaded or env_creds,
        "google_client_id": GOOGLE_CLIENT_ID,
        "config": config,
    })


# ─── API: Upload files ─────────────────────────────────────────────────────────

@app.route("/api/upload/credentials", methods=["POST"])
@auth_required
def upload_credentials():
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file"}), 400
    try:
        content = json.loads(f.read())
        # Accept credentials.json or token.json
        CREDENTIALS_FILE.write_text(json.dumps(content))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/upload/token", methods=["POST"])
@auth_required
def upload_token():
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file"}), 400
    try:
        content = json.loads(f.read())
        TOKEN_FILE.write_text(json.dumps(content))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ─── API: OAuth flow ───────────────────────────────────────────────────────────

def _build_flow(state=None) -> Flow:
    """
    Build an OAuth Flow from either:
    1. GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET env vars (preferred)
    2. credentials.json file (fallback)
    """
    redirect_uri = url_for("oauth_callback", _external=True)
    if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
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
    elif CREDENTIALS_FILE.exists():
        return Flow.from_client_secrets_file(
            str(CREDENTIALS_FILE), scopes=SCOPES, state=state,
            redirect_uri=redirect_uri,
        )
    raise RuntimeError("No OAuth credentials configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET env vars, or upload credentials.json.")


@app.route("/api/oauth/start")
@auth_required
def oauth_start():
    try:
        flow = _build_flow()
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    auth_url, state = flow.authorization_url(access_type="offline", prompt="consent")
    session["oauth_state"] = state
    # Persist the PKCE code_verifier so the callback can use it
    session["oauth_code_verifier"] = getattr(flow, "code_verifier", None)
    return jsonify({"url": auth_url})


@app.route("/api/oauth/callback")
def oauth_callback():
    try:
        flow = _build_flow(state=session.get("oauth_state"))
        code_verifier = session.pop("oauth_code_verifier", None)
        flow.fetch_token(
            authorization_response=request.url,
            code_verifier=code_verifier,
        )
        TOKEN_FILE.write_text(flow.credentials.to_json())
    except Exception as e:
        return f"OAuth failed: {e}", 400
    return redirect("/?auth=success")


# ─── API: Config ───────────────────────────────────────────────────────────────

@app.route("/api/config", methods=["GET"])
def get_config():
    return jsonify(load_config())


@app.route("/api/config", methods=["POST"])
@auth_required
def set_config():
    data = request.json or {}
    config = load_config()
    for key in ["folder_id", "quality", "min_size_kb", "max_width", "max_height",
                "delete_original", "output_folder_id"]:
        if key in data:
            config[key] = data[key]
    save_config(config)
    return jsonify({"ok": True, "config": config})


@app.route("/api/drive/folders")
@auth_required
def list_drive_folders():
    """Returns all Drive folders accessible to the user for dropdown population."""
    service = get_drive_service()
    if not service:
        return jsonify({"error": "Not authenticated with Google Drive"}), 401

    try:
        folders = []
        page_token = None
        while True:
            resp = service.files().list(
                q="mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces="drive",
                fields="nextPageToken, files(id, name)",
                orderBy="name",
                pageSize=200,
                pageToken=page_token,
            ).execute()
            folders.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return jsonify(folders)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── API: Duplicate Detection ──────────────────────────────────────────────────

@app.route("/api/drive/duplicates")
@auth_required
def list_duplicates():
    """Find duplicate files in a folder by MD5 checksum."""
    folder_id = request.args.get("folder_id", "").strip()
    if not folder_id:
        return jsonify({"error": "folder_id is required"}), 400

    service = get_drive_service()
    if not service:
        return jsonify({"error": "Not authenticated with Google Drive"}), 401

    try:
        files = []
        page_token = None
        while True:
            resp = service.files().list(
                q=f"'{folder_id}' in parents and trashed=false and mimeType!='application/vnd.google-apps.folder'",
                spaces="drive",
                fields="nextPageToken, files(id, name, size, md5Checksum, mimeType, modifiedTime)",
                pageSize=500,
                pageToken=page_token,
            ).execute()
            files.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        # Group by md5Checksum
        hash_map = defaultdict(list)
        for f in files:
            key = f.get("md5Checksum") or f.get("name", "")
            hash_map[key].append(f)

        # Only keep groups with duplicates
        groups = []
        for key, group in hash_map.items():
            if len(group) > 1:
                groups.append({
                    "hash": key,
                    "count": len(group),
                    "files": group,
                })

        return jsonify({
            "total_files": len(files),
            "duplicate_groups": len(groups),
            "groups": groups,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/drive/duplicates/cleanup", methods=["POST"])
@auth_required
def cleanup_duplicates():
    """Delete selected duplicate files by IDs."""
    data = request.json or {}
    file_ids = data.get("file_ids", [])
    if not file_ids:
        return jsonify({"error": "No file_ids provided"}), 400

    service = get_drive_service()
    if not service:
        return jsonify({"error": "Not authenticated with Google Drive"}), 401

    deleted = 0
    errors = []
    for fid in file_ids:
        try:
            service.files().delete(fileId=fid).execute()
            deleted += 1
        except Exception as e:
            errors.append({"id": fid, "error": str(e)})

    return jsonify({"deleted": deleted, "errors": errors})


# ─── API: Jobs ─────────────────────────────────────────────────────────────────

@app.route("/api/jobs", methods=["POST"])
@auth_required
def start_job():
    config = load_config()
    folder_id = config.get("folder_id", "").strip()
    if not folder_id:
        return jsonify({"error": "No folder ID configured"}), 400

    service = get_drive_service()
    if not service:
        return jsonify({"error": "Not authenticated with Google Drive"}), 401

    job_id = str(uuid.uuid4())[:8]
    log_q = queue.Queue()
    jobs[job_id] = {
        "id": job_id,
        "status": "running",
        "log_queue": log_q,
        "stats": {"success": 0, "failed": 0, "total": 0},
        "created_at": time.time(),
    }

    thread = threading.Thread(
        target=run_compression_job,
        args=(job_id, service, config, log_q),
        daemon=True,
    )
    thread.start()
    return jsonify({"job_id": job_id})


@app.route("/api/jobs/<job_id>")
def job_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({
        "id": job["id"],
        "status": job["status"],
        "stats": job["stats"],
    })


@app.route("/api/jobs")
def list_jobs():
    result = []
    for job in sorted(jobs.values(), key=lambda j: j["created_at"], reverse=True)[:20]:
        result.append({
            "id": job["id"],
            "status": job["status"],
            "stats": job["stats"],
            "created_at": job["created_at"],
        })
    return jsonify(result)


@app.route("/api/jobs/<job_id>/stream")
def job_stream(job_id):
    """Server-Sent Events stream for real-time log output."""
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    def event_stream():
        log_q = job["log_queue"]
        while True:
            try:
                msg = log_q.get(timeout=30)
                if msg is None:  # sentinel: job done
                    yield f"data: __done__\n\n"
                    break
                yield f"data: {msg}\n\n"
            except queue.Empty:
                yield f"data: __ping__\n\n"

    return Response(event_stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ─── Compression Worker ─────────────────────────────────────────────────────────

def compress_image(data: bytes, quality: int = 80,
                   max_width: int = None, max_height: int = None) -> bytes:
    img = Image.open(io.BytesIO(data))
    if img.mode in ("P", "RGBA"):
        img = img.convert("RGBA")
    elif img.mode != "RGB":
        img = img.convert("RGB")
    if max_width or max_height:
        img.thumbnail((max_width or img.width, max_height or img.height), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="WEBP", quality=quality, method=6)
    out.seek(0)
    return out.read()


def run_compression_job(job_id: str, service, config: dict, log_q: queue.Queue):
    def log(msg: str):
        log_q.put(msg)

    job = jobs[job_id]

    try:
        folder_id = config["folder_id"]
        quality = int(config.get("quality", 80))
        min_size_kb = int(config.get("min_size_kb", 0))
        max_width = config.get("max_width") or None
        max_height = config.get("max_height") or None
        delete_original = bool(config.get("delete_original", False))
        output_folder = config.get("output_folder_id", "").strip() or folder_id

        if max_width:
            max_width = int(max_width)
        if max_height:
            max_height = int(max_height)

        # List files
        log(f"🔍 Scanning folder for images...")
        mime_query = " or ".join([f"mimeType='{m}'" for m in IMAGE_MIME_TYPES])
        query = f"('{folder_id}' in parents) and ({mime_query}) and trashed=false"
        files = []
        page_token = None
        while True:
            resp = service.files().list(
                q=query, spaces="drive",
                fields="nextPageToken, files(id, name, mimeType, size)",
                pageToken=page_token,
            ).execute()
            for f in resp.get("files", []):
                size_kb = int(f.get("size", 0)) / 1024
                if size_kb >= min_size_kb:
                    files.append(f)
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        total = len(files)
        job["stats"]["total"] = total
        log(f"📁 Found {total} image(s) to process.")

        if total == 0:
            log("✅ Nothing to do.")
            job["status"] = "done"
            log_q.put(None)
            return

        success = 0
        failed = 0

        for i, file in enumerate(files, 1):
            name = file["name"]
            fid = file["id"]
            orig_size = int(file.get("size", 0))
            stem = Path(name).stem
            webp_name = f"{stem}.webp"

            log(f"[{i}/{total}] 📥 {name} ({orig_size / 1024:.1f} KB)")
            try:
                # Download
                req = service.files().get_media(fileId=fid)
                buf = io.BytesIO()
                dl = MediaIoBaseDownload(buf, req)
                done = False
                while not done:
                    _, done = dl.next_chunk()
                buf.seek(0)
                raw = buf.read()

                # Compress
                log(f"[{i}/{total}] ⚙️  Converting to WebP (q={quality})...")
                webp = compress_image(raw, quality=quality,
                                      max_width=max_width, max_height=max_height)
                webp_size = len(webp)
                savings = (1 - webp_size / orig_size) * 100 if orig_size > 0 else 0

                # Upload
                media = MediaIoBaseUpload(io.BytesIO(webp), mimetype="image/webp", resumable=True)
                uploaded = service.files().create(
                    body={"name": webp_name, "parents": [output_folder]},
                    media_body=media, fields="id"
                ).execute()
                log(f"[{i}/{total}] ✅ {webp_name} ({webp_size / 1024:.1f} KB, saved {savings:.1f}%)")

                if delete_original:
                    service.files().delete(fileId=fid).execute()
                    log(f"[{i}/{total}] 🗑️  Deleted original.")

                success += 1
                job["stats"]["success"] = success
            except Exception as e:
                log(f"[{i}/{total}] ❌ Failed: {e}")
                failed += 1
                job["stats"]["failed"] = failed

        log(f"\n─────────────────────────────────")
        log(f"✅ Done — {success} compressed, {failed} failed.")
        job["status"] = "done"

    except Exception as e:
        log(f"💥 Fatal error: {e}")
        job["status"] = "error"
    finally:
        log_q.put(None)  # signal stream end


# ─── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
