"""
Configuration Module — Commons Depicts Analyzer

Centralizes application settings and OAuth credentials.
Uses environment variables with STRICT enforcement in production.
Development mode uses secure auto-generated defaults.

SECURITY NOTES:
- NEVER commit secrets to version control
- In production, ALL secrets MUST come from environment variables
- The app will crash on startup if production secrets are missing
"""

import os
import sys
from pathlib import Path

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    # Find .env file in project root (parent of backend/)
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✓ Loaded environment variables from {env_path}")
except ImportError:
    # python-dotenv not installed, env vars must be set manually
    pass

# ============ Environment ============
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development").lower()
IS_PRODUCTION = ENVIRONMENT == "production"

# ============ OAuth 2.0 Settings ============
# Register an OAuth consumer at: https://meta.wikimedia.org/wiki/Special:OAuthConsumerRegistration
# Required env vars in production: OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET, OAUTH_CALLBACK_URL

OAUTH_CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID", "")
OAUTH_CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET", "")
OAUTH_CALLBACK_URL = os.environ.get(
    "OAUTH_CALLBACK_URL",
    "http://localhost:5000/auth/callback" if not IS_PRODUCTION else ""
)

# Wikimedia OAuth endpoints (these are public, not sensitive)
OAUTH_AUTHORIZE_URL = "https://meta.wikimedia.org/w/rest.php/oauth2/authorize"
OAUTH_TOKEN_URL = "https://meta.wikimedia.org/w/rest.php/oauth2/access_token"
OAUTH_PROFILE_URL = "https://meta.wikimedia.org/w/rest.php/oauth2/resource/profile"

# ============ Flask Secret Key ============
# CRITICAL: This key signs session cookies. Must be strong and secret.
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "")

if not FLASK_SECRET_KEY:
    if IS_PRODUCTION:
        print("FATAL: FLASK_SECRET_KEY environment variable is required in production!", file=sys.stderr)
        print("Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\"", file=sys.stderr)
        sys.exit(1)
    else:
        # Auto-generate a secure key for development (changes each restart)
        FLASK_SECRET_KEY = os.urandom(32).hex()

# ============ Session Configuration ============
SESSION_LIFETIME_MINUTES = int(os.environ.get("SESSION_LIFETIME_MINUTES", "60"))
SESSION_COOKIE_SECURE = IS_PRODUCTION  # HTTPS-only cookies in production
SESSION_COOKIE_HTTPONLY = True          # JavaScript cannot access session cookie
SESSION_COOKIE_SAMESITE = "Lax"        # Prevent CSRF via cross-site requests

# ============ CORS Settings ============
# Whitelist of allowed origins for cross-origin requests
# In development: allow localhost variations
# In production: set ALLOWED_ORIGINS env var (comma-separated)
_default_origins = [
    "http://localhost:5000",
    "http://127.0.0.1:5000",
    "http://localhost:3000",
]
_env_origins = os.environ.get("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = (
    [o.strip() for o in _env_origins.split(",") if o.strip()]
    if _env_origins
    else _default_origins if not IS_PRODUCTION else []
)

if IS_PRODUCTION and not ALLOWED_ORIGINS:
    print("WARNING: No ALLOWED_ORIGINS configured in production. CORS will block all cross-origin requests.", file=sys.stderr)

# ============ Rate Limiting ============
RATE_LIMIT_DEFAULT = os.environ.get("RATE_LIMIT_DEFAULT", "200 per hour")
RATE_LIMIT_AUTH = os.environ.get("RATE_LIMIT_AUTH", "5 per minute")
RATE_LIMIT_CALLBACK = os.environ.get("RATE_LIMIT_CALLBACK", "10 per minute")
RATE_LIMIT_API_WRITE = os.environ.get("RATE_LIMIT_API_WRITE", "30 per minute")

# ============ Application Settings ============
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", 5000))
DEBUG = not IS_PRODUCTION and os.environ.get("DEBUG", "true").lower() == "true"
