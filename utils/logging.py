import logging

_LOGGED_MESSAGES: set[str] = set()

dev_logger = logging.getLogger('dev')
data_logger = logging.getLogger('data_qc')


def log_once(logger: logging.Logger, message: str, level: int = logging.WARNING) -> None:
    """Log a message only once, avoiding duplicates across all loggers."""
    if message not in _LOGGED_MESSAGES:
        _LOGGED_MESSAGES.add(message)
        logger.log(level, message)
