from langchain.llms.base import LLM
from typing import Optional, List, Any
from ..config.models import LLMConfig
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class LangChainLLM:
    """Wrapper for LLM models to work with LangChain. Supports both Ollama and HuggingFace."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.llm: Optional[LLM] = None
        self._wrapper = None
        self._multi_model_manager = None
        self.is_multi_model = config.multi_model is not None
    
    def initialize(self):
        """Initialize the LLM based on the configured provider."""
        logger.info(f"Initializing LangChain LLM wrapper with provider: {self.config.provider}")
        
        if self.is_multi_model:
            logger.info("Multi-model configuration detected, initializing multi-model manager")
            from .multi_model_manager import MultiModelManager
            self._multi_model_manager = MultiModelManager(self.config)
            self._multi_model_manager.initialize()
            self.llm = self._multi_model_manager.get_model("main")
            logger.info("Multi-model manager initialized")
            return
        
        if self.config.provider == "ollama":
            from .ollama_wrapper import OllamaLLM
            self._wrapper = OllamaLLM(self.config)
            self._wrapper.initialize()
            self.llm = self._wrapper.get_llm()
            
        elif self.config.provider == "huggingface":
            from .model_loader import ModelLoader
            from langchain_community.llms import HuggingFacePipeline
            
            self._wrapper = ModelLoader(self.config)
            self._wrapper.load_model()
            pipe = self._wrapper.create_pipeline()
            self.llm = HuggingFacePipeline(pipeline=pipe)
            
        else:
            raise ValueError(f"Unknown provider: {self.config.provider}. Must be 'ollama' or 'huggingface'")
        
        logger.info(f"LangChain LLM wrapper initialized with {self.config.provider}")
    
    def get_llm(self) -> LLM:
        """Get the LangChain LLM instance."""
        if self.llm is None:
            raise ValueError("LLM not initialized. Call initialize() first.")
        return self.llm
    
    def generate(self, prompt: str, use_reasoning: bool = False) -> str:
        """Generate text from a prompt.
        
        Args:
            prompt: Input prompt
            use_reasoning: Whether to use reasoning model (only for multi-model mode)
            
        Returns:
            Generated text
        """
        if self.is_multi_model and self._multi_model_manager:
            logger.info(f"Using multi-model generation (reasoning: {use_reasoning})")
            return self._multi_model_manager.generate(prompt, use_reasoning=use_reasoning)
        
        if self.llm is None:
            raise ValueError("LLM not initialized. Call initialize() first.")
        
        # Log which model is being used
        model_name = getattr(self.config, 'model_name', 'Unknown')
        provider = self.config.provider
        logger.info(f"Using LLM: {provider} - {model_name}")
        
        return self.llm.invoke(prompt)
    
    def generate_with_reasoning(self, prompt: str) -> tuple[str, str]:
        """Generate response using reasoning model first, then main model.
        Only available in multi-model mode.
        
        Args:
            prompt: Input prompt
            
        Returns:
            Tuple of (reasoning_output, final_response)
        """
        if not self.is_multi_model or not self._multi_model_manager:
            raise ValueError("Multi-model mode not enabled")
        
        logger.info("Using multi-model generation with reasoning chain")
        return self._multi_model_manager.generate_with_reasoning(prompt)
    
    def cleanup(self):
        """Clean up resources."""
        if self._multi_model_manager:
            self._multi_model_manager.cleanup()
        elif self._wrapper and hasattr(self._wrapper, 'cleanup'):
            self._wrapper.cleanup()
        elif self._wrapper and hasattr(self._wrapper, 'unload_model'):
            self._wrapper.unload_model()
        self.llm = None
        logger.info("LangChain LLM wrapper cleaned up")
