"""
OAuth 2.0 Module for Wikimedia Authentication

Handles the OAuth 2.0 authorization code flow with Wikimedia.
Provides helper functions for:
- Generating authorization URLs
- Exchanging codes for tokens
- Making authenticated API calls
- Adding depicts statements to Commons
"""

import requests
from typing import Dict, Any, Optional, Tuple
from config import (
    OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET, OAUTH_CALLBACK_URL,
    OAUTH_AUTHORIZE_URL, OAUTH_TOKEN_URL, OAUTH_PROFILE_URL
)

COMMONS_API = "https://commons.wikimedia.org/w/api.php"


def is_oauth_configured() -> bool:
    """Check if OAuth credentials are configured."""
    return bool(OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET)


def get_authorize_url(state: str) -> str:
    """
    Generate the OAuth authorization URL.
    
    Args:
        state: Random state string for CSRF protection
    
    Returns:
        Authorization URL to redirect the user to
    """
    params = {
        "response_type": "code",
        "client_id": OAUTH_CLIENT_ID,
        "redirect_uri": OAUTH_CALLBACK_URL,
        "state": state
    }
    query = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
    return f"{OAUTH_AUTHORIZE_URL}?{query}"


def exchange_code_for_token(code: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Exchange an authorization code for an access token.
    
    Args:
        code: Authorization code from the callback
    
    Returns:
        Tuple of (success, token_data or error_data)
    """
    try:
        response = requests.post(OAUTH_TOKEN_URL, data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": OAUTH_CLIENT_ID,
            "client_secret": OAUTH_CLIENT_SECRET,
            "redirect_uri": OAUTH_CALLBACK_URL
        }, timeout=30)
        
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, {"error": f"Token exchange failed: {response.status_code}"}
    except Exception as e:
        return False, {"error": str(e)}


def get_user_profile(access_token: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Get the authenticated user's profile from Wikimedia.
    
    Args:
        access_token: OAuth access token
    
    Returns:
        Tuple of (success, profile_data or error_data)
    """
    try:
        response = requests.get(OAUTH_PROFILE_URL, headers={
            "Authorization": f"Bearer {access_token}"
        }, timeout=15)
        
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, {"error": f"Profile fetch failed: {response.status_code}"}
    except Exception as e:
        return False, {"error": str(e)}


def add_depicts_statement(access_token: str, file_title: str, qid: str) -> Tuple[bool, str]:
    """
    Add a depicts (P180) statement to a Wikimedia Commons file.
    
    Uses the Wikibase API to create a new P180 claim on the file's
    structured data entity.
    
    Args:
        access_token: OAuth access token with edit permissions
        file_title: File title (e.g., 'File:Example.jpg')
        qid: Wikidata Q-ID to add as depicts value (e.g., 'Q123')
    
    Returns:
        Tuple of (success, message)
    """
    if not file_title.startswith("File:"):
        file_title = f"File:{file_title}"
    
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    try:
        # Step 1: Get the page ID to construct the media ID
        params = {
            "action": "query",
            "titles": file_title,
            "format": "json"
        }
        response = requests.get(COMMONS_API, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        pages = data.get("query", {}).get("pages", {})
        page_id = list(pages.keys())[0]
        if page_id == "-1":
            return False, f"File '{file_title}' not found on Commons"
        
        media_id = f"M{page_id}"
        
        # Step 2: Get a CSRF token
        token_params = {
            "action": "query",
            "meta": "tokens",
            "format": "json"
        }
        token_response = requests.get(COMMONS_API, params=token_params, headers=headers, timeout=15)
        token_response.raise_for_status()
        csrf_token = token_response.json().get("query", {}).get("tokens", {}).get("csrftoken", "+\\")
        
        # Step 3: Add the depicts claim
        claim_data = {
            "action": "wbcreateclaim",
            "entity": media_id,
            "property": "P180",
            "snaktype": "value",
            "value": f'{{"entity-type":"item","numeric-id":{qid.replace("Q", "")}}}',
            "token": csrf_token,
            "format": "json",
            "summary": "Added depicts statement via Commons Depicts Analyzer"
        }
        
        claim_response = requests.post(COMMONS_API, data=claim_data, headers=headers, timeout=30)
        claim_response.raise_for_status()
        result = claim_response.json()
        
        if "error" in result:
            return False, result["error"].get("info", "Unknown error adding depicts")
        
        return True, f"Successfully added depicts {qid} to {file_title}"
    
    except requests.exceptions.RequestException as e:
        return False, f"API request failed: {str(e)}"
    except Exception as e:
        return False, f"Error: {str(e)}"
