from langchain_community.llms import Ollama
from typing import Optional
from ..config.models import LLMConfig
from ..core.logging_config import get_logger
from ..core.exceptions import ModelLoadError

logger = get_logger(__name__)


class OllamaLLM:
    """Wrapper for Ollama models to work with LangChain."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.llm: Optional[Ollama] = None
    
    def initialize(self):
        """Initialize the Ollama LLM."""
        logger.info(f"Initializing Ollama LLM with model: {self.config.model_name}")
        logger.info(f"Ollama base URL: {self.config.base_url}")
        
        try:
            self.llm = Ollama(
                model=self.config.model_name,
                base_url=self.config.base_url,
                temperature=self.config.temperature,
            )
            
            logger.info("Ollama LLM initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Ollama: {str(e)}")
            raise ModelLoadError(f"Failed to initialize Ollama: {str(e)}")
    
    def get_llm(self) -> Ollama:
        """Get the LangChain LLM instance."""
        if self.llm is None:
            raise ValueError("LLM not initialized. Call initialize() first.")
        return self.llm
    
    def generate(self, prompt: str) -> str:
        """Generate text from a prompt.
        
        Args:
            prompt: Input prompt
            
        Returns:
            Generated text
        """
        if self.llm is None:
            raise ValueError("LLM not initialized. Call initialize() first.")
        
        logger.info(f"Using Ollama model: {self.config.model_name}")
        return self.llm.invoke(prompt)
    
    def cleanup(self):
        """Clean up resources."""
        self.llm = None
        logger.info("Ollama LLM cleaned up")
