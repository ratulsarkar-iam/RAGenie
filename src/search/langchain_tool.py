from langchain.tools import Tool
from typing import Optional
from .search_service import SearchService
from ..core.logging_config import get_logger

logger = get_logger(__name__)


def create_search_tool(search_service: SearchService) -> Tool:
    """Create a LangChain tool for web search.
    
    Args:
        search_service: SearchService instance
        
    Returns:
        LangChain Tool object
    """
    def search_wrapper(query: str) -> str:
        """Wrapper function for the search tool."""
        try:
            results = search_service.search(query)
            return search_service.format_results(results)
        except Exception as e:
            logger.error(f"Search tool error: {str(e)}")
            return f"Search failed: {str(e)}"
    
    return Tool(
        name="web_search",
        description="Search the internet for current information. Use this when you need up-to-date information or facts that might not be in the knowledge base. Input should be a search query string.",
        func=search_wrapper
    )
