import logging

_LOGGED_MESSAGES: set[str] = set()

dev_logger = logging.getLogger('dev')
data_logger = logging.getLogger('data_qc')

def setup_logging() -> None:
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    dev_logger.setLevel(logging.INFO)
    dev_handler = logging.FileHandler('dev_debug.log')
    dev_handler.setFormatter(formatter)
    dev_logger.addHandler(dev_handler)

    data_logger.setLevel(logging.INFO)
    data_handler = logging.FileHandler('report.log')
    data_handler.setFormatter(formatter)
    data_logger.addHandler(data_handler)

def log_once(logger: logging.Logger, message: str, level: int = logging.WARNING) -> None:
    """Log a message only once, avoiding duplicates across all loggers."""
    if message not in _LOGGED_MESSAGES:
        _LOGGED_MESSAGES.add(message)
        logger.log(level, message)
