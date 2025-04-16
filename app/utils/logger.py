import logging
import sys

# Create a logger
logger = logging.getLogger("salestroopz")
logger.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

# Console Handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)

# Avoid duplicate handlers during reload
if not logger.handlers:
    logger.addHandler(console_handler)
