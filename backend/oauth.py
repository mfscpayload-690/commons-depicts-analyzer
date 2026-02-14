"""
OAuth 2.0 Module — Commons Depicts Analyzer

Handles the OAuth 2.0 authorization code flow with Wikimedia.
Provides helper functions for:
- Generating authorization URLs
- Exchanging codes for tokens
- Making authenticated API calls
- Adding depicts statements to Commons

SECURITY NOTES:
- All tokens are stored server-side (never exposed to browser JS)
- Error messages are sanitized before returning to clients
- Token exchange uses HTTPS with strict timeouts
- CSRF protection via state parameter
"""

import json
import logging
from urllib.parse import quote
import requests
from typing import Dict, Any, Tuple
from config import (
    OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET, OAUTH_CALLBACK_URL,
    OAUTH_AUTHORIZE_URL, OAUTH_TOKEN_URL, OAUTH_PROFILE_URL
)

logger = logging.getLogger("oauth")

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "CommonsDepictsAnalyzer/1.0 (+https://github.com/mfscpayload-690/commons-depicts-analyzer)"

# Strict HTTP timeouts (seconds)
TOKEN_EXCHANGE_TIMEOUT = 15
PROFILE_FETCH_TIMEOUT = 10
API_REQUEST_TIMEOUT = 20

# Maximum retries for API calls
MAX_RETRIES = 2


def is_oauth_configured() -> bool:
    """Check if OAuth credentials are configured."""
    return bool(OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET)


def get_authorize_url(state: str) -> str:
    """
    Generate the OAuth authorization URL.

    Args:
        state: Cryptographically random state string for CSRF protection

    Returns:
        Authorization URL to redirect the user to
    """
    params = {
        "response_type": "code",
        "client_id": OAUTH_CLIENT_ID,
        "redirect_uri": OAUTH_CALLBACK_URL,
        "state": state
    }
    query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    return f"{OAUTH_AUTHORIZE_URL}?{query}"


def exchange_code_for_token(code: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Exchange an authorization code for an access token.

    Args:
        code: Authorization code from the callback

    Returns:
        Tuple of (success, token_data or error_data)
        token_data includes: access_token, token_type, expires_in

    Security:
        - Uses HTTPS POST (never GET for token exchange)
        - Strict timeout prevents hanging connections
        - Error details are logged server-side, not returned to client
    """
    try:
        response = requests.post(
            OAUTH_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": OAUTH_CLIENT_ID,
                "client_secret": OAUTH_CLIENT_SECRET,
                "redirect_uri": OAUTH_CALLBACK_URL
            },
            timeout=TOKEN_EXCHANGE_TIMEOUT,
            verify=True  # Enforce TLS certificate verification
        )

        if response.status_code == 200:
            token_data = response.json()
            # Validate required fields exist
            if "access_token" not in token_data:
                logger.error("Token response missing access_token field")
                return False, {"error": "Invalid token response from authorization server"}
            return True, token_data
        else:
            logger.error(f"Token exchange failed with status {response.status_code}")
            return False, {"error": "Token exchange failed"}
    except requests.exceptions.Timeout:
        logger.error("Token exchange timed out")
        return False, {"error": "Authorization server did not respond in time"}
    except requests.exceptions.SSLError:
        logger.error("SSL verification failed during token exchange")
        return False, {"error": "Secure connection could not be established"}
    except Exception:
        logger.exception("Unexpected error during token exchange")
        return False, {"error": "Token exchange failed due to an internal error"}


def get_user_profile(access_token: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Get the authenticated user's profile from Wikimedia.

    Args:
        access_token: OAuth access token

    Returns:
        Tuple of (success, profile_data or error_data)

    Security:
        - Token sent via Authorization header (not query param)
        - Strict timeout prevents hanging connections
    """
    try:
        response = requests.get(
            OAUTH_PROFILE_URL,
            headers={
                "Authorization": f"Bearer {access_token}"
            },
            timeout=PROFILE_FETCH_TIMEOUT,
            verify=True
        )

        if response.status_code == 200:
            profile = response.json()
            # Only extract safe fields
            return True, {
                "username": profile.get("username", "Unknown"),
                "sub": profile.get("sub", ""),
            }
        elif response.status_code == 401:
            logger.warning("Profile fetch returned 401 — token may be expired")
            return False, {"error": "Access token is invalid or expired"}
        else:
            logger.error(f"Profile fetch failed with status {response.status_code}")
            return False, {"error": "Failed to retrieve user profile"}
    except requests.exceptions.Timeout:
        logger.error("Profile fetch timed out")
        return False, {"error": "Profile service did not respond in time"}
    except Exception:
        logger.exception("Unexpected error fetching profile")
        return False, {"error": "Failed to retrieve user profile"}


def revoke_token(access_token: str) -> bool:
    """
    Attempt to revoke an OAuth token on the Wikimedia side.

    This is a best-effort operation. Even if revocation fails,
    the local session will still be cleared.

    Returns:
        True if revocation succeeded, False otherwise
    """
    try:
        response = requests.post(
            "https://meta.wikimedia.org/w/rest.php/oauth2/access_token",
            data={
                "grant_type": "revoke",
                "token": access_token,
                "client_id": OAUTH_CLIENT_ID,
                "client_secret": OAUTH_CLIENT_SECRET
            },
            timeout=10,
            verify=True
        )
        return response.status_code == 200
    except Exception:
        logger.warning("Token revocation failed (best-effort)")
        return False


def add_depicts_statement(access_token: str, file_title: str, qid: str) -> Tuple[bool, str]:
    """
    Add a depicts (P180) statement to a Wikimedia Commons file.

    Uses the Wikibase API to create a new P180 claim on the file's
    structured data entity.

    Args:
        access_token: OAuth access token with edit permissions
        file_title: Validated file title (e.g., 'File:Example.jpg')
        qid: Validated Wikidata Q-ID (e.g., 'Q123')

    Returns:
        Tuple of (success, message)

    Security:
        - Input validation must be done BEFORE calling this function
        - Token sent via Authorization header
        - CSRF token obtained fresh for each write operation
    """
    if not file_title.startswith("File:"):
        file_title = f"File:{file_title}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "User-Agent": USER_AGENT,
        "Accept": "application/json"
    }

    try:
        # Step 1: Get the page ID to construct the media ID
        params = {
            "action": "query",
            "titles": file_title,
            "format": "json"
        }
        response = requests.get(
            COMMONS_API, params=params, headers=headers,
            timeout=API_REQUEST_TIMEOUT, verify=True
        )
        response.raise_for_status()
        data = response.json()

        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return False, "File not found on Commons"

        page_id = list(pages.keys())[0]
        if page_id == "-1":
            return False, "File not found on Commons"

        media_id = f"M{page_id}"

        # Step 2: Get a CSRF token (fresh for each write)
        token_params = {
            "action": "query",
            "meta": "tokens",
            "type": "csrf",
            "format": "json",
            "formatversion": "2"
        }
        token_response = requests.get(
            COMMONS_API, params=token_params, headers=headers,
            timeout=PROFILE_FETCH_TIMEOUT, verify=True
        )
        token_response.raise_for_status()
        csrf_token = token_response.json().get("query", {}).get("tokens", {}).get("csrftoken")
        if not csrf_token or csrf_token == "+\\":
            return False, "Failed to obtain CSRF token. Please re-authenticate."

        # Step 3: Add the depicts claim
        numeric_id = int(qid[1:])
        value_payload = json.dumps({"entity-type": "item", "numeric-id": numeric_id})
        claim_data = {
            "action": "wbcreateclaim",
            "entity": media_id,
            "property": "P180",
            "snaktype": "value",
            "value": value_payload,
            "token": csrf_token,
            "format": "json",
            "formatversion": "2",
            "summary": "Added depicts statement via Commons Depicts Analyzer",
            "assert": "user"
        }

        claim_response = requests.post(
            COMMONS_API, data=claim_data, headers=headers,
            timeout=API_REQUEST_TIMEOUT, verify=True
        )
        claim_response.raise_for_status()
        result = claim_response.json()

        if "error" in result:
            error_info = result["error"].get("info", "Unknown error")
            error_code = result["error"].get("code", "unknown")
            logger.error(f"Wikibase API error adding depicts ({error_code}): {error_info}")
            if error_code in {"modification-failed", "statement-conflict"}:
                return False, "Failed to add depicts statement. The file may already have this depicts."
            if error_code in {"assertuserfailed", "notloggedin"}:
                return False, "Authentication expired. Please log in again."
            return False, "Failed to add depicts statement. Please try again."

        logger.info(f"Successfully added depicts {qid} to {file_title}")
        return True, f"Successfully added depicts {qid} to {file_title}"

    except requests.exceptions.Timeout:
        logger.error("API request timed out while adding depicts")
        return False, "Request timed out. Please try again."
    except requests.exceptions.RequestException:
        logger.exception("API request failed while adding depicts")
        return False, "Failed to communicate with Wikimedia API"
    except Exception:
        logger.exception("Unexpected error adding depicts")
        return False, "An unexpected error occurred"
