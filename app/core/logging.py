import logging
import sys
from datetime import datetime


class StructuredFormatter(logging.Formatter):
    """Custom formatter providing clean structured logs with timestamps and levels."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.utcfromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] [{record.levelname:<8}] [{record.name}] {record.getMessage()}"
        if record.exc_info:
            log_msg += f"\n{self.formatException(record.exc_info)}"
        return log_msg


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configures application-wide logging."""
    logger = logging.getLogger("clinic_platform")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)

    return logger


logger = setup_logging()
