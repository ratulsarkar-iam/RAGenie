from typing import Dict, Optional, Literal
from langchain.llms.base import LLM
from ..config.models import LLMConfig, ModelConfig
from ..core.logging_config import get_logger
from ..core.exceptions import ModelLoadError

logger = get_logger(__name__)


class MultiModelManager:
    """Manage multiple LLM models with different roles (reasoning, main, fallback)."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.models: Dict[str, LLM] = {}
        self.wrappers: Dict[str, any] = {}
        self.is_multi_model = config.multi_model is not None
        
    def initialize(self):
        """Initialize all configured models."""
        if not self.is_multi_model:
            logger.info("Multi-model not configured, using single model mode")
            return
        
        logger.info("Initializing multi-model setup")
        
        for role, model_config in self.config.multi_model.items():
            try:
                logger.info(f"Loading {role} model: {model_config.model_name}")
                
                if model_config.provider == "ollama":
                    from .ollama_wrapper import OllamaLLM
                    wrapper = OllamaLLM(self._convert_to_llm_config(model_config))
                    wrapper.initialize()
                    self.models[role] = wrapper.get_llm()
                    self.wrappers[role] = wrapper
                    
                elif model_config.provider == "huggingface":
                    from .model_loader import ModelLoader
                    from langchain_community.llms import HuggingFacePipeline
                    
                    wrapper = ModelLoader(self._convert_to_llm_config(model_config))
                    wrapper.load_model()
                    pipe = wrapper.create_pipeline()
                    self.models[role] = HuggingFacePipeline(pipeline=pipe)
                    self.wrappers[role] = wrapper
                    
                else:
                    raise ValueError(f"Unknown provider: {model_config.provider}")
                
                logger.info(f"Successfully loaded {role} model: {model_config.model_name}")
                
            except Exception as e:
                logger.error(f"Failed to load {role} model: {str(e)}")
                if role == "main":
                    raise ModelLoadError(f"Failed to load main model: {str(e)}")
                logger.warning(f"Continuing without {role} model")
    
    def _convert_to_llm_config(self, model_config: ModelConfig) -> LLMConfig:
        """Convert ModelConfig to LLMConfig for compatibility."""
        return LLMConfig(
            provider=model_config.provider,
            model_name=model_config.model_name,
            base_url=model_config.base_url,
            max_tokens=model_config.max_tokens,
            temperature=model_config.temperature,
            top_p=model_config.top_p,
            top_k=model_config.top_k,
            quantization=model_config.quantization,
            device=model_config.device
        )
    
    def get_model(self, role: Literal["reasoning", "main", "fallback"] = "main") -> Optional[LLM]:
        """Get a model by role.
        
        Args:
            role: Model role (reasoning, main, or fallback)
            
        Returns:
            LLM instance or None if not available
        """
        if not self.is_multi_model:
            return None
        
        return self.models.get(role)
    
    def generate_with_reasoning(self, prompt: str) -> tuple[str, str]:
        """Generate response using reasoning model first, then main model.
        
        Args:
            prompt: Input prompt
            
        Returns:
            Tuple of (reasoning_output, final_response)
        """
        reasoning_output = ""
        reasoning_model_name = ""
        
        if "reasoning" in self.models:
            try:
                reasoning_config = self.config.multi_model.get("reasoning")
                reasoning_model_name = reasoning_config.model_name if reasoning_config else "Unknown"
                logger.info(f"Using reasoning model: {reasoning_model_name}")
                
                reasoning_prompt = f"""Analyze the following question and provide your reasoning process:

Question: {prompt}

Provide a step-by-step reasoning process:"""
                
                reasoning_output = self.models["reasoning"].invoke(reasoning_prompt)
                logger.info("Reasoning model completed")
                
            except Exception as e:
                logger.error(f"Reasoning model failed: {str(e)}")
                reasoning_output = ""
        
        main_model = self.models.get("main")
        model_used = "main"
        if not main_model:
            logger.warning("Main model not available, trying fallback")
            main_model = self.models.get("fallback")
            model_used = "fallback"
        
        if not main_model:
            raise ModelLoadError("No available model for generation")
        
        try:
            # Get model name for logging
            model_config = self.config.multi_model.get(model_used)
            model_name = model_config.model_name if model_config else "Unknown"
            
            if reasoning_output:
                logger.info(f"Using {model_used} model with reasoning: {model_name}")
                final_prompt = f"""Based on the following reasoning process, provide a clear and concise answer:

Reasoning:
{reasoning_output}

Original Question: {prompt}

Answer:"""
            else:
                logger.info(f"Using {model_used} model: {model_name}")
                final_prompt = prompt
            
            final_response = main_model.invoke(final_prompt)
            return reasoning_output, final_response
            
        except Exception as e:
            logger.error(f"Main model failed: {str(e)}")
            
            if "fallback" in self.models and main_model != self.models["fallback"]:
                logger.info("Trying fallback model")
                try:
                    fallback_config = self.config.multi_model.get("fallback")
                    fallback_name = fallback_config.model_name if fallback_config else "Unknown"
                    logger.info(f"Using fallback model: {fallback_name}")
                    
                    final_response = self.models["fallback"].invoke(final_prompt)
                    return reasoning_output, final_response
                except Exception as fallback_error:
                    logger.error(f"Fallback model also failed: {str(fallback_error)}")
                    raise ModelLoadError(f"All models failed: {str(e)}")
            else:
                raise ModelLoadError(f"Generation failed: {str(e)}")
    
    def generate(self, prompt: str, use_reasoning: bool = False) -> str:
        """Generate response using appropriate model(s).
        
        Args:
            prompt: Input prompt
            use_reasoning: Whether to use reasoning model first
            
        Returns:
            Generated response
        """
        if not self.is_multi_model:
            logger.warning("Multi-model not initialized")
            return ""
        
        # Use reasoning model if requested and available
        if use_reasoning and "reasoning" in self.models:
            reasoning_output, final_response = self.generate_with_reasoning(prompt)
            return final_response
        
        # Use main model
        main_model = self.models.get("main")
        model_used = "main"
        if not main_model:
            logger.warning("Main model not available, trying fallback")
            main_model = self.models.get("fallback")
            model_used = "fallback"
        
        if not main_model:
            raise ModelLoadError("No available model for generation")
        
        try:
            # Get model name for logging
            model_config = self.config.multi_model.get(model_used)
            model_name = model_config.model_name if model_config else "Unknown"
            logger.info(f"Using multi-model: {model_used} - {model_name}")
            
            response = main_model.invoke(prompt)
            return response
        except Exception as e:
            logger.error(f"Main model failed: {str(e)}")
            
            # Try fallback model
            if "fallback" in self.models and main_model != self.models["fallback"]:
                logger.info("Trying fallback model")
                try:
                    fallback_config = self.config.multi_model.get("fallback")
                    fallback_name = fallback_config.model_name if fallback_config else "Unknown"
                    logger.info(f"Using fallback model: {fallback_name}")
                    
                    response = self.models["fallback"].invoke(prompt)
                    return response
                except Exception as fallback_error:
                    logger.error(f"Fallback model also failed: {str(fallback_error)}")
                    raise ModelLoadError(f"All models failed: {str(e)}")
            else:
                raise ModelLoadError(f"Generation failed: {str(e)}")
    
    def cleanup(self):
        """Clean up all model resources."""
        for role, wrapper in self.wrappers.items():
            try:
                if hasattr(wrapper, 'cleanup'):
                    wrapper.cleanup()
                elif hasattr(wrapper, 'unload_model'):
                    wrapper.unload_model()
                logger.info(f"Cleaned up {role} model")
            except Exception as e:
                logger.error(f"Error cleaning up {role} model: {str(e)}")
        
        self.models.clear()
        self.wrappers.clear()
        logger.info("Multi-model manager cleaned up")
