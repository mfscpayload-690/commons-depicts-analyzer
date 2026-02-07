"""
Wikimedia Commons API Module

Provides functions to interact with MediaWiki and Wikidata APIs:
- fetch_category_files: Get all files from a Commons category
- check_depicts: Check if a file has P180 depicts statements
- resolve_labels: Convert QIDs to human-readable labels
"""

import requests
from typing import List, Tuple, Dict

# API Endpoints
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"

# User-Agent header (required by Wikimedia API policy)
HEADERS = {
    "User-Agent": "CommonsDepictsAnalyzer/1.0 (Educational workshop project; Contact: workshop@example.com)"
}

# Simple in-memory cache for QID labels
_label_cache: Dict[str, str] = {}


def fetch_category_files(category_name: str) -> List[str]:
    """
    Fetch all file titles from a Wikimedia Commons category.
    
    Args:
        category_name: Category name (with or without 'Category:' prefix)
    
    Returns:
        List of file titles (e.g., ['File:Example.jpg', ...])
    """
    # Normalize category name
    if not category_name.startswith("Category:"):
        category_name = f"Category:{category_name}"
    
    files = []
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": category_name,
        "cmtype": "file",
        "cmlimit": "500",  # Max allowed per request
        "format": "json"
    }
    
    while True:
        response = requests.get(COMMONS_API, params=params, headers=HEADERS, timeout=90)
        response.raise_for_status()
        data = response.json()
        
        # Extract file titles
        members = data.get("query", {}).get("categorymembers", [])
        for member in members:
            files.append(member["title"])
        
        # Check for more pages
        if "continue" in data:
            params["cmcontinue"] = data["continue"]["cmcontinue"]
        else:
            break
    
    return files


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
