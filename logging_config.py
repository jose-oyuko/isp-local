import os
from datetime import datetime
from loguru import logger

def setup_logging():
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Remove default handler
    logger.remove()

    # Add file handler
    log_file = os.path.join('logs', f'mikrotik_{datetime.now().strftime("%Y%m%d")}.log')
    logger.add(
        log_file,
        rotation="5 MB",
        retention="10 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}"
    )

    # Add console handler
    logger.add(
        lambda msg: print(msg),
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
    )

    return logger 