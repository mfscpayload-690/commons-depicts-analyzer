"""
Wikimedia Commons API Module

Provides functions to interact with MediaWiki and Wikidata APIs:
- fetch_category_files: Get all files from a Commons category
- check_depicts: Check if a file has P180 depicts statements
- resolve_labels: Convert QIDs to human-readable labels

Enhanced with:
- Retry logic with exponential backoff
- Rate limiting to avoid API throttling
- Better error messages
"""

import requests
import time
import functools
from typing import List, Tuple, Dict, Optional

# API Endpoints
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"

# User-Agent header (required by Wikimedia API policy)
HEADERS = {
    "User-Agent": "CommonsDepictsAnalyzer/1.0 (Educational workshop project; Contact: workshop@example.com)"
}

# Simple in-memory cache for QID labels
_label_cache: Dict[str, str] = {}

# Rate limiting disabled - let API handle its own throttling
# Set to 0 for real-time speed, increase if you get rate limited
RATE_LIMIT_DELAY = 0.0  # No delay between requests
_last_request_time = 0.0


def _rate_limit():
    """Enforce rate limiting between API calls (disabled by default)."""
    global _last_request_time
    if RATE_LIMIT_DELAY > 0:
        current_time = time.time()
        elapsed = current_time - _last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        _last_request_time = time.time()


def retry_on_failure(max_retries: int = 3, base_delay: float = 1.0):
    """
    Decorator to retry failed API calls with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds (doubles each retry)
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        print(f"  [RETRY] Attempt {attempt + 1} failed, retrying in {delay}s...")
                        time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator


def validate_category_exists(category_name: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a category exists on Wikimedia Commons.
    
    Args:
        category_name: Category name (with 'Category:' prefix)
    
    Returns:
        Tuple of (exists: bool, error_message: Optional[str])
    """
    _rate_limit()
    params = {
        "action": "query",
        "titles": category_name,
        "format": "json"
    }
    
    try:
        response = requests.get(COMMONS_API, params=params, headers=HEADERS, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return (False, f"Category '{category_name}' not found on Commons")
        
        page_id = list(pages.keys())[0]
        if page_id == "-1":
            return (False, f"Category '{category_name}' does not exist on Wikimedia Commons")
        
        return (True, None)
    except requests.exceptions.RequestException as e:
        return (False, f"Network error checking category: {str(e)}")


@retry_on_failure(max_retries=2, base_delay=0.5)
def fetch_category_suggestions(query: str, limit: int = 8) -> List[str]:
    """
    Fetch category name suggestions from Wikimedia Commons.

    Args:
        query: Partial category name (without 'Category:' prefix)
        limit: Max number of suggestions

    Returns:
        List of category names without the 'Category:' prefix
    """
    if not query or len(query.strip()) < 2:
        return []

    _rate_limit()
    params = {
        "action": "query",
        "list": "prefixsearch",
        "pssearch": f"Category:{query.strip()}",
        "psnamespace": 14,
        "pslimit": str(limit),
        "format": "json"
    }

    response = requests.get(COMMONS_API, params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()
    data = response.json()

    results = []
    items = data.get("query", {}).get("prefixsearch", [])
    for item in items:
        title = item.get("title", "")
        if title.startswith("Category:"):
            title = title[len("Category:"):]
        if title:
            results.append(title)

    return results


@retry_on_failure(max_retries=3, base_delay=1.0)
def fetch_category_files(category_name: str) -> List[str]:
    """
    Fetch all file titles from a Wikimedia Commons category.
    
    Args:
        category_name: Category name (with or without 'Category:' prefix)
    
    Returns:
        List of file titles (e.g., ['File:Example.jpg', ...])
    
    Raises:
        ValueError: If category doesn't exist or is empty
        requests.exceptions.RequestException: If API call fails after retries
    """
    # Normalize category name
    if not category_name.startswith("Category:"):
        category_name = f"Category:{category_name}"
    
    # Validate category exists before fetching
    exists, error_msg = validate_category_exists(category_name)
    if not exists:
        raise ValueError(error_msg)
    
    files = []
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": category_name,
        "cmtype": "file",
        "cmlimit": "500",  # Max allowed per request
        "format": "json"
    }
    
    page_count = 0
    while True:
        _rate_limit()  # Rate limit each request
        response = requests.get(COMMONS_API, params=params, headers=HEADERS, timeout=90)
        response.raise_for_status()
        data = response.json()
        
        # Extract file titles
        members = data.get("query", {}).get("categorymembers", [])
        for member in members:
            files.append(member["title"])
        
        page_count += 1
        print(f"  [API] Fetched page {page_count}, total files so far: {len(files)}")
        
        # Check for more pages
        if "continue" in data:
            params["cmcontinue"] = data["continue"]["cmcontinue"]
        else:
            break
    
    return files


@retry_on_failure(max_retries=2, base_delay=0.5)
def check_depicts(file_title: str) -> Tuple[bool, List[str]]:
    """
    Check if a Commons file has depicts (P180) statements.
    
    Uses Structured Data on Commons (SDC) via wbgetentities.
    
    Args:
        file_title: File title (e.g., 'File:Example.jpg')
    
    Returns:
        Tuple of (has_depicts: bool, qid_list: list of QIDs)
    """
    # Get the media ID (M-prefixed) for the file
    # First, get the page ID
    params = {
        "action": "query",
        "titles": file_title,
        "format": "json"
    }
    
    _rate_limit()  # Rate limit
    response = requests.get(COMMONS_API, params=params, headers=HEADERS, timeout=90)
    response.raise_for_status()
    data = response.json()
    
    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return (False, [])
    
    page_id = list(pages.keys())[0]
    if page_id == "-1":
        return (False, [])  # File not found
    
    # Now get the structured data using the M-prefixed ID
    media_id = f"M{page_id}"
    
    sdc_params = {
        "action": "wbgetentities",
        "ids": media_id,
        "format": "json"
    }
    
    _rate_limit()  # Rate limit
    sdc_response = requests.get(COMMONS_API, params=sdc_params, headers=HEADERS, timeout=90)
    sdc_response.raise_for_status()
    sdc_data = sdc_response.json()
    
    entity = sdc_data.get("entities", {}).get(media_id, {})
    statements = entity.get("statements", {})
    
    # Check for P180 (depicts) property
    p180_claims = statements.get("P180", [])
    
    if not p180_claims:
        return (False, [])
    
    # Extract QIDs from depicts claims
    qids = []
    for claim in p180_claims:
        mainsnak = claim.get("mainsnak", {})
        datavalue = mainsnak.get("datavalue", {})
        if datavalue.get("type") == "wikibase-entityid":
            qid = datavalue.get("value", {}).get("id")
            if qid:
                qids.append(qid)
    
    return (len(qids) > 0, qids)


@retry_on_failure(max_retries=2, base_delay=0.5)
def resolve_labels(qids: List[str]) -> Dict[str, str]:
    """
    Resolve Wikidata QIDs to English labels.
    
    Uses caching to avoid repeated API calls for the same QIDs.
    
    Args:
        qids: List of QIDs (e.g., ['Q123', 'Q456'])
    
    Returns:
        Dict mapping QID to label (e.g., {'Q123': 'Cat', 'Q456': 'Dog'})
    """
    if not qids:
        return {}
    
    result = {}
    qids_to_fetch = []
    
    # Check cache first
    for qid in qids:
        if qid in _label_cache:
            result[qid] = _label_cache[qid]
        else:
            qids_to_fetch.append(qid)
    
    if not qids_to_fetch:
        return result
    
    # Fetch uncached labels (batch up to 50 at a time)
    for i in range(0, len(qids_to_fetch), 50):
        batch = qids_to_fetch[i:i + 50]
        
        params = {
            "action": "wbgetentities",
            "ids": "|".join(batch),
            "props": "labels",
            "languages": "en",
            "format": "json"
        }
        
        response = requests.get(WIKIDATA_API, params=params, headers=HEADERS, timeout=90)
        response.raise_for_status()
        data = response.json()
        
        entities = data.get("entities", {})
        for qid, entity in entities.items():
            labels = entity.get("labels", {})
            en_label = labels.get("en", {}).get("value", qid)  # Fallback to QID
            result[qid] = en_label
            _label_cache[qid] = en_label  # Cache it
    
    return result
