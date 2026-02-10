"""
Wikimedia Commons Depicts Analyzer - Main Application

Flask web server and CLI orchestrator.
Provides API endpoints for frontend and command-line analysis.
"""

import argparse
import json
import os
import sys
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from api import fetch_category_files, check_depicts, resolve_labels
from database import init_db, insert_file, get_files_by_category, get_statistics, clear_category, get_history_stats

# Initialize Flask app
app = Flask(__name__, static_folder="../frontend")
CORS(app)

# Initialize database on startup
init_db()


def analyze_category(category_name: str, progress_callback=None) -> dict:
    """
    Run full analysis pipeline for a category.
    """
    # Normalize category name
    category_name = category_name.strip()
    if not category_name.startswith("Category:"):
        category_name = f"Category:{category_name}"
    
    # Clear previous results for this category
    clear_category(category_name)
    
    # Step 1: Fetch all files
    if progress_callback:
        progress_callback("Fetching files from category...")
    
    try:
        files = fetch_category_files(category_name)
    except Exception as e:
        return {"error": f"Failed to fetch category: {str(e)}"}
    
    if not files:
        return {"error": "No files found in category"}
    
    # Step 2: Check each file for depicts
    total = len(files)
    
    for i, file_title in enumerate(files):
        if progress_callback and i % 10 == 0:
            progress_callback(f"Checking file {i + 1}/{total}...")
        
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
    stats = get_statistics(category_name)
    files_data = get_files_by_category(category_name)
    
    return {
        "category": category_name,
        "statistics": stats,
        "files": files_data
    }


# ============ API Endpoints ============

@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/<path:filename>")
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    data = request.get_json()
    if not data or "category" not in data:
        return jsonify({"error": "Missing 'category' in request body"}), 400
    
    category = data["category"].strip()
    if not category:
        return jsonify({"error": "Category name cannot be empty"}), 400
    
    result = analyze_category(category)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@app.route("/api/results/<path:category>", methods=["GET"])
def api_results(category):
    if not category.startswith("Category:"):
        category = f"Category:{category}"
    
    stats = get_statistics(category)
    if stats["total"] == 0:
        return jsonify({"error": "No results found"}), 404
    
    files_data = get_files_by_category(category)
    return jsonify({
        "category": category,
        "statistics": stats,
        "files": files_data
    })


@app.route("/api/history", methods=["GET"])
def api_history():
    """Get list of all analyzed categories with stats."""
    history = get_history_stats()
    return jsonify(history)


@app.route("/api/delete", methods=["POST"])
def api_delete():
    """Delete a category from history."""
    data = request.get_json()
    if not data or "category" not in data:
        return jsonify({"error": "Missing 'category'"}), 400
    
    clear_category(data["category"])
    return jsonify({"success": True})


@app.route("/api/autocomplete", methods=["GET"])
def api_autocomplete():
    """Proxy for Commons Opensearch API."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])
    
    try:
        # Action=opensearch, namespace 14 (Category)
        url = "https://commons.wikimedia.org/w/api.php"
        params = {
            "action": "opensearch",
            "format": "json",
            "namespace": "14",
            "limit": "8",
            "search": query
        }
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        
        # Opensearch returns [query, [names], [descriptions], [links]]
        # We just want the names (index 1)
        suggestions = data[1]
        
        # Clean up output: remove "Category:" prefix if user query didn't have it, 
        # or keep it consistent. Let's return clean names.
        clean_suggestions = []
        for s in suggestions:
            clean_suggestions.append(s.replace("Category:", ""))
            
        return jsonify(clean_suggestions)
        
    except Exception as e:
        print(f"Autocomplete error: {e}", file=sys.stderr)
        return jsonify([])


# ============ CLI Mode ============

def cli_main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", "-c", required=True)
    parser.add_argument("--json", "-j", action="store_true")
    args = parser.parse_args()
    
    def progress(msg):
        print(f"  {msg}", file=sys.stderr)
    
    print(f"\n📂 Analyzing: {args.category}\n", file=sys.stderr)
    result = analyze_category(args.category, progress_callback=progress)
    
    if "error" in result:
        print(f"\n❌ Error: {result['error']}", file=sys.stderr)
        sys.exit(1)
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        stats = result["statistics"]
        print(f"\n{'='*50}", file=sys.stderr)
        print(f"📊 Results for {result['category']}", file=sys.stderr)
        print(f"{'='*50}", file=sys.stderr)
        print(f"  Total files:      {stats['total']}", file=sys.stderr)
        print(f"  With depicts:     {stats['with_depicts']} ✓", file=sys.stderr)
        print(f"  Without depicts:  {stats['without_depicts']} ✗", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ["--category", "-c", "--help", "-h"]:
        cli_main()
    else:
        print("🚀 Server at http://localhost:5000")
        app.run(host="0.0.0.0", port=5000, debug=True)
