"""
Wikimedia Commons Depicts Analyzer - Main Application

Flask web server and CLI orchestrator.
Provides API endpoints for frontend and command-line analysis.

SECURITY: This module integrates server-side sessions, rate limiting,
CSRF protection, input validation, and security headers.
"""

import argparse
import json
import logging
import os
import secrets
import sys
import tempfile
import threading
import time
import uuid
from datetime import timedelta
from flask import Flask, request, jsonify, send_from_directory, redirect, session
from flask_cors import CORS
from flask_session import Session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from api import (fetch_category_files, check_depicts, resolve_labels,
                 fetch_category_suggestions, fetch_file_info, suggest_depicts)
from database import (init_db, insert_file, get_files_by_category,
                      get_statistics, clear_category, verify_category_saved, get_all_categories)
from config import (
    FLASK_SECRET_KEY, ALLOWED_ORIGINS,
    SESSION_LIFETIME_MINUTES, SESSION_COOKIE_SECURE,
    SESSION_COOKIE_HTTPONLY, SESSION_COOKIE_SAMESITE,
    RATE_LIMIT_DEFAULT, RATE_LIMIT_AUTH, RATE_LIMIT_CALLBACK, RATE_LIMIT_API_WRITE,
    HOST, PORT, DEBUG
)
from oauth import (is_oauth_configured, get_authorize_url, exchange_code_for_token,
                   get_user_profile, add_depicts_statement, revoke_token)
from security import (
    validate_qid, validate_file_title, add_security_headers,
    generate_csrf_token, csrf_required, login_required
)

logger = logging.getLogger("app")

# ============ Initialize Flask App ============
app = Flask(__name__, static_folder="../frontend")
app.secret_key = FLASK_SECRET_KEY

# --- Server-Side Session Configuration ---
# Sessions stored on filesystem (NOT in browser cookies)
_session_dir = os.path.join(tempfile.gettempdir(), "cda_sessions")
os.makedirs(_session_dir, exist_ok=True)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = _session_dir
app.config["SESSION_PERMANENT"] = True
app.config["SESSION_USE_SIGNER"] = True  # Sign session ID cookie
app.config["SESSION_KEY_PREFIX"] = "cda_"  # Namespace sessions
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=SESSION_LIFETIME_MINUTES)
app.config["SESSION_COOKIE_SECURE"] = SESSION_COOKIE_SECURE
app.config["SESSION_COOKIE_HTTPONLY"] = SESSION_COOKIE_HTTPONLY
app.config["SESSION_COOKIE_SAMESITE"] = SESSION_COOKIE_SAMESITE
Session(app)

# --- CORS: Locked to Whitelisted Origins ---
CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=True)

# --- Rate Limiting ---
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[RATE_LIMIT_DEFAULT],
    storage_uri="memory://"
)

# --- Security Headers on Every Response ---
app.after_request(add_security_headers)


# Initialize database on startup
init_db()


def analyze_category(category_name: str, progress_callback=None, progress_hook=None, language: str = "en") -> dict:
    """
    Run full analysis pipeline for a category.

    Args:
        category_name: Commons category name
        progress_callback: Optional callback for progress updates
        language: Language code for depicts labels (default: 'en')

    Returns:
        Analysis results dict
    """
    # Normalize category name
    if not category_name.startswith("Category:"):
        category_name = f"Category:{category_name}"

    # Clear previous results for this category
    clear_category(category_name)

    # Step 1: Fetch all files
    if progress_callback:
        progress_callback("Fetching files from category...")

    if progress_hook:
        progress_hook({
            "phase": "fetching",
            "message": "Fetching files from category",
            "processed": 0,
            "total": None
        })

    try:
        files = fetch_category_files(category_name)
    except ValueError as e:
        # Category validation error (doesn't exist)
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Failed to fetch category: {str(e)}"}

    if not files:
        return {"error": "No files found in category"}

    # Step 2: Check each file for depicts
    total = len(files)

    if progress_hook:
        progress_hook({
            "phase": "checking",
            "message": "Checking depicts statements",
            "processed": 0,
            "total": total
        })

    for i, file_title in enumerate(files):
        if progress_callback:
            progress_callback(f"Checking file {i + 1}/{total}: {file_title}")

        if progress_hook:
            progress_hook({
                "phase": "checking",
                "message": "Checking depicts statements",
                "processed": i + 1,
                "total": total
            })

        try:
            has_depicts, qids = check_depicts(file_title)

            # Resolve labels if there are QIDs (with language parameter)
            depicts_str = None
            if qids:
                labels = resolve_labels(qids, language)  # Pass language here
                label_list = [labels.get(qid, qid) for qid in qids]
                depicts_str = ", ".join(label_list)

            # Store in database
            insert_file(file_title, category_name, depicts_str, has_depicts)

        except Exception as e:
            # Log error but continue with other files
            print(f"Error processing {file_title}: {e}", file=sys.stderr)
            insert_file(file_title, category_name, None, False)

    # Step 3: Get results
    if progress_hook:
        progress_hook({
            "phase": "finalizing",
            "message": "Finalizing results",
            "processed": total,
            "total": total
        })
    stats = get_statistics(category_name)
    files_data = get_files_by_category(category_name)

    return {
        "category": category_name,
        "statistics": stats,
        "files": files_data
    }


# ============ Background Analysis Jobs ============

class _AnalysisCancelled(Exception):
    """Raised when a job is cancelled mid-flight."""


analysis_jobs = {}
analysis_lock = threading.Lock()


def _set_job(job_id: str, **updates) -> None:
    with analysis_lock:
        job = analysis_jobs.get(job_id, {})
        job.update(updates)
        job["updated_at"] = time.time()
        analysis_jobs[job_id] = job


def _compute_percent(job: dict) -> int:
    total = job.get("total")
    processed = job.get("processed", 0)
    phase = job.get("phase")

    if total:
        return min(100, int((processed / total) * 100))
    if phase == "fetching":
        return 5
    if phase == "finalizing":
        return 95
    return 0


def is_job_cancelled(job_id: str) -> bool:
    with analysis_lock:
        job = analysis_jobs.get(job_id, {})
        return job.get("status") == "cancelled"


def cancel_job(job_id: str) -> bool:
    with analysis_lock:
        job = analysis_jobs.get(job_id)
        if not job:
            return False
        if job.get("status") in ("done", "error", "cancelled"):
            return False
        job["status"] = "cancelled"
        job["phase"] = "cancelled"
        job["message"] = "Cancelled by user"
        job["updated_at"] = time.time()
        return True


def _run_analysis_job(job_id: str, category: str, language: str = "en") -> None:
    def hook(info: dict) -> None:
        if is_job_cancelled(job_id):
            raise _AnalysisCancelled()
        _set_job(job_id, **info)

    _set_job(job_id, status="running", phase="fetching", message="Starting analysis")

    try:
        result = analyze_category(category, progress_hook=hook, language=language)
    except _AnalysisCancelled:
        return

    if is_job_cancelled(job_id):
        return

    if "error" in result:
        _set_job(job_id, status="error", error=result["error"], phase="error")
        return

    _set_job(job_id, status="done", phase="done", processed=job_total(job_id), message="Completed")


def job_total(job_id: str) -> int:
    with analysis_lock:
        job = analysis_jobs.get(job_id, {})
        return int(job.get("total") or 0)


def start_analysis_job(category: str, language: str = "en") -> str:
    job_id = uuid.uuid4().hex
    _set_job(
        job_id,
        status="queued",
        phase="queued",
        category=category,
        language=language,
        processed=0,
        total=None,
        message="Queued"
    )

    thread = threading.Thread(target=_run_analysis_job, args=(job_id, category, language), daemon=True)
    thread.start()
    return job_id


# ============ API Endpoints ============

@app.route("/")
def serve_index():
    """Serve the frontend index.html."""
    return send_from_directory(app.static_folder, "index.html")


@app.route("/<path:filename>")
def serve_static(filename):
    """Serve static frontend files."""
    return send_from_directory(app.static_folder, filename)


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """
    Analyze a Commons category.

    Request body: {"category": "Category:Example"}
    Query params: ?language=en (optional, default: 'en')
    Returns: Analysis results with statistics and file lists
    """
    data = request.get_json()

    if not data or "category" not in data:
        return jsonify({"error": "Missing 'category' in request body"}), 400

    category = data["category"].strip()
    if not category:
        return jsonify({"error": "Category name cannot be empty"}), 400

    async_mode = request.args.get("async") == "1"
    language = request.args.get("language", "en")  # Get language parameter

    if async_mode:
        job_id = start_analysis_job(category, language)
        return jsonify({"job_id": job_id, "status": "started"}), 202

    result = analyze_category(category, language=language)

    if "error" in result:
        return jsonify(result), 400

    return jsonify(result)


@app.route("/api/results/<path:category>", methods=["GET"])
def api_results(category):
    """
    Get stored results for a category.

    Returns cached analysis results from database.
    """
    # Normalize category name
    if not category.startswith("Category:"):
        category = f"Category:{category}"

    stats = get_statistics(category)

    if stats["total"] == 0:
        return jsonify({"error": "No results found for this category"}), 404

    files_data = get_files_by_category(category)

    return jsonify({
        "category": category,
        "statistics": stats,
        "files": files_data
    })


@app.route("/api/progress/<job_id>", methods=["GET"])
def api_progress(job_id):
    """
    Get progress for a background analysis job.

    Returns status, phase, processed/total, and percent.
    """
    with analysis_lock:
        job = analysis_jobs.get(job_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404

    payload = {
        "job_id": job_id,
        "status": job.get("status"),
        "phase": job.get("phase"),
        "category": job.get("category"),
        "processed": job.get("processed", 0),
        "total": job.get("total"),
        "message": job.get("message"),
        "error": job.get("error"),
        "percent": _compute_percent(job)
    }

    return jsonify(payload)


@app.route("/api/cancel/<job_id>", methods=["POST"])
def api_cancel(job_id):
    """Cancel a running analysis job."""
    ok = cancel_job(job_id)
    if not ok:
        return jsonify({"error": "Job not found or already finished"}), 404
    return jsonify({"status": "cancelled", "job_id": job_id})


@app.route("/api/suggest", methods=["GET"])
def api_suggest():
    """
    Suggest Commons categories by prefix.

    Query params: ?query=partial
    Returns: {"suggestions": ["Cats", "Cathedrals", ...]}
    """
    query = request.args.get("query", "").strip()
    if not query:
        return jsonify({"suggestions": []})

    try:
        suggestions = fetch_category_suggestions(query)
        return jsonify({"suggestions": suggestions})
    except Exception as e:
        return jsonify({"error": f"Failed to fetch suggestions: {str(e)}"}), 400


@app.route("/api/verify/<path:category>", methods=["GET"])
def api_verify(category):
    """
    Verify that a category's data was saved to the database.

    Returns verification info including record counts, timestamps, and sample data.
    """
    result = verify_category_saved(category)

    if not result.get("verified"):
        return jsonify(result), 404

    return jsonify(result)


@app.route("/api/history", methods=["GET"])
def api_history():
    """
    Get a list of all previously analyzed categories.

    Returns category names, file counts, and last analyzed timestamps.
    """
    categories = get_all_categories()
    return jsonify({
        "categories": categories,
        "total": len(categories)
    })


@app.route("/api/category/<path:category>", methods=["DELETE"])
def api_delete_category(category):
    """
    Delete a category and all its files from the database.

    Args:
        category: Category name to delete
    """
    # Normalize category name
    if not category.startswith("Category:"):
        category = f"Category:{category}"

    # Check if category exists
    stats = get_statistics(category)
    if stats["total"] == 0:
        return jsonify({"error": "Category not found in database"}), 404

    # Delete the category
    clear_category(category)

    return jsonify({
        "success": True,
        "message": f"Deleted {stats['total']} files from {category}",
        "deleted_files": stats["total"]
    })


@app.route("/api/export/<path:category>", methods=["GET"])
def api_export(category):
    """
    Export category analysis results as CSV or JSON.

    Query params: ?format=csv|json (default: csv)
    """
    from flask import Response
    import csv
    from io import StringIO

    # Normalize category name
    if not category.startswith("Category:"):
        category = f"Category:{category}"

    # Get data
    stats = get_statistics(category)
    if stats["total"] == 0:
        return jsonify({"error": "No results found for this category"}), 404

    files_data = get_files_by_category(category)
    export_format = request.args.get("format", "csv").lower()

    if export_format == "json":
        # JSON export
        result = {
            "category": category,
            "statistics": stats,
            "files": files_data,
            "exported_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        }
        response = Response(
            json.dumps(result, indent=2),
            mimetype="application/json",
            headers={
                "Content-Disposition": (
                    "attachment; filename="
                    + category.replace('Category:', '').replace(' ', '_')
                    + "_export.json"
                )
            }
        )
        return response

    else:
        # CSV export
        output = StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(["File Name", "Has Depicts", "Depicts Labels"])

        # Data rows
        for file in files_data:
            writer.writerow([
                file["file_name"],
                "Yes" if file["has_depicts"] else "No",
                file.get("depicts", "")
            ])

        csv_data = output.getvalue()
        output.close()

        response = Response(
            csv_data,
            mimetype="text/csv",
            headers={
                "Content-Disposition": (
                    "attachment; filename="
                    + category.replace('Category:', '').replace(' ', '_')
                    + "_export.csv"
                )
            }
        )
        return response


@app.route("/api/fileinfo/<path:file_title>", methods=["GET"])
def api_fileinfo(file_title):
    """
    Get detailed file information from Wikimedia Commons.

    Returns thumbnail URL, dimensions, description, license, etc.
    """
    try:
        if not file_title.startswith("File:"):
            file_title = f"File:{file_title}"

        info = fetch_file_info(file_title)

        if "error" in info:
            return jsonify({"error": info["error"]}), 404

        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/suggests/<path:file_title>", methods=["GET"])
def api_suggests(file_title):
    """
    Get Wikidata depicts suggestions based on file title keywords.

    Returns a list of suggested Q-items with labels and descriptions.
    """
    try:
        if not file_title.startswith("File:"):
            file_title = f"File:{file_title}"

        limit = request.args.get("limit", 5, type=int)
        suggestions = suggest_depicts(file_title, limit=min(limit, 10))

        return jsonify({"suggestions": suggestions, "file": file_title})
    except Exception as e:
        return jsonify({"error": str(e), "suggestions": []}), 500


# ============ Auth Endpoints (Security-Hardened) ============


@app.route("/auth/login")
@limiter.limit(RATE_LIMIT_AUTH)
def auth_login():
    """Redirect user to Wikimedia OAuth authorization."""
    if not is_oauth_configured():
        return jsonify({"error": "OAuth is not configured."}), 503

    # Generate cryptographically secure state for CSRF protection
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    return redirect(get_authorize_url(state))


@app.route("/auth/callback")
@limiter.limit(RATE_LIMIT_CALLBACK)
def auth_callback():
    """Handle OAuth callback after user authorizes."""
    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")

    # User denied authorization
    if error:
        logger.info(f"OAuth authorization denied by user: {error}")
        return redirect("/?auth_error=denied")

    if not code:
        logger.warning("OAuth callback missing code parameter")
        return redirect("/?auth_error=no_code")

    # Verify state matches (CSRF protection)
    stored_state = session.get("oauth_state")
    if not stored_state or not state:
        logger.warning("OAuth state parameter missing")
        return redirect("/?auth_error=state_mismatch")

    # Constant-time comparison to prevent timing attacks
    import hmac
    if not hmac.compare_digest(state, stored_state):
        logger.warning("OAuth state mismatch — possible CSRF attack")
        return redirect("/?auth_error=state_mismatch")

    # Exchange code for token
    success, token_data = exchange_code_for_token(code)
    if not success:
        logger.error("OAuth token exchange failed")
        return redirect("/?auth_error=token_failed")

    # SESSION REGENERATION: Prevent session fixation attacks
    # Clear old session data, start fresh
    session.clear()

    access_token = token_data.get("access_token")
    session["access_token"] = access_token

    # Track token expiry
    expires_in = token_data.get("expires_in")
    if expires_in:
        session["token_expires_at"] = time.time() + int(expires_in)
    else:
        # Default: 1 hour expiry
        session["token_expires_at"] = time.time() + 3600

    # Get user profile
    profile_success, profile = get_user_profile(access_token)
    if profile_success:
        session["username"] = profile.get("username", "Unknown")
        session["user_id"] = profile.get("sub", "")

    # Generate CSRF token for subsequent write operations
    generate_csrf_token()

    logger.info(f"User logged in: {session.get('username', 'Unknown')}")
    return redirect("/?auth_success=true")


@app.route("/auth/logout")
def auth_logout():
    """Log user out by clearing session and revoking token."""
    # Attempt token revocation on Wikimedia side (best-effort)
    access_token = session.get("access_token")
    if access_token:
        revoke_token(access_token)
        logger.info(f"User logged out: {session.get('username', 'Unknown')}")

    # Clear ALL session data (nuclear option — safest)
    session.clear()
    return redirect("/")


@app.route("/auth/status")
def auth_status():
    """Check current auth status."""
    logged_in = "access_token" in session

    # Auto-expire if token is past its lifetime
    if logged_in:
        token_expiry = session.get("token_expires_at")
        if token_expiry and time.time() > token_expiry:
            session.clear()
            logged_in = False

    response_data = {
        "logged_in": logged_in,
        "username": session.get("username", "") if logged_in else "",
        "oauth_configured": is_oauth_configured()
    }

    # Include CSRF token for authenticated users (needed for write operations)
    if logged_in:
        response_data["csrf_token"] = session.get("_csrf_token", generate_csrf_token())

    return jsonify(response_data)


@app.route("/api/add-depicts", methods=["POST"])
@limiter.limit(RATE_LIMIT_API_WRITE)
@login_required
@csrf_required
def api_add_depicts():
    """
    Add a depicts (P180) statement to a Commons file.

    Security:
    - Requires valid authentication (login_required)
    - Requires valid CSRF token (csrf_required)
    - Rate limited to prevent abuse
    - Input validated before use
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    # Validate and sanitize inputs
    try:
        file_title = validate_file_title(data.get("file_title", ""))
        qid = validate_qid(data.get("qid", ""))
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400

    success, message = add_depicts_statement(session["access_token"], file_title, qid)

    if success:
        logger.info(f"Depicts {qid} added to {file_title} by {session.get('username')}")
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "error": message}), 500


# ============ CLI Mode ============

def cli_main():
    """Command-line interface for analysis."""
    parser = argparse.ArgumentParser(
        description="Analyze Wikimedia Commons categories for depicts (P180) metadata"
    )
    parser.add_argument(
        "--category", "-c",
        required=True,
        help="Commons category to analyze (e.g., 'Category:Example')"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()

    def progress(msg):
        print(f"  {msg}", file=sys.stderr)

    print(f"\n[*] Analyzing: {args.category}\n", file=sys.stderr)

    result = analyze_category(args.category, progress_callback=progress)

    if "error" in result:
        print(f"\n[ERROR] {result['error']}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        stats = result["statistics"]
        print(f"\n{'='*50}", file=sys.stderr)
        print(f"[STATS] Results for {result['category']}", file=sys.stderr)
        print(f"{'='*50}", file=sys.stderr)
        print(f"  Total files:      {stats['total']}", file=sys.stderr)
        print(f"  With depicts:     {stats['with_depicts']} [OK]", file=sys.stderr)
        print(f"  Without depicts:  {stats['without_depicts']} [X]", file=sys.stderr)

        if stats["total"] > 0:
            coverage = (stats["with_depicts"] / stats["total"]) * 100
            print(f"  Coverage:         {coverage:.1f}%", file=sys.stderr)

        print("\n[FILES] Without depicts:", file=sys.stderr)
        for f in result["files"]:
            if not f["has_depicts"]:
                print(f"    - {f['file_name']}", file=sys.stderr)


if __name__ == "__main__":
    # Check if running in CLI mode
    if len(sys.argv) > 1 and sys.argv[1] in ["--category", "-c", "--help", "-h"]:
        cli_main()
    else:
        # Start web server
        print("Starting Wikimedia Commons Depicts Analyzer...")
        print("Open http://localhost:5000 in your browser")
        app.run(host=HOST, port=PORT, debug=DEBUG)
