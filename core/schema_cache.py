import time
from core.databricks_connect import get_schema_metadata

_CACHE = {}
_CACHE_TIMESTAMP = 0
CACHE_TTL = 3600  # Cache for 1 hour

def get_cached_schema() -> dict:
    """
    Retrieves governed schema metadata from Databricks Unity Catalog,
    caching it in memory to prevent repeated warehouse queries.
    """
    global _CACHE, _CACHE_TIMESTAMP
    current_time = time.time()
    
    if not _CACHE or (current_time - _CACHE_TIMESTAMP) > CACHE_TTL:
        _CACHE = get_schema_metadata("workspace", "governed")
        _CACHE_TIMESTAMP = current_time
    
    return _CACHE

def invalidate_cache():
    """Force clears the schema cache to fetch fresh data on the next run."""
    global _CACHE, _CACHE_TIMESTAMP
    _CACHE = {}
    _CACHE_TIMESTAMP = 0
