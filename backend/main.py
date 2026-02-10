"""
Wikimedia Commons Depicts Analyzer - Main Application

Flask web server and CLI orchestrator.
Provides API endpoints for frontend and command-line analysis.
"""

import argparse
import json
import os
import sys
import threading
import time
import uuid
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from api import fetch_category_files, check_depicts, resolve_labels, fetch_category_suggestions
from database import (init_db, insert_file, get_files_by_category, 
                      get_statistics, clear_category, verify_category_saved, get_all_categories)

# Initialize Flask app
app = Flask(__name__, static_folder="../frontend")
CORS(app)

# Initialize database on startup
init_db()


def analyze_category(category_name: str, progress_callback=None, progress_hook=None) -> dict:
    """
    Run full analysis pipeline for a category.
    
    Args:
        category_name: Commons category name
        progress_callback: Optional callback for progress updates
    
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
            
            # Resolve labels if there are QIDs
            depicts_str = None
            if qids:
                labels = resolve_labels(qids)
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


def _run_analysis_job(job_id: str, category: str) -> None:
    def hook(info: dict) -> None:
        if is_job_cancelled(job_id):
            raise _AnalysisCancelled()
        _set_job(job_id, **info)

    _set_job(job_id, status="running", phase="fetching", message="Starting analysis")

    try:
        result = analyze_category(category, progress_hook=hook)
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


def start_analysis_job(category: str) -> str:
    job_id = uuid.uuid4().hex
    _set_job(
        job_id,
        status="queued",
        phase="queued",
        category=category,
        processed=0,
        total=None,
        message="Queued"
    )

    thread = threading.Thread(target=_run_analysis_job, args=(job_id, category), daemon=True)
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
    Returns: Analysis results with statistics and file lists
    """
    data = request.get_json()
    
    if not data or "category" not in data:
        return jsonify({"error": "Missing 'category' in request body"}), 400
    
    category = data["category"].strip()
    if not category:
        return jsonify({"error": "Category name cannot be empty"}), 400
    
    async_mode = request.args.get("async") == "1"

    if async_mode:
        job_id = start_analysis_job(category)
        return jsonify({"job_id": job_id, "status": "started"}), 202

    result = analyze_category(category)

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
        
        print(f"\n[FILES] Without depicts:", file=sys.stderr)
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
        app.run(host="0.0.0.0", port=5000, debug=True)
