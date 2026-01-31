"""
Progress Tracker for DLRScanner

Manages checkpoint files for resume capability in bulk processing.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any
import tempfile
import shutil


class ProgressTracker:
    """Tracks processing progress with checkpoint files."""

    def __init__(self, checkpoint_path: str, logger=None):
        """
        Initialize the Progress Tracker.

        Args:
            checkpoint_path: Path to checkpoint file
            logger: Optional logger instance
        """
        self.checkpoint_path = checkpoint_path
        self.logger = logger or self._setup_logging()
        self.checkpoint_data = self._initialize_checkpoint()

    def _setup_logging(self):
        """Set up logging for the progress tracker."""
        today = datetime.now().strftime("%Y%m%d")

        logger = logging.getLogger('progress_tracker')
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            os.makedirs("logs", exist_ok=True)

            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler = logging.FileHandler(f"logs/progress_tracker_{today}.log")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def _initialize_checkpoint(self) -> Dict[str, Any]:
        """
        Initialize checkpoint data structure.

        Returns:
            Empty checkpoint dict
        """
        return {
            "phase": "parse",
            "total_files": 0,
            "processed_files": 0,
            "processed_file_paths": [],
            "failed_files": [],
            "last_updated": datetime.now().isoformat(),
            "statistics": {
                "emails_read": 0,
                "articles_extracted": 0,
                "entities_extracted": 0,
                "entities_matched": 0
            }
        }

    def load_checkpoint(self) -> Dict[str, Any]:
        """
        Load checkpoint from file.

        Returns:
            Checkpoint dict (or empty if file doesn't exist)
        """
        if os.path.exists(self.checkpoint_path):
            try:
                with open(self.checkpoint_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.checkpoint_data = data
                self.logger.info(f"Loaded checkpoint: {self.checkpoint_data['processed_files']}/{self.checkpoint_data['total_files']} files processed")
                return data
            except Exception as e:
                self.logger.error(f"Failed to load checkpoint: {e}")
                return self._initialize_checkpoint()
        else:
            self.logger.info("No checkpoint found, starting fresh")
            return self._initialize_checkpoint()

    def save_checkpoint(self, data: Dict[str, Any] = None):
        """
        Save checkpoint to file atomically.

        Args:
            data: Optional checkpoint data (uses current if not provided)
        """
        if data:
            self.checkpoint_data = data

        # Update timestamp
        self.checkpoint_data['last_updated'] = datetime.now().isoformat()

        try:
            # Create parent directory if needed
            os.makedirs(os.path.dirname(self.checkpoint_path) or '.', exist_ok=True)

            # Write to temp file first (atomic operation)
            with tempfile.NamedTemporaryFile(
                mode='w',
                encoding='utf-8',
                delete=False,
                dir=os.path.dirname(self.checkpoint_path) or '.',
                suffix='.tmp'
            ) as tmp_file:
                json.dump(self.checkpoint_data, tmp_file, indent=2, ensure_ascii=False)
                tmp_path = tmp_file.name

            # Atomic rename
            shutil.move(tmp_path, self.checkpoint_path)

            self.logger.debug(f"Saved checkpoint: {self.checkpoint_data['processed_files']}/{self.checkpoint_data['total_files']} files")

        except Exception as e:
            self.logger.error(f"Failed to save checkpoint: {e}")
            # Clean up temp file if it exists
            if 'tmp_path' in locals() and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except:
                    pass

    def is_processed(self, file_path: str) -> bool:
        """
        Check if a file has been processed.

        Args:
            file_path: File path to check

        Returns:
            True if file has been processed
        """
        # Normalize path for comparison
        normalized_path = os.path.normpath(file_path)
        processed_paths = [os.path.normpath(p) for p in self.checkpoint_data.get('processed_file_paths', [])]
        return normalized_path in processed_paths

    def mark_processed(self, file_path: str):
        """
        Mark a file as processed.

        Args:
            file_path: File path to mark
        """
        if not self.is_processed(file_path):
            self.checkpoint_data['processed_file_paths'].append(file_path)
            self.checkpoint_data['processed_files'] = len(self.checkpoint_data['processed_file_paths'])

    def mark_failed(self, file_path: str, error: str):
        """
        Mark a file as failed.

        Args:
            file_path: File path that failed
            error: Error message
        """
        self.checkpoint_data['failed_files'].append({
            "path": file_path,
            "error": error,
            "timestamp": datetime.now().isoformat()
        })
        self.logger.warning(f"Marked as failed: {file_path} - {error}")

    def get_remaining_files(self, all_files: List[str]) -> List[str]:
        """
        Get list of files that haven't been processed yet.

        Args:
            all_files: List of all file paths

        Returns:
            List of unprocessed file paths
        """
        processed_paths = set(os.path.normpath(p) for p in self.checkpoint_data.get('processed_file_paths', []))
        remaining = [f for f in all_files if os.path.normpath(f) not in processed_paths]

        self.logger.info(f"Remaining files: {len(remaining)}/{len(all_files)}")
        return remaining

    def update_statistics(self, stats: Dict[str, Any]):
        """
        Update checkpoint statistics.

        Args:
            stats: Statistics dict to merge
        """
        if 'statistics' not in self.checkpoint_data:
            self.checkpoint_data['statistics'] = {}

        self.checkpoint_data['statistics'].update(stats)

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get current statistics.

        Returns:
            Statistics dict
        """
        return self.checkpoint_data.get('statistics', {})

    def reset(self):
        """Reset checkpoint to initial state."""
        self.checkpoint_data = self._initialize_checkpoint()
        self.logger.info("Checkpoint reset")


# Convenience function
def create_tracker(checkpoint_path: str, resume: bool = False, logger=None) -> ProgressTracker:
    """
    Create a progress tracker with optional resume.

    Args:
        checkpoint_path: Path to checkpoint file
        resume: If True, load existing checkpoint
        logger: Optional logger instance

    Returns:
        ProgressTracker instance
    """
    tracker = ProgressTracker(checkpoint_path, logger=logger)

    if resume:
        tracker.load_checkpoint()
    else:
        tracker.reset()

    return tracker
