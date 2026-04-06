import logging
import sys
from pathlib import Path
from typing import Optional
from ..config.models import LoggingConfig


def setup_logging(config: Optional[LoggingConfig] = None) -> logging.Logger:
    """Set up logging configuration for the application.
    
    Args:
        config: LoggingConfig object with logging settings
        
    Returns:
        Configured logger instance
    """
    if config is None:
        config = LoggingConfig()
    
    # Create logs directory if it doesn't exist
    log_file = Path(config.file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, config.level),
        format=config.format,
        handlers=[
            logging.FileHandler(config.file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Get logger for the application
    logger = logging.getLogger("rag_chatbot")
    logger.setLevel(getattr(logging, config.level))
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module.
    
    Args:
        name: Logger name (typically __name__ of the module)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(f"rag_chatbot.{name}")
