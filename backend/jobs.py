import io
import queue
import threading
import time
import uuid
from pathlib import Path
from flask import Blueprint, jsonify, Response
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from PIL import Image

from .utils import (
    IMAGE_MIME_TYPES,
    load_config,
    get_drive_service,
    auth_required,
)

jobs_bp = Blueprint("jobs", __name__)

# ─── In-memory job store ────────────────────────────────────────────────────────
jobs: dict[str, dict] = {}  # job_id -> { status, log_queue, stats, created_at }

@jobs_bp.route("/api/jobs", methods=["POST"])
@auth_required
def start_job():
    config = load_config()
    folder_id = config.get("folder_id", "").strip()
    if not folder_id:
        return jsonify({"error": "No folder ID configured"}), 400

    service = get_drive_service()
    if not service:
        return jsonify({"error": "Not authenticated with Google Drive"}), 401

    from flask import session
    user_email = session.get("user_email", "")

    job_id = str(uuid.uuid4())[:8]
    log_q = queue.Queue()
    jobs[job_id] = {
        "id": job_id,
        "user_email": user_email,
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

@jobs_bp.route("/api/jobs/<job_id>")
@auth_required
def job_status(job_id):
    from flask import session
    job = jobs.get(job_id)
    if not job or job.get("user_email") != session.get("user_email"):
        return jsonify({"error": "Job not found"}), 404
    return jsonify({
        "id": job["id"],
        "status": job["status"],
        "stats": job["stats"],
    })

@jobs_bp.route("/api/jobs")
@auth_required
def list_jobs():
    from flask import session
    user_email = session.get("user_email", "")
    result = []
    user_jobs = [j for j in jobs.values() if j.get("user_email") == user_email]
    sorted_jobs = sorted(user_jobs, key=lambda j: j["created_at"], reverse=True)[:20]
    for job in sorted_jobs:
        result.append({
            "id": job["id"],
            "status": job["status"],
            "stats": job["stats"],
            "created_at": job["created_at"],
        })
    return jsonify(result)

@jobs_bp.route("/api/jobs/<job_id>/stream")
@auth_required
def job_stream(job_id):
    """Server-Sent Events stream for real-time log output."""
    from flask import session
    job = jobs.get(job_id)
    if not job or job.get("user_email") != session.get("user_email"):
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

# ─── Compression Engine ─────────────────────────────────────────────────────────

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

        if max_width: max_width = int(max_width)
        if max_height: max_height = int(max_height)

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
                req = service.files().get_media(fileId=fid)
                buf = io.BytesIO()
                dl = MediaIoBaseDownload(buf, req)
                done = False
                while not done:
                    _, done = dl.next_chunk()
                buf.seek(0)
                raw = buf.read()

                log(f"[{i}/{total}] ⚙️  Converting to WebP (q={quality})...")
                webp = compress_image(raw, quality=quality,
                                      max_width=max_width, max_height=max_height)
                webp_size = len(webp)
                savings = (1 - webp_size / orig_size) * 100 if orig_size > 0 else 0

                media = MediaIoBaseUpload(io.BytesIO(webp), mimetype="image/webp", resumable=True)
                service.files().create(
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
        log_q.put(None)
