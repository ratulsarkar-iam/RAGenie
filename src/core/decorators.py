"""Decorators for error handling and retry logic."""

import functools
import time
from typing import Callable, Type, Tuple, Optional
from .logging_config import get_logger
from .exceptions import RagChatbotException

logger = get_logger(__name__)


def handle_exceptions(
    exception_types: Tuple[Type[Exception], ...] = (Exception,),
    default_return=None,
    log_error: bool = True
):
    """Decorator to handle exceptions and return default value.
    
    Args:
        exception_types: Tuple of exception types to catch
        default_return: Default value to return on exception
        log_error: Whether to log the error
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exception_types as e:
                if log_error:
                    logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
                return default_return
        return wrapper
    return decorator


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """Decorator to retry a function on failure with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exception types to retry on
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {str(e)}. "
                            f"Retrying in {current_delay}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed for {func.__name__}: {str(e)}"
                        )
            
            raise last_exception
        return wrapper
    return decorator


def log_execution(log_args: bool = False, log_result: bool = False):
    """Decorator to log function execution.
    
    Args:
        log_args: Whether to log function arguments
        log_result: Whether to log function result
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            
            if log_args:
                logger.debug(f"Calling {func_name} with args={args}, kwargs={kwargs}")
            else:
                logger.debug(f"Calling {func_name}")
            
            try:
                result = func(*args, **kwargs)
                
                if log_result:
                    logger.debug(f"{func_name} returned: {result}")
                else:
                    logger.debug(f"{func_name} completed successfully")
                
                return result
            except Exception as e:
                logger.error(f"{func_name} raised exception: {str(e)}", exc_info=True)
                raise
        return wrapper
    return decorator


def validate_input(**validators):
    """Decorator to validate function inputs.
    
    Args:
        **validators: Keyword arguments mapping parameter names to validation functions
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get function signature
            import inspect
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # Validate each parameter
            for param_name, validator_func in validators.items():
                if param_name in bound_args.arguments:
                    value = bound_args.arguments[param_name]
                    if not validator_func(value):
                        raise ValueError(
                            f"Validation failed for parameter '{param_name}' in {func.__name__}"
                        )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator
