#!/usr/bin/env python3
"""
Logging configuration for distroget.
Sets up file and console logging with appropriate levels.
"""

import logging
import os
from pathlib import Path


def setup_logging(log_level=logging.INFO, log_file=None):
    """
    Configure logging for the application.
    
    Args:
        log_level: Logging level (default: INFO)
        log_file: Path to log file. If None, uses ~/.config/distroget/distroget.log
    """
    # Determine log file location
    if log_file is None:
        config_dir = Path.home() / '.config' / 'distroget'
        config_dir.mkdir(parents=True, exist_ok=True)
        log_file = config_dir / 'distroget.log'
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Set up root logger
    root_logger = logging.getLogger('distroget')
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # File handler
    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler (only for WARNING and above to avoid cluttering terminal)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    root_logger.info(f"Logging initialized - log file: {log_file}")
    
    return str(log_file)


def get_log_file():
    """Get the path to the log file."""
    config_dir = Path.home() / '.config' / 'distroget'
    return config_dir / 'distroget.log'
