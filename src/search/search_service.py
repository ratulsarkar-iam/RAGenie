from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from duckduckgo_search import DDGS
from ..config.models import SearchConfig
from ..core.logging_config import get_logger
from ..core.exceptions import SearchError
from ..core.decorators import handle_exceptions, retry

logger = get_logger(__name__)


class SearchResult:
    """Represents a search result."""
    
    def __init__(self, title: str, url: str, snippet: str, source: str = "web"):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.source = source
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source
        }
    
    def __str__(self) -> str:
        return f"[{self.title}]({self.url})\n{self.snippet}"


class SearchService:
    """Service for performing internet searches."""
    
    def __init__(self, config: SearchConfig):
        self.config = config
        self.cache: Dict[str, tuple] = {}  # query -> (results, timestamp)
    
    @retry(max_attempts=3, delay=1.0, exceptions=(Exception,))
    @handle_exceptions(exception_types=(Exception,), log_error=True, default_return=[])
    def search(self, query: str, max_results: Optional[int] = None) -> List[SearchResult]:
        """Perform a web search.
        
        Args:
            query: Search query
            max_results: Maximum number of results (overrides config)
            
        Returns:
            List of SearchResult objects
        """
        # Check cache
        cached_results = self._get_from_cache(query)
        if cached_results is not None:
            logger.debug(f"Returning cached results for: {query}")
            return cached_results
        
        # Determine max results
        limit = max_results or self.config.max_results
        
        logger.info(f"Searching for: {query} (max_results={limit})")
        
        # Perform search based on provider
        if self.config.provider == "duckduckgo":
            results = self._search_duckduckgo(query, limit)
        else:
            raise SearchError(f"Unsupported search provider: {self.config.provider}")
        
        # Cache results
        self._add_to_cache(query, results)
        
        logger.info(f"Found {len(results)} results for: {query}")
        return results
    
    def _search_duckduckgo(self, query: str, max_results: int) -> List[SearchResult]:
        """Search using DuckDuckGo."""
        try:
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(query, max_results=max_results))
            
            # Convert to SearchResult objects
            results = []
            for item in raw_results:
                result = SearchResult(
                    title=item.get('title', ''),
                    url=item.get('href', ''),
                    snippet=item.get('body', ''),
                    source='duckduckgo'
                )
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {str(e)}")
            raise SearchError(f"Search failed: {str(e)}")
    
    def _get_from_cache(self, query: str) -> Optional[List[SearchResult]]:
        """Get results from cache if not expired.
        
        Args:
            query: Search query
            
        Returns:
            Cached results or None if expired/not found
        """
        if query not in self.cache:
            return None
        
        results, timestamp = self.cache[query]
        
        # Check if expired
        age = datetime.now() - timestamp
        if age.total_seconds() > self.config.cache_ttl_seconds:
            del self.cache[query]
            return None
        
        return results
    
    def _add_to_cache(self, query: str, results: List[SearchResult]):
        """Add results to cache.
        
        Args:
            query: Search query
            results: Search results
        """
        self.cache[query] = (results, datetime.now())
    
    def clear_cache(self):
        """Clear the search cache."""
        self.cache.clear()
        logger.info("Search cache cleared")
    
    def format_results(self, results: List[SearchResult]) -> str:
        """Format search results as a string.
        
        Args:
            results: List of SearchResult objects
            
        Returns:
            Formatted string
        """
        if not results:
            return "No search results found."
        
        formatted = []
        for i, result in enumerate(results, 1):
            formatted.append(f"{i}. {result.title}\n   URL: {result.url}\n   {result.snippet}\n")
        
        return "\n".join(formatted)
