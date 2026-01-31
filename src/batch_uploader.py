"""
Batch Uploader for DLRScanner

Uploads articles to DealCloud in batches with rate limiting and retry logic.
"""

import os
import json
import logging
import time
import tempfile
import shutil
from datetime import datetime
from typing import List, Dict, Any


class BatchUploader:
    """Uploads articles in batches with rate limiting and retry."""

    def __init__(
        self,
        dealcloud_uploader,
        batch_size: int = 50,
        rate_limit_delay: float = 1.0,
        max_retries: int = 3,
        logger=None
    ):
        """
        Initialize the Batch Uploader.

        Args:
            dealcloud_uploader: DealCloudUploader instance
            batch_size: Number of articles per batch (default: 50)
            rate_limit_delay: Delay in seconds between batches (default: 1.0)
            max_retries: Maximum retry attempts per batch (default: 3)
            logger: Optional logger instance
        """
        self.uploader = dealcloud_uploader
        self.batch_size = batch_size
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.logger = logger or self._setup_logging()

    def _setup_logging(self):
        """Set up logging for the batch uploader."""
        today = datetime.now().strftime("%Y%m%d")

        logger = logging.getLogger('batch_uploader')
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            os.makedirs("logs", exist_ok=True)

            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler = logging.FileHandler(f"logs/batch_uploader_{today}.log")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def _initialize_upload_checkpoint(self, total_articles: int) -> Dict[str, Any]:
        """
        Initialize upload checkpoint structure.

        Args:
            total_articles: Total number of articles to upload

        Returns:
            Checkpoint dict
        """
        return {
            "total_articles": total_articles,
            "uploaded_articles": 0,
            "current_batch": 0,
            "last_successful_batch": -1,
            "failed_batches": [],
            "last_updated": datetime.now().isoformat(),
            "statistics": {
                "successful_uploads": 0,
                "failed_uploads": 0,
                "batches_completed": 0,
                "batches_failed": 0
            }
        }

    def _load_upload_checkpoint(self, checkpoint_path: str) -> Dict[str, Any]:
        """
        Load upload checkpoint from file.

        Args:
            checkpoint_path: Path to checkpoint file

        Returns:
            Checkpoint dict (or empty if doesn't exist)
        """
        if os.path.exists(checkpoint_path):
            try:
                with open(checkpoint_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Failed to load upload checkpoint: {e}")
                return None
        return None

    def _save_upload_checkpoint(self, checkpoint_data: Dict[str, Any], checkpoint_path: str):
        """
        Save upload checkpoint atomically.

        Args:
            checkpoint_data: Checkpoint data
            checkpoint_path: Path to checkpoint file
        """
        checkpoint_data['last_updated'] = datetime.now().isoformat()

        try:
            # Create parent directory if needed
            os.makedirs(os.path.dirname(checkpoint_path) or '.', exist_ok=True)

            # Write to temp file first
            with tempfile.NamedTemporaryFile(
                mode='w',
                encoding='utf-8',
                delete=False,
                dir=os.path.dirname(checkpoint_path) or '.',
                suffix='.tmp'
            ) as tmp_file:
                json.dump(checkpoint_data, tmp_file, indent=2, ensure_ascii=False)
                tmp_path = tmp_file.name

            # Atomic rename
            shutil.move(tmp_path, checkpoint_path)

            self.logger.debug(f"Saved upload checkpoint: batch {checkpoint_data['current_batch']}")

        except Exception as e:
            self.logger.error(f"Failed to save upload checkpoint: {e}")
            if 'tmp_path' in locals() and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except:
                    pass

    def _upload_batch(self, batch: List[Dict[str, Any]], batch_num: int) -> Dict[str, Any]:
        """
        Upload a single batch of articles.

        Args:
            batch: List of articles to upload
            batch_num: Batch number (for logging)

        Returns:
            Upload statistics dict
        """
        self.logger.info(f"Uploading batch {batch_num} ({len(batch)} articles)...")

        try:
            stats = self.uploader.upload_articles(batch)
            return stats
        except Exception as e:
            self.logger.error(f"Error uploading batch {batch_num}: {e}")
            return {
                'total_articles': len(batch),
                'uploaded': 0,
                'failed': len(batch),
                'entry_ids': [],
                'success_rate': 0,
                'error': str(e)
            }

    def _retry_with_backoff(self, batch: List[Dict[str, Any]], batch_num: int) -> Dict[str, Any]:
        """
        Retry batch upload with exponential backoff.

        Args:
            batch: List of articles to upload
            batch_num: Batch number

        Returns:
            Upload statistics dict
        """
        for attempt in range(self.max_retries):
            # Calculate backoff delay: 0s, 2s, 4s
            if attempt > 0:
                backoff_delay = attempt * 2
                self.logger.info(f"Retrying batch {batch_num} (attempt {attempt + 1}/{self.max_retries}) after {backoff_delay}s...")
                time.sleep(backoff_delay)

            stats = self._upload_batch(batch, batch_num)

            # Check if upload was successful
            if stats.get('uploaded', 0) > 0 or stats.get('success_rate', 0) > 0:
                if attempt > 0:
                    self.logger.info(f"Batch {batch_num} succeeded on attempt {attempt + 1}")
                return stats

            # If completely failed and we have retries left, continue
            if attempt < self.max_retries - 1:
                self.logger.warning(f"Batch {batch_num} failed, will retry...")
            else:
                self.logger.error(f"Batch {batch_num} failed after {self.max_retries} attempts")

        # Return the last failed stats
        return stats

    def upload_in_batches(
        self,
        articles: List[Dict[str, Any]],
        checkpoint_path: str,
        resume: bool = False
    ) -> Dict[str, Any]:
        """
        Upload articles in batches with checkpointing.

        Args:
            articles: List of prepared articles
            checkpoint_path: Path to checkpoint file
            resume: If True, resume from checkpoint

        Returns:
            Upload statistics dict
        """
        total_articles = len(articles)
        self.logger.info(f"Starting batch upload of {total_articles} articles")
        self.logger.info(f"Batch size: {self.batch_size}, Rate limit: {self.rate_limit_delay}s, Max retries: {self.max_retries}")

        # Initialize or load checkpoint
        checkpoint = None
        start_batch = 0

        if resume:
            checkpoint = self._load_upload_checkpoint(checkpoint_path)
            if checkpoint:
                start_batch = checkpoint['last_successful_batch'] + 1
                self.logger.info(f"Resuming from batch {start_batch}")
            else:
                self.logger.warning("Resume requested but no checkpoint found, starting fresh")

        if not checkpoint:
            checkpoint = self._initialize_upload_checkpoint(total_articles)

        # Split articles into batches
        total_batches = (total_articles + self.batch_size - 1) // self.batch_size
        self.logger.info(f"Total batches: {total_batches}")

        # Process batches
        for batch_num in range(start_batch, total_batches):
            # Extract batch
            start_idx = batch_num * self.batch_size
            end_idx = min(start_idx + self.batch_size, total_articles)
            batch = articles[start_idx:end_idx]

            checkpoint['current_batch'] = batch_num

            # Upload with retry
            stats = self._retry_with_backoff(batch, batch_num)

            # Update checkpoint
            uploaded = stats.get('uploaded', 0)
            failed = stats.get('failed', 0)

            checkpoint['uploaded_articles'] += uploaded
            checkpoint['statistics']['successful_uploads'] += uploaded
            checkpoint['statistics']['failed_uploads'] += failed

            if uploaded > 0:
                checkpoint['last_successful_batch'] = batch_num
                checkpoint['statistics']['batches_completed'] += 1
                self.logger.info(f"Batch {batch_num} completed: {uploaded}/{len(batch)} uploaded")
            else:
                checkpoint['statistics']['batches_failed'] += 1
                checkpoint['failed_batches'].append({
                    "batch_num": batch_num,
                    "error": stats.get('error', 'Unknown error'),
                    "timestamp": datetime.now().isoformat()
                })
                self.logger.error(f"Batch {batch_num} failed completely")

            # Save checkpoint every batch (for fine-grained resume)
            self._save_upload_checkpoint(checkpoint, checkpoint_path)

            # Rate limiting between batches (except for last batch)
            if batch_num < total_batches - 1:
                self.logger.debug(f"Rate limit delay: {self.rate_limit_delay}s")
                time.sleep(self.rate_limit_delay)

        # Final statistics
        final_stats = {
            'total_articles': total_articles,
            'uploaded': checkpoint['uploaded_articles'],
            'failed': total_articles - checkpoint['uploaded_articles'],
            'success_rate': (checkpoint['uploaded_articles'] / total_articles * 100) if total_articles > 0 else 0,
            'batches_completed': checkpoint['statistics']['batches_completed'],
            'batches_failed': checkpoint['statistics']['batches_failed'],
            'total_batches': total_batches
        }

        if checkpoint['failed_batches']:
            final_stats['failed_batches'] = checkpoint['failed_batches']

        self.logger.info(f"Batch upload complete: {final_stats['uploaded']}/{total_articles} uploaded ({final_stats['success_rate']:.1f}%)")

        return final_stats


# Convenience function
def upload_with_batching(
    articles: List[Dict[str, Any]],
    dealcloud_uploader,
    checkpoint_path: str = "data/upload_checkpoint.json",
    batch_size: int = 50,
    rate_limit_delay: float = 1.0,
    max_retries: int = 3,
    resume: bool = False,
    logger=None
) -> Dict[str, Any]:
    """
    Convenience function to upload articles in batches.

    Args:
        articles: List of prepared articles
        dealcloud_uploader: DealCloudUploader instance
        checkpoint_path: Path to checkpoint file
        batch_size: Articles per batch
        rate_limit_delay: Delay between batches (seconds)
        max_retries: Max retry attempts per batch
        resume: Resume from checkpoint
        logger: Optional logger instance

    Returns:
        Upload statistics dict
    """
    uploader = BatchUploader(
        dealcloud_uploader=dealcloud_uploader,
        batch_size=batch_size,
        rate_limit_delay=rate_limit_delay,
        max_retries=max_retries,
        logger=logger
    )

    return uploader.upload_in_batches(
        articles=articles,
        checkpoint_path=checkpoint_path,
        resume=resume
    )
