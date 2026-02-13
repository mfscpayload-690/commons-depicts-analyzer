"""
Configuration Module

Centralizes application settings and OAuth credentials.
Uses environment variables with sensible defaults for development.
"""

import os

# ============ OAuth 2.0 Settings ============
# Register an OAuth consumer at: https://meta.wikimedia.org/wiki/Special:OAuthConsumerRegistration
# Set these environment variables in production:
#   OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET, OAUTH_CALLBACK_URL

OAUTH_CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID", "")
OAUTH_CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET", "")
OAUTH_CALLBACK_URL = os.environ.get("OAUTH_CALLBACK_URL", "http://localhost:5000/auth/callback")

# Wikimedia OAuth endpoints
OAUTH_AUTHORIZE_URL = "https://meta.wikimedia.org/w/rest.php/oauth2/authorize"
OAUTH_TOKEN_URL = "https://meta.wikimedia.org/w/rest.php/oauth2/access_token"
OAUTH_PROFILE_URL = "https://meta.wikimedia.org/w/rest.php/oauth2/resource/profile"

# Flask secret key for session management
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "commons-depicts-dev-key-change-in-production")

# ============ Application Settings ============
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 5000))
DEBUG = os.environ.get("DEBUG", "true").lower() == "true"
