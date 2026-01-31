"""
Bulk Email Processor for DLRScanner

CLI tool for processing thousands of .eml files in two phases:
- Phase 1 (parse): Read .eml files → Parse → Extract entities → Validate → Save to JSON
- Phase 2 (upload): Load JSON → Upload to DealCloud in batches

Usage:
    # Parse emails and save locally
    python bulk_process_emails.py parse --folder "C:\\path\\to\\emails" --output "data/bulk_articles.json"

    # Upload previously parsed articles
    python bulk_process_emails.py upload --input "data/bulk_articles.json"

    # Resume interrupted processing
    python bulk_process_emails.py parse --folder "C:\\path\\to\\emails" --resume
    python bulk_process_emails.py upload --input "data/bulk_articles.json" --resume
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Any
import traceback

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from email_file_reader import EmailFileReader
from progress_tracker import ProgressTracker
from batch_uploader import BatchUploader
from newsletter_parser_deterministic import DeterministicNewsletterParser
from entity_extractor import EntityExtractor
from validation_orchestrator import ValidationOrchestrator
from article_preparator import ArticlePreparator
from dealcloud_uploader import DealCloudUploader
from report_generator import ReportGenerator


class BulkEmailProcessor:
    """Orchestrates bulk email processing in two phases."""

    # Configuration constants
    ARTICLE_TYPE = "Actual"           # Mark as production data
    UPLOAD_BATCH_SIZE = 50            # Articles per upload batch
    RATE_LIMIT_DELAY = 1.0            # Seconds between batches
    MAX_RETRIES = 3                   # Retry attempts per batch
    PARSE_BATCH_SIZE = 100            # Emails per memory batch
    ENTITY_BATCH_SIZE = 10            # Articles per entity extraction batch
    CHECKPOINT_SAVE_INTERVAL = 10     # Save checkpoint every N files

    def __init__(self, logger=None):
        """
        Initialize the Bulk Email Processor.

        Args:
            logger: Optional logger instance
        """
        self.logger = logger or self._setup_logging()

    def _setup_logging(self):
        """Set up logging for the bulk processor."""
        today = datetime.now().strftime("%Y%m%d_%H%M%S")

        logger = logging.getLogger('bulk_processor')
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            os.makedirs("logs", exist_ok=True)

            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler = logging.FileHandler(f"logs/bulk_process_{today}.log")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        return logger

    def parse_phase(
        self,
        folder_path: str,
        output_path: str,
        checkpoint_path: str,
        resume: bool = False,
        limit: int = None
    ) -> Dict[str, Any]:
        """
        Phase 1: Parse .eml files and save articles to JSON.

        Args:
            folder_path: Path to folder containing .eml files
            output_path: Path to output JSON file
            checkpoint_path: Path to checkpoint file
            resume: Resume from checkpoint
            limit: Maximum emails to process (for testing)

        Returns:
            Statistics dict
        """
        start_time = datetime.now()
        self.logger.info("=" * 70)
        self.logger.info("PHASE 1: PARSE EMAILS AND EXTRACT ENTITIES")
        self.logger.info("=" * 70)

        # Initialize components
        reader = EmailFileReader(logger=self.logger)
        tracker = ProgressTracker(checkpoint_path, logger=self.logger)
        parser = DeterministicNewsletterParser(logger=self.logger)
        extractor = EntityExtractor(logger=self.logger)
        validator = ValidationOrchestrator(logger=self.logger)
        preparator = ArticlePreparator(article_type=self.ARTICLE_TYPE, logger=self.logger)

        # Load checkpoint if resuming
        if resume:
            tracker.load_checkpoint()
        else:
            tracker.reset()

        # Scan folder for .eml files
        self.logger.info(f"Scanning folder: {folder_path}")
        all_files = reader.scan_folder(folder_path)

        if limit:
            all_files = all_files[:limit]
            self.logger.info(f"Limited to {limit} files")

        # Filter out already processed files
        remaining_files = tracker.get_remaining_files(all_files) if resume else all_files

        tracker.checkpoint_data['total_files'] = len(all_files)
        tracker.save_checkpoint()

        if not remaining_files:
            self.logger.info("No files to process")
            return self._generate_parse_stats(tracker, start_time, output_path, checkpoint_path)

        self.logger.info(f"Processing {len(remaining_files)} files...")

        # Create or append to output file
        output_mode = 'a' if resume and os.path.exists(output_path) else 'w'
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

        # Track statistics
        total_articles = 0
        total_entities = {'hotels': 0, 'companies': 0, 'contacts': 0}
        total_matched = {'hotels': 0, 'companies': 0, 'contacts': 0}
        files_processed = 0

        # Process files in batches (for memory management)
        with open(output_path, output_mode, encoding='utf-8') as out_file:
            # If starting fresh, write opening bracket
            if output_mode == 'w':
                out_file.write('[\n')

            for i, file_path in enumerate(remaining_files):
                try:
                    # Read email (supports both .eml and .msg)
                    from_, subject, date, body_text, body_html = reader.read_email_file(file_path)

                    # Parse newsletter (pass all parameters)
                    articles = parser.parse_newsletter(from_, subject, date, body_text, body_html)

                    if not articles:
                        self.logger.warning(f"No articles extracted from {os.path.basename(file_path)}")
                        tracker.mark_processed(file_path)
                        continue

                    # Extract entities in batches
                    articles_with_entities = extractor.extract_from_articles_batched(
                        articles,
                        batch_size=self.ENTITY_BATCH_SIZE
                    )

                    # Validate entities
                    validated_articles = validator.validate_articles(articles_with_entities)

                    # Add source metadata to articles
                    for article in validated_articles:
                        article['source_subject'] = subject
                        article['source_date'] = date
                        article['source_from'] = from_

                    # Prepare for DealCloud
                    prepared_articles = preparator.prepare_articles(validated_articles)

                    # Write articles to JSON (append mode)
                    for article in prepared_articles:
                        # Add comma if not first article
                        if total_articles > 0 or output_mode == 'a':
                            out_file.write(',\n')

                        json.dump(article, out_file, indent=2, ensure_ascii=False)
                        total_articles += 1

                        # Track entity stats
                        if article.get('Hotels'):
                            total_entities['hotels'] += len(article['Hotels'])
                        if article.get('Companies'):
                            total_entities['companies'] += len(article['Companies'])
                        if article.get('Contacts'):
                            total_entities['contacts'] += len(article['Contacts'])

                    # Mark as processed
                    tracker.mark_processed(file_path)
                    files_processed += 1

                    # Save checkpoint periodically
                    if files_processed % self.CHECKPOINT_SAVE_INTERVAL == 0:
                        tracker.update_statistics({
                            'emails_read': files_processed,
                            'articles_extracted': total_articles,
                            'hotels_extracted': total_entities['hotels'],
                            'companies_extracted': total_entities['companies'],
                            'contacts_extracted': total_entities['contacts']
                        })
                        tracker.save_checkpoint()
                        self.logger.info(f"Progress: {files_processed}/{len(remaining_files)} files, {total_articles} articles")

                except Exception as e:
                    self.logger.error(f"Error processing {file_path}: {e}")
                    self.logger.debug(traceback.format_exc())
                    tracker.mark_failed(file_path, str(e))
                    continue

            # Close JSON array
            out_file.write('\n]\n')

        # Final checkpoint save
        tracker.update_statistics({
            'emails_read': files_processed,
            'articles_extracted': total_articles,
            'hotels_extracted': total_entities['hotels'],
            'companies_extracted': total_entities['companies'],
            'contacts_extracted': total_entities['contacts']
        })
        tracker.save_checkpoint()

        end_time = datetime.now()
        self.logger.info("=" * 70)
        self.logger.info("PARSE PHASE COMPLETE")
        self.logger.info(f"Processed: {files_processed} files")
        self.logger.info(f"Extracted: {total_articles} articles")
        self.logger.info(f"Output: {output_path}")
        self.logger.info("=" * 70)

        return self._generate_parse_stats(tracker, start_time, output_path, checkpoint_path, end_time)

    def upload_phase(
        self,
        input_path: str,
        checkpoint_path: str,
        resume: bool = False
    ) -> Dict[str, Any]:
        """
        Phase 2: Upload articles to DealCloud in batches.

        Args:
            input_path: Path to JSON file with prepared articles
            checkpoint_path: Path to upload checkpoint file
            resume: Resume from checkpoint

        Returns:
            Statistics dict
        """
        start_time = datetime.now()
        self.logger.info("=" * 70)
        self.logger.info("PHASE 2: UPLOAD TO DEALCLOUD")
        self.logger.info("=" * 70)

        # Load articles from JSON
        self.logger.info(f"Loading articles from {input_path}")
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                articles = json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load articles: {e}")
            raise

        total_articles = len(articles)
        self.logger.info(f"Loaded {total_articles} articles")

        # Initialize uploader
        dealcloud_uploader = DealCloudUploader(logger=self.logger)

        # Initialize batch uploader
        batch_uploader = BatchUploader(
            dealcloud_uploader=dealcloud_uploader,
            batch_size=self.UPLOAD_BATCH_SIZE,
            rate_limit_delay=self.RATE_LIMIT_DELAY,
            max_retries=self.MAX_RETRIES,
            logger=self.logger
        )

        # Upload in batches
        upload_stats = batch_uploader.upload_in_batches(
            articles=articles,
            checkpoint_path=checkpoint_path,
            resume=resume
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        self.logger.info("=" * 70)
        self.logger.info("UPLOAD PHASE COMPLETE")
        self.logger.info(f"Uploaded: {upload_stats['uploaded']}/{total_articles} articles")
        self.logger.info(f"Success Rate: {upload_stats['success_rate']:.1f}%")
        self.logger.info("=" * 70)

        # Add timing info
        upload_stats['start_time'] = start_time.isoformat()
        upload_stats['end_time'] = end_time.isoformat()
        upload_stats['duration_seconds'] = duration
        upload_stats['input_file'] = input_path
        upload_stats['checkpoint_file'] = checkpoint_path

        return upload_stats

    def _generate_parse_stats(
        self,
        tracker: ProgressTracker,
        start_time: datetime,
        output_path: str,
        checkpoint_path: str,
        end_time: datetime = None
    ) -> Dict[str, Any]:
        """Generate statistics for parse phase."""
        if end_time is None:
            end_time = datetime.now()

        duration = (end_time - start_time).total_seconds()
        checkpoint_data = tracker.checkpoint_data
        stats_data = checkpoint_data.get('statistics', {})

        stats = {
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': duration,
            'total_files': checkpoint_data.get('total_files', 0),
            'processed_files': checkpoint_data.get('processed_files', 0),
            'failed_files': len(checkpoint_data.get('failed_files', [])),
            'skipped_files': checkpoint_data.get('total_files', 0) - checkpoint_data.get('processed_files', 0),
            'articles_extracted': stats_data.get('articles_extracted', 0),
            'articles_with_entities': stats_data.get('articles_extracted', 0),  # Assume all have entities
            'hotels_extracted': stats_data.get('hotels_extracted', 0),
            'companies_extracted': stats_data.get('companies_extracted', 0),
            'contacts_extracted': stats_data.get('contacts_extracted', 0),
            'hotels_matched': stats_data.get('entities_matched', 0),  # Placeholder
            'companies_matched': 0,
            'contacts_matched': 0,
            'hotel_match_rate': 0,
            'company_match_rate': 0,
            'contact_match_rate': 0,
            'output_file': output_path,
            'checkpoint_file': checkpoint_path
        }

        if checkpoint_data.get('failed_files'):
            stats['failed_file_details'] = checkpoint_data['failed_files']

        return stats


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Bulk Email Processor for DLRScanner",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='phase', help='Processing phase')

    # Parse phase
    parse_parser = subparsers.add_parser('parse', help='Parse emails and save locally')
    parse_parser.add_argument('--folder', required=True, help='Path to folder containing .eml files')
    parse_parser.add_argument('--output', help='Output JSON file path (default: data/bulk_articles_YYYYMMDD_HHMMSS.json)')
    parse_parser.add_argument('--checkpoint', default='data/bulk_checkpoint.json', help='Checkpoint file path')
    parse_parser.add_argument('--resume', action='store_true', help='Resume from checkpoint')
    parse_parser.add_argument('--limit', type=int, help='Maximum emails to process (for testing)')

    # Upload phase
    upload_parser = subparsers.add_parser('upload', help='Upload previously parsed articles')
    upload_parser.add_argument('--input', required=True, help='Input JSON file path')
    upload_parser.add_argument('--checkpoint', default='data/upload_checkpoint.json', help='Upload checkpoint file path')
    upload_parser.add_argument('--resume', action='store_true', help='Resume from checkpoint')

    args = parser.parse_args()

    if not args.phase:
        parser.print_help()
        sys.exit(1)

    # Initialize processor
    processor = BulkEmailProcessor()
    report_generator = ReportGenerator()

    try:
        if args.phase == 'parse':
            # Generate default output path if not provided
            if not args.output:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                args.output = f"data/bulk_articles_{timestamp}.json"

            # Run parse phase
            stats = processor.parse_phase(
                folder_path=args.folder,
                output_path=args.output,
                checkpoint_path=args.checkpoint,
                resume=args.resume,
                limit=args.limit
            )

            # Generate report
            json_path, text_path = report_generator.generate_bulk_parse_report(stats)
            print(f"\nReport saved to:")
            print(f"  - {json_path}")
            print(f"  - {text_path}")

        elif args.phase == 'upload':
            # Run upload phase
            stats = processor.upload_phase(
                input_path=args.input,
                checkpoint_path=args.checkpoint,
                resume=args.resume
            )

            # Generate report
            json_path, text_path = report_generator.generate_bulk_upload_report(stats)
            print(f"\nReport saved to:")
            print(f"  - {json_path}")
            print(f"  - {text_path}")

    except KeyboardInterrupt:
        print("\n\nProcessing interrupted by user. Progress has been saved.")
        print("Run with --resume to continue from where you left off.")
        sys.exit(1)
    except Exception as e:
        processor.logger.error(f"Fatal error: {e}")
        processor.logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()
