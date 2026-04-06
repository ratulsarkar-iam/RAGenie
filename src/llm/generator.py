from typing import Iterator, Optional
import torch
from ..config.models import LLMConfig
from ..core.logging_config import get_logger
from ..core.exceptions import GenerationError
from ..core.decorators import handle_exceptions

logger = get_logger(__name__)


class TextGenerator:
    """Handle text generation with streaming support."""
    
    def __init__(self, model_loader):
        self.model_loader = model_loader
        self.model = model_loader.model
        self.tokenizer = model_loader.tokenizer
        self.config = model_loader.config
    
    @handle_exceptions(exception_types=(Exception,), log_error=True)
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text from a prompt.
        
        Args:
            prompt: Input prompt
            **kwargs: Additional generation parameters
            
        Returns:
            Generated text
        """
        if self.model is None or self.tokenizer is None:
            raise GenerationError("Model not loaded")
        
        # Tokenize input
        inputs = self.tokenizer(prompt, return_tensors="pt")
        
        # Move to device
        device = self.model_loader.device
        if device != "cpu":
            inputs = {k: v.to(device) for k, v in inputs.items()}
        
        # Generation parameters
        gen_kwargs = {
            "max_new_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "top_p": kwargs.get("top_p", self.config.top_p),
            "top_k": kwargs.get("top_k", self.config.top_k),
            "do_sample": True,
            "pad_token_id": self.tokenizer.pad_token_id,
            "eos_token_id": self.tokenizer.eos_token_id
        }
        
        # Generate
        with torch.no_grad():
            outputs = self.model.generate(**inputs, **gen_kwargs)
        
        # Decode
        generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Remove the prompt from output
        if generated_text.startswith(prompt):
            generated_text = generated_text[len(prompt):].strip()
        
        return generated_text
    
    def generate_stream(self, prompt: str, **kwargs) -> Iterator[str]:
        """Generate text with streaming (token by token).
        
        Args:
            prompt: Input prompt
            **kwargs: Additional generation parameters
            
        Yields:
            Generated tokens
        """
        if self.model is None or self.tokenizer is None:
            raise GenerationError("Model not loaded")
        
        # Tokenize input
        inputs = self.tokenizer(prompt, return_tensors="pt")
        
        # Move to device
        device = self.model_loader.device
        if device != "cpu":
            inputs = {k: v.to(device) for k, v in inputs.items()}
        
        # Generation parameters
        gen_kwargs = {
            "max_new_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "top_p": kwargs.get("top_p", self.config.top_p),
            "top_k": kwargs.get("top_k", self.config.top_k),
            "do_sample": True,
            "pad_token_id": self.tokenizer.pad_token_id,
            "eos_token_id": self.tokenizer.eos_token_id
        }
        
        # Track generated tokens
        input_length = inputs["input_ids"].shape[1]
        
        # Generate with streaming
        with torch.no_grad():
            for _ in range(gen_kwargs["max_new_tokens"]):
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=1,
                    temperature=gen_kwargs["temperature"],
                    top_p=gen_kwargs["top_p"],
                    top_k=gen_kwargs["top_k"],
                    do_sample=gen_kwargs["do_sample"],
                    pad_token_id=gen_kwargs["pad_token_id"],
                    eos_token_id=gen_kwargs["eos_token_id"]
                )
                
                # Get new token
                new_token_id = outputs[0, -1].unsqueeze(0).unsqueeze(0)
                
                # Check for EOS
                if new_token_id.item() == self.tokenizer.eos_token_id:
                    break
                
                # Decode and yield
                token_text = self.tokenizer.decode(new_token_id[0], skip_special_tokens=True)
                yield token_text
                
                # Update inputs for next iteration
                inputs["input_ids"] = outputs
                if "attention_mask" in inputs:
                    inputs["attention_mask"] = torch.cat([
                        inputs["attention_mask"],
                        torch.ones((1, 1), dtype=torch.long, device=inputs["attention_mask"].device)
                    ], dim=1)
    
    def clear_cache(self):
        """Clear GPU cache to free memory."""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.debug("Cleared GPU cache")
