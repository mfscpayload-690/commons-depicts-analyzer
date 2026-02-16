"""
Security Module — Commons Depicts Analyzer

Centralized security utilities:
- Input validation & sanitization
- CSRF token management
- Security headers middleware
- Error sanitization
- Logging configuration
"""

import logging
import re
import secrets
import hmac
from functools import wraps
from flask import request, jsonify, session, abort

# ============ Logging ============
# Configure secure logging — never log tokens or secrets
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("security")


# ============ Input Validation ============

# Strict patterns — whitelist approach
QID_PATTERN = re.compile(r"^Q\d{1,10}$")
FILE_TITLE_PATTERN = re.compile(
    r"^[A-Za-z0-9 _\-.,;:()\[\]{}!@#%&+=\u00C0-\u024F\u0400-\u04FF\u4E00-\u9FFF]+\.[a-zA-Z]{2,5}$"
)
MAX_FILE_TITLE_LENGTH = 255
MAX_CATEGORY_LENGTH = 255
CATEGORY_PATTERN = re.compile(r"^[A-Za-z0-9 _\-.,;:()\[\]{}!@#%&+=\u00C0-\u024F\u0400-\u04FF\u4E00-\u9FFF]+$")


def validate_qid(qid: str) -> str:
    """
    Validate a Wikidata Q-ID.

    Only allows format: Q followed by 1-10 digits (e.g., Q42, Q12345678).
    Raises ValueError on invalid input.
    """
    if not qid or not isinstance(qid, str):
        raise ValueError("QID is required and must be a string")

    qid = qid.strip().upper()

    if not QID_PATTERN.match(qid):
        raise ValueError("Invalid QID format: must match Q followed by 1-10 digits")

    return qid


def validate_file_title(title: str) -> str:
    """
    Validate a Wikimedia Commons file title.

    Whitelists safe characters, enforces max length.
    Raises ValueError on invalid input.
    """
    if not title or not isinstance(title, str):
        raise ValueError("File title is required and must be a string")

    title = title.strip()

    if len(title) > MAX_FILE_TITLE_LENGTH:
        raise ValueError(f"File title too long (max {MAX_FILE_TITLE_LENGTH} characters)")

    # Strip "File:" prefix for validation, add back later
    clean_title = title
    if clean_title.startswith("File:"):
        clean_title = clean_title[5:]

    if not clean_title:
        raise ValueError("File title cannot be empty")

    if not FILE_TITLE_PATTERN.match(clean_title):
        raise ValueError("File title contains invalid characters")

    # Block path traversal attempts
    if ".." in title or "/" in title or "\\" in title:
        logger.warning("Path traversal attempt blocked in file title")
        raise ValueError("File title contains invalid characters")

    return title


def validate_category(category: str) -> str:
    """
    Validate a Wikimedia Commons category name.

    Whitelists safe characters, enforces max length.
    Raises ValueError on invalid input.
    """
    if not category or not isinstance(category, str):
        raise ValueError("Category is required and must be a string")

    category = category.strip()

    if len(category) > MAX_CATEGORY_LENGTH:
        raise ValueError(f"Category name too long (max {MAX_CATEGORY_LENGTH} characters)")

    # Strip "Category:" prefix for validation
    clean_cat = category
    if clean_cat.startswith("Category:"):
        clean_cat = clean_cat[9:]

    if not clean_cat:
        raise ValueError("Category name cannot be empty")

    if not CATEGORY_PATTERN.match(clean_cat):
        raise ValueError("Category name contains invalid characters")

    if ".." in category or "\\" in category:
        logger.warning("Path traversal attempt blocked in category name")
        raise ValueError("Category name contains invalid characters")

    return category


# ============ CSRF Protection ============

CSRF_TOKEN_LENGTH = 64  # 256-bit tokens


def generate_csrf_token() -> str:
    """
    Generate a cryptographically secure CSRF token and store it in the session.
    Uses the double-submit cookie pattern with session binding.
    """
    token = secrets.token_hex(CSRF_TOKEN_LENGTH // 2)
    session["_csrf_token"] = token
    return token


def validate_csrf_token(token: str) -> bool:
    """
    Validate a CSRF token against the session-stored token.
    Uses constant-time comparison to prevent timing attacks.

    Returns True if valid, raises 403 Forbidden if invalid.
    """
    stored_token = session.get("_csrf_token")

    if not stored_token or not token:
        logger.warning("CSRF validation failed: missing token")
        abort(403, description="CSRF token missing")

    if not hmac.compare_digest(stored_token, token):
        logger.warning("CSRF validation failed: token mismatch")
        abort(403, description="CSRF token invalid")

    return True


def csrf_required(f):
    """Decorator to enforce CSRF token validation on state-changing endpoints."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("X-CSRF-Token", "")
        validate_csrf_token(token)
        return f(*args, **kwargs)
    return decorated


# ============ Security Headers ============

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "0",  # Disabled per modern best practice; CSP handles XSS
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "img-src 'self' https://*.wikimedia.org https://*.wikipedia.org data:; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
        "font-src 'self' https://cdnjs.cloudflare.com; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    ),
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()"
}


def add_security_headers(response):
    """
    Flask after_request handler to inject security headers on every response.
    """
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value

    # Cache control for authenticated responses
    if "access_token" in session:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        response.headers["Pragma"] = "no-cache"

    return response


# ============ Error Sanitization ============

def sanitize_error(exception: Exception, context: str = "operation") -> dict:
    """
    Sanitize an exception for client-facing error responses.

    Logs the full exception server-side for debugging,
    returns a generic message to the client (no stack traces, no internals).
    """
    logger.exception(f"Error in {context}: {type(exception).__name__}")

    return {
        "error": f"An internal error occurred during {context}. Please try again later.",
        "status": "error"
    }


# ============ Authentication Guard ============

def login_required(f):
    """Decorator to enforce authentication on protected endpoints."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "access_token" not in session:
            return jsonify({
                "error": "Authentication required. Please log in first.",
                "status": "unauthorized"
            }), 401

        # Check if token has expired
        token_expiry = session.get("token_expires_at")
        if token_expiry:
            import time
            if time.time() > token_expiry:
                # Clear expired session
                session.clear()
                return jsonify({
                    "error": "Session expired. Please log in again.",
                    "status": "session_expired"
                }), 401

        return f(*args, **kwargs)
    return decorated
