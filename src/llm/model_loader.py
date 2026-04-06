import torch
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
    pipeline
)
from typing import Optional
from ..config.models import LLMConfig
from ..core.logging_config import get_logger
from ..core.exceptions import ModelLoadError
from ..core.decorators import log_execution

logger = get_logger(__name__)


class ModelLoader:
    """Load and manage HuggingFace models with quantization support."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.model = None
        self.tokenizer = None
        self.device = self._get_device()
    
    def _get_device(self) -> str:
        """Detect and return the appropriate device."""
        if self.config.device == "mps" and torch.backends.mps.is_available():
            logger.info("Using MPS (Metal Performance Shaders) for Mac M3")
            return "mps"
        elif self.config.device == "cuda" and torch.cuda.is_available():
            logger.info("Using CUDA GPU")
            return "cuda"
        else:
            logger.info("Using CPU")
            return "cpu"
    
    @log_execution()
    def load_model(self):
        """Load the HuggingFace model with quantization if configured."""
        try:
            logger.info(f"Loading model: {self.config.model_name}")
            logger.info(f"Quantization: {self.config.quantization}")
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.config.model_name,
                trust_remote_code=True,
                use_fast=False
            )
            
            # Set pad token if not present
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Configure quantization
            quantization_config = None
            if self.config.quantization == "4bit":
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True
                )
            elif self.config.quantization == "8bit":
                quantization_config = BitsAndBytesConfig(
                    load_in_8bit=True
                )
            
            # Load model
            model_kwargs = {
                "trust_remote_code": True,
                "low_cpu_mem_usage": True
            }
            
            if quantization_config:
                model_kwargs["quantization_config"] = quantization_config
                model_kwargs["device_map"] = "auto"
            else:
                model_kwargs["torch_dtype"] = torch.float16
            
            self.model = AutoModelForCausalLM.from_pretrained(
                self.config.model_name,
                **model_kwargs
            )
            
            # Move to device if not using quantization
            if not quantization_config and self.device != "cpu":
                self.model = self.model.to(self.device)
            
            logger.info("Model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            raise ModelLoadError(f"Failed to load model {self.config.model_name}: {str(e)}")
    
    def create_pipeline(self):
        """Create a text generation pipeline."""
        if self.model is None or self.tokenizer is None:
            raise ModelLoadError("Model not loaded. Call load_model() first.")
        
        return pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer,
            max_new_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            top_p=self.config.top_p,
            top_k=self.config.top_k,
            do_sample=True,
            pad_token_id=self.tokenizer.pad_token_id
        )
    
    def unload_model(self):
        """Unload model from memory."""
        if self.model is not None:
            del self.model
            self.model = None
        
        if self.tokenizer is not None:
            del self.tokenizer
            self.tokenizer = None
        
        # Clear CUDA cache if using GPU
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        logger.info("Model unloaded from memory")
