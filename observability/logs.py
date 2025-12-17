"""
Structured Logging Configuration
Sets up structlog with JSON output and context processors
"""

import logging
import sys
from typing import Any, Dict, Optional
import structlog
from structlog.types import EventDict, Processor


def add_app_context(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """Add application context to log entries"""
    event_dict["app"] = "local-assistant"
    return event_dict


def add_log_level(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """Add log level to event dict"""
    event_dict["level"] = method_name
    return event_dict


def censor_sensitive_data(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """Censor sensitive data from logs"""
    sensitive_keys = ["api_key", "password", "token", "secret", "authorization"]

    def _censor_dict(d: Dict[str, Any]) -> Dict[str, Any]:
        censored = {}
        for key, value in d.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                censored[key] = "***REDACTED***"
            elif isinstance(value, dict):
                censored[key] = _censor_dict(value)
            elif isinstance(value, list):
                censored[key] = [_censor_dict(item) if isinstance(item, dict) else item for item in value]
            else:
                censored[key] = value
        return censored

    return _censor_dict(event_dict)


def setup_logging(
    log_level: str = "INFO",
    json_logs: bool = True,
    console_logs: bool = True,
    log_file: Optional[str] = None,
) -> None:
    """
    Configure structured logging with structlog.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: Whether to output logs in JSON format
        console_logs: Whether to output logs to console
        log_file: Optional path to log file

    Example:
        setup_logging(log_level="DEBUG", json_logs=True, log_file="logs/app.log")
        logger = get_logger(__name__)
        logger.info("application_started", version="1.0.0")
    """
    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout if console_logs else None,
        level=numeric_level,
    )

    # Build processor chain
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        add_app_context,
        add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        censor_sensitive_data,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Create formatters
    if json_logs:
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=processors,
        )
    else:
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=True),
            foreign_pre_chain=processors,
        )

    # Configure handlers
    handlers = []

    if console_logs:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(numeric_level)
        handlers.append(console_handler)

    if log_file:
        from pathlib import Path
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(numeric_level)
        handlers.append(file_handler)

    # Apply handlers to root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    for handler in handlers:
        root_logger.addHandler(handler)
    root_logger.setLevel(numeric_level)

    # Log initialization
    logger = structlog.get_logger(__name__)
    logger.info(
        "logging_configured",
        log_level=log_level,
        json_logs=json_logs,
        console_logs=console_logs,
        log_file=log_file,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Structured logger

    Example:
        logger = get_logger(__name__)
        logger.info("event_occurred", user_id=123, action="login")
    """
    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """
    Bind context variables to all subsequent log entries.

    Args:
        **kwargs: Context variables to bind

    Example:
        bind_context(request_id="abc123", user_id=456)
        logger.info("processing_request")  # Will include request_id and user_id
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all bound context variables"""
    structlog.contextvars.clear_contextvars()


def unbind_context(*keys: str) -> None:
    """
    Unbind specific context variables.

    Args:
        *keys: Context variable keys to unbind
    """
    structlog.contextvars.unbind_contextvars(*keys)


class LogContext:
    """
    Context manager for temporary log context.

    Example:
        with LogContext(request_id="abc123"):
            logger.info("processing")  # Includes request_id
        logger.info("done")  # Does not include request_id
    """

    def __init__(self, **kwargs: Any):
        self.context = kwargs
        self.previous_context: Dict[str, Any] = {}

    def __enter__(self) -> "LogContext":
        # Save current context
        self.previous_context = structlog.contextvars.get_contextvars()
        # Bind new context
        structlog.contextvars.bind_contextvars(**self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # Restore previous context
        structlog.contextvars.clear_contextvars()
        if self.previous_context:
            structlog.contextvars.bind_contextvars(**self.previous_context)


# Log level helpers
def set_log_level(level: str) -> None:
    """
    Change log level at runtime.

    Args:
        level: New log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.getLogger().setLevel(numeric_level)
    for handler in logging.getLogger().handlers:
        handler.setLevel(numeric_level)


def disable_library_logs(library: str, level: str = "WARNING") -> None:
    """
    Disable or reduce verbosity of third-party library logs.

    Args:
        library: Library name (e.g., "httpx", "openai")
        level: Minimum level to show (defaults to WARNING)
    """
    numeric_level = getattr(logging, level.upper(), logging.WARNING)
    logging.getLogger(library).setLevel(numeric_level)


# Default configuration
def setup_default_logging() -> None:
    """Setup logging with sensible defaults for local assistant"""
    setup_logging(
        log_level="INFO",
        json_logs=True,
        console_logs=True,
        log_file="logs/local_assistant.log",
    )

    # Reduce verbosity of common libraries
    disable_library_logs("httpx", "WARNING")
    disable_library_logs("httpcore", "WARNING")
    disable_library_logs("openai", "WARNING")
    disable_library_logs("anthropic", "WARNING")
    disable_library_logs("google", "WARNING")
