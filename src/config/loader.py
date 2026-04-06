import os
import yaml
from pathlib import Path
from typing import Any, Dict
from dotenv import load_dotenv
from .models import Config


class ConfigLoader:
    """Load and manage application configuration with environment variable overrides."""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = Path(config_path)
        load_dotenv()
    
    def load(self) -> Config:
        """Load configuration from YAML file with environment variable overrides."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, "r") as f:
            config_dict = yaml.safe_load(f) or {}
        
        # Apply environment variable overrides
        config_dict = self._apply_env_overrides(config_dict)
        
        # Validate and create Config object
        return Config(**config_dict)
    
    def _apply_env_overrides(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides to configuration.
        
        Environment variables follow the pattern: SECTION_KEY
        Example: LLM_MODEL_NAME, RAG_CHUNK_SIZE, SERVER_PORT
        """
        env_mappings = {
            # Mode
            "MODE": ("mode",),
            
            # LLM settings
            "LLM_PROVIDER": ("llm", "provider"),
            "LLM_MODEL_NAME": ("llm", "model_name"),
            "LLM_BASE_URL": ("llm", "base_url"),
            "LLM_QUANTIZATION": ("llm", "quantization"),
            "LLM_MAX_TOKENS": ("llm", "max_tokens"),
            "LLM_TEMPERATURE": ("llm", "temperature"),
            "LLM_DEVICE": ("llm", "device"),
            
            # RAG settings
            "RAG_STORAGE_TYPE": ("rag", "storage_type"),
            "RAG_CHUNK_SIZE": ("rag", "chunk_size"),
            "RAG_CHUNK_OVERLAP": ("rag", "chunk_overlap"),
            "RAG_TOP_K": ("rag", "top_k"),
            "RAG_INDEX_PATH": ("rag", "index_path"),
            
            # Search settings
            "SEARCH_PROVIDER": ("search", "provider"),
            "SEARCH_MAX_RESULTS": ("search", "max_results"),
            
            # Server settings
            "SERVER_HOST": ("server", "host"),
            "SERVER_PORT": ("server", "port"),
            
            # MCP Server settings
            "MCP_SERVER_ENABLED": ("mcp_server", "enabled"),
            "MCP_SERVER_TRANSPORT": ("mcp_server", "transport"),
            "MCP_SERVER_NAME": ("mcp_server", "name"),
            "MCP_SERVER_PORT": ("mcp_server", "port"),
            
            # Conversation settings
            "CONVERSATION_MAX_HISTORY": ("conversation", "max_history"),
            "CONVERSATION_DB_PATH": ("conversation", "db_path"),
            
            # Logging settings
            "LOGGING_LEVEL": ("logging", "level"),
            "LOGGING_FILE": ("logging", "file"),
        }
        
        for env_var, path in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                self._set_nested_value(config_dict, path, self._convert_type(value))
        
        return config_dict
    
    def _set_nested_value(self, d: Dict, path: tuple, value: Any):
        """Set a value in a nested dictionary using a path tuple."""
        for key in path[:-1]:
            if key not in d:
                d[key] = {}
            d = d[key]
        d[path[-1]] = value
    
    def _convert_type(self, value: str) -> Any:
        """Convert string environment variable to appropriate type."""
        # Boolean conversion
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False
        
        # Integer conversion
        try:
            return int(value)
        except ValueError:
            pass
        
        # Float conversion
        try:
            return float(value)
        except ValueError:
            pass
        
        # Return as string
        return value


def load_config(config_path: str = "config/config.yaml") -> Config:
    """Convenience function to load configuration."""
    loader = ConfigLoader(config_path)
    return loader.load()
