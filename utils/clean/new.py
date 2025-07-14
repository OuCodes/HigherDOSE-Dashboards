"""
Utility module for cleaning up development artifacts.

This module provides functions to clean up common development artifacts:
- Removes all __pycache__ directories recursively from a given path
- Removes all .log files and their rotated versions from the logs directory

The module can be run directly as a script to clean the project directory.
"""

import sys
import shutil
from pathlib import Path

# Add the parent directory to sys.path so we can import from logs
if __name__ == "__main__":
    # When running directly, add the utils directory to the path
    sys.path.insert(0, str(Path(__file__).parent.parent))

from logs import report

logger = report.settings(__file__)

def remove_pycache_dirs(start_path: Path | str) -> None:
    """Recursively remove all __pycache__ directories from the given path."""
    start_path = Path(start_path)
    try:
        for pycache_path in start_path.glob('**/__pycache__'):
            if pycache_path.is_dir():
                logger.info("Removing __pycache__ directory: %s", pycache_path)
                shutil.rmtree(pycache_path)
    except OSError as e:
        logger.error("Error removing __pycache__ directories: %s", e)

def remove_log_files(logs_dir: Path | str) -> None:
    """Remove all .log and .log.* files from the logs directory."""
    log_path = Path(logs_dir)
    if not log_path.exists():
        logger.warning("Logs directory does not exist: %s", logs_dir)
        return

    try:
        # Simplified pattern matching using a single glob pattern
        log_files = list(log_path.glob("*.log*"))

        for log_file in log_files:
            if log_file.is_file():  # Ensure we're only removing files
                logger.info("Removing log file: %s", log_file)
                try:
                    log_file.unlink(missing_ok=True)
                except (PermissionError, OSError) as e:
                    logger.error("Failed to remove log file %s: %s", log_file, e)
    except OSError as e:
        logger.error("Error scanning logs directory %s: %s", logs_dir, e)

def main():
    """Main function to orchestrate the cleanup process.
    This function:
    1. Determines the project's base directory structure
    2. Removes all __pycache__ directories from the utils directory
    3. Removes all log files from the logs directory
    The cleanup process is logged for tracking and debugging purposes.
    """
    # Get the base directory (assuming script is in utils/clean)
    base_dir = Path(__file__).parent.parent.parent
    utils_dir = base_dir / 'utils'
    logs_dir = utils_dir / 'logs'

    logger.info("Starting cleanup process...")

    # Remove __pycache__ directories
    logger.info("Removing __pycache__ directories...")
    remove_pycache_dirs(utils_dir)

    # Remove log files
    logger.info("Removing log files...")
    remove_log_files(logs_dir)

    logger.info("Cleanup completed successfully!")

if __name__ == "__main__":
    main()
