import logging
import os
import sys

def configure_logging(log_file=None, level=None):
    """
    Configure consistent logging across the application
    
    Args:
        log_file: Optional path to log file. If None, only console logging is used.
        level: Optional log level to override default
    """
    # Set default level based on environment or use INFO
    default_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    log_level = getattr(logging, level or default_level, logging.INFO)
    
    # Create handlers
    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file, mode='a'))  # Append to existing log
        
    # Configure basic logging
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message).200s',  # Truncate long messages
        handlers=handlers
    )
    
    # Set specific module levels
    logging.getLogger('roollm').setLevel(log_level)
    logging.getLogger('github_mcp_adapter').setLevel(log_level)
    logging.getLogger('roollm_with_mcp').setLevel(log_level)
    
    # Reduce noise from HTTP libraries
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    
    # Log configuration info
    logging.getLogger(__name__).info(f"Logging configured: level={logging.getLevelName(log_level)}")
    
def get_request_logger(request_id=None):
    """
    Get a logger that includes request ID in messages
    
    Args:
        request_id: Optional request ID to include in log messages
    
    Returns:
        A logger function that formats messages with request ID
    """
    logger = logging.getLogger('request')
    
    def log(level, message, *args, **kwargs):
        formatted_message = f"[{request_id}] {message}" if request_id else message
        getattr(logger, level)(formatted_message, *args, **kwargs)
    
    return {
        'debug': lambda msg, *args, **kwargs: log('debug', msg, *args, **kwargs),
        'info': lambda msg, *args, **kwargs: log('info', msg, *args, **kwargs),
        'warning': lambda msg, *args, **kwargs: log('warning', msg, *args, **kwargs),
        'error': lambda msg, *args, **kwargs: log('error', msg, *args, **kwargs)
    } 