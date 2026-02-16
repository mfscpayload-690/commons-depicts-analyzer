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
import threading
from collections import OrderedDict
from typing import List, Tuple, Dict, Optional, Any

# API Endpoints
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"

# User-Agent header (required by Wikimedia API policy)
HEADERS = {
    "User-Agent": "CommonsDepictsAnalyzer/1.0 (Educational workshop project; Contact: workshop@example.com)"
}

# Simple in-memory cache for QID labels with TTL + LRU eviction
_LABEL_CACHE_TTL = 3600  # seconds
_LABEL_CACHE_MAX = 5000
_label_cache: "OrderedDict[str, Tuple[str, float]]" = OrderedDict()
_label_cache_lock = threading.Lock()

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


def _cache_get(cache_key: str) -> Optional[str]:
    now = time.time()
    with _label_cache_lock:
        entry = _label_cache.get(cache_key)
        if not entry:
            return None
        value, timestamp = entry
        if now - timestamp > _LABEL_CACHE_TTL:
            _label_cache.pop(cache_key, None)
            return None
        _label_cache.move_to_end(cache_key)
        return value


def _cache_set(cache_key: str, value: str) -> None:
    now = time.time()
    with _label_cache_lock:
        _label_cache[cache_key] = (value, now)
        _label_cache.move_to_end(cache_key)
        while len(_label_cache) > _LABEL_CACHE_MAX:
            _label_cache.popitem(last=False)


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
    response = requests.get(COMMONS_API, params=params, headers=HEADERS, timeout=30)
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
    sdc_response = requests.get(COMMONS_API, params=sdc_params, headers=HEADERS, timeout=30)
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
def check_depicts_batch(file_titles: List[str]) -> Dict[str, Tuple[bool, List[str]]]:
    """
    Check multiple Commons files for depicts (P180) statements in batches.

    Args:
        file_titles: List of file titles (e.g., ['File:Example.jpg', ...])

    Returns:
        Dict mapping file title to (has_depicts, qid_list)
    """
    results: Dict[str, Tuple[bool, List[str]]] = {title: (False, []) for title in file_titles}
    if not file_titles:
        return results

    params = {
        "action": "query",
        "titles": "|".join(file_titles),
        "format": "json"
    }

    _rate_limit()
    response = requests.get(COMMONS_API, params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()
    data = response.json()

    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return results

    media_ids: List[str] = []
    media_to_title: Dict[str, str] = {}

    for page_id, page in pages.items():
        title = page.get("title")
        if not title or page_id == "-1":
            continue
        media_id = f"M{page_id}"
        media_ids.append(media_id)
        media_to_title[media_id] = title

    if not media_ids:
        return results

    sdc_params = {
        "action": "wbgetentities",
        "ids": "|".join(media_ids),
        "format": "json"
    }

    _rate_limit()
    sdc_response = requests.get(COMMONS_API, params=sdc_params, headers=HEADERS, timeout=30)
    sdc_response.raise_for_status()
    sdc_data = sdc_response.json()

    entities = sdc_data.get("entities", {})
    for media_id, entity in entities.items():
        title = media_to_title.get(media_id)
        if not title:
            continue

        statements = entity.get("statements", {})
        p180_claims = statements.get("P180", [])

        qids: List[str] = []
        for claim in p180_claims:
            mainsnak = claim.get("mainsnak", {})
            datavalue = mainsnak.get("datavalue", {})
            if datavalue.get("type") == "wikibase-entityid":
                qid = datavalue.get("value", {}).get("id")
                if qid:
                    qids.append(qid)

        results[title] = (len(qids) > 0, qids)

    return results


@retry_on_failure(max_retries=2, base_delay=0.5)
def resolve_labels(qids: List[str], language: str = "en") -> Dict[str, str]:
    """
    Resolve Wikidata QIDs to labels in specified language.

    Uses caching to avoid repeated API calls for the same QIDs.

    Args:
        qids: List of QIDs (e.g., ['Q123', 'Q456'])
        language: Language code (e.g., 'en', 'fr', 'de', 'es', 'hi', 'ml')

    Returns:
        Dict mapping QID to label (e.g., {'Q123': 'Cat', 'Q456': 'Dog'})
    """
    if not qids:
        return {}

    result = {}
    qids_to_fetch = []

    # Check cache first (cache key includes language)
    for qid in qids:
        cache_key = f"{qid}:{language}"
        cached = _cache_get(cache_key)
        if cached is not None:
            result[qid] = cached
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
            "languages": language,
            "format": "json"
        }

        response = requests.get(WIKIDATA_API, params=params, headers=HEADERS, timeout=30)
        response.raise_for_status()
        data = response.json()

        entities = data.get("entities", {})
        for qid, entity in entities.items():
            labels = entity.get("labels", {})
            # Try requested language, fallback to English, then QID
            label = labels.get(language, {}).get("value") or labels.get("en", {}).get("value", qid)
            result[qid] = label
            _cache_set(f"{qid}:{language}", label)

    return result


@retry_on_failure(max_retries=2, base_delay=0.5)
def fetch_file_info(file_title: str) -> Dict[str, Any]:
    """
    Fetch detailed file information from Wikimedia Commons.

    Args:
        file_title: File title (e.g., 'File:Example.jpg')

    Returns:
        Dict with thumbnail URL, dimensions, size, description, upload date, etc.
    """
    if not file_title.startswith("File:"):
        file_title = f"File:{file_title}"

    params = {
        "action": "query",
        "titles": file_title,
        "prop": "imageinfo",
        "iiprop": "url|size|extmetadata|timestamp|mime|user",
        "iiurlwidth": 800,
        "format": "json"
    }

    _rate_limit()
    response = requests.get(COMMONS_API, params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()
    data = response.json()

    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return {"error": "File not found"}

    page = list(pages.values())[0]
    if "imageinfo" not in page:
        return {"error": "No image info available"}

    info = page["imageinfo"][0]
    extmeta = info.get("extmetadata", {})

    # Extract description (strip HTML tags for clean display)
    description_raw = extmeta.get("ImageDescription", {}).get("value", "")
    # Basic HTML tag stripping
    import re
    description = re.sub(r'<[^>]+>', '', description_raw).strip()

    return {
        "title": file_title,
        "thumbnail_url": info.get("thumburl", ""),
        "original_url": info.get("url", ""),
        "width": info.get("width", 0),
        "height": info.get("height", 0),
        "size": info.get("size", 0),
        "mime": info.get("mime", ""),
        "timestamp": info.get("timestamp", ""),
        "user": info.get("user", ""),
        "description": description,
        "license": extmeta.get("LicenseShortName", {}).get("value", "Unknown"),
        "categories": extmeta.get("Categories", {}).get("value", ""),
    }


def suggest_depicts(file_title: str, limit: int = 5) -> List[Dict[str, str]]:
    """
    Suggest Wikidata Q-items based on keywords parsed from a file's title.

    Parses the filename into keywords, searches Wikidata for matching entities,
    and returns top suggestions with labels, descriptions, and QIDs.

    Args:
        file_title: File title (e.g., 'File:Golden Gate Bridge at sunset.jpg')
        limit: Maximum suggestions to return

    Returns:
        List of dicts with 'qid', 'label', 'description' keys
    """
    import re

    # Strip prefix and extension
    name = file_title.replace("File:", "")
    name = re.sub(r'\.[a-zA-Z0-9]+$', '', name)  # Remove extension

    # Replace common separators with spaces
    name = name.replace("_", " ").replace("-", " ")

    # Remove common wiki noise patterns
    name = re.sub(r'\b\d{4,}\b', '', name)  # Remove years/numbers
    name = re.sub(r'\b[A-Z]{2,5}\s*\d+\b', '', name)  # e.g., "DSC 1234"
    name = re.sub(r'\bIMG\b|\bDSC\b|\bP\d+\b|\bIMGP\b', '', name, flags=re.IGNORECASE)

    # Split into meaningful keywords (3+ chars)
    stopwords = {
        'the', 'and', 'for', 'from', 'with', 'this', 'that', 'are', 'was',
        'has', 'have', 'been', 'not', 'but', 'its', 'his', 'her', 'their',
        'our', 'can', 'will', 'may', 'jpg', 'jpeg', 'png', 'svg', 'tif',
        'tiff', 'gif', 'file', 'image', 'photo', 'picture', 'crop', 'edit',
        'version', 'original', 'commons', 'wiki', 'wikipedia'
    }

    words = name.split()
    keywords = [w.strip() for w in words if len(w.strip()) >= 3 and w.strip().lower() not in stopwords]

    if not keywords:
        return []

    # Build compound search queries for better results
    # Try the full cleaned name first, then individual keywords
    search_queries = []

    # Full phrase (up to first 5 meaningful words)
    full_phrase = " ".join(keywords[:5])
    if len(keywords) > 1:
        search_queries.append(full_phrase)

    # Individual keywords (skip very short ones for individual search)
    for kw in keywords[:4]:
        if len(kw) >= 4:
            search_queries.append(kw)

    # Deduplicate
    seen = set()
    unique_queries = []
    for q in search_queries:
        ql = q.lower()
        if ql not in seen:
            seen.add(ql)
            unique_queries.append(q)

    suggestions = []
    seen_qids = set()

    for query in unique_queries:
        if len(suggestions) >= limit:
            break

        try:
            params = {
                "action": "wbsearchentities",
                "search": query,
                "language": "en",
                "format": "json",
                "limit": 3,
                "type": "item"
            }

            _rate_limit()
            response = requests.get(WIKIDATA_API, params=params, headers=HEADERS, timeout=15)
            response.raise_for_status()
            data = response.json()

            for result in data.get("search", []):
                qid = result.get("id", "")
                if qid and qid not in seen_qids:
                    seen_qids.add(qid)
                    suggestions.append({
                        "qid": qid,
                        "label": result.get("label", qid),
                        "description": result.get("description", "")
                    })
                    if len(suggestions) >= limit:
                        break
        except Exception:
            continue

    return suggestions
