"""
DLRScanner - Main Entry Point

Scans daily hotel industry newsletters, extracts articles,
identifies hotels/companies/contacts, validates against DealCloud,
and prepares Article records.

Usage:
    python dlr_scanner.py [--days-back N] [--limit N] [--no-validate] [--output PATH]
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from dotenv import load_dotenv

# Add src directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gmx_fetcher import GmxFetcher
from newsletter_parser import NewsletterParser
from newsletter_parser_deterministic import DeterministicNewsletterParser
from entity_extractor import EntityExtractor
from validation_orchestrator import ValidationOrchestrator
from article_preparator import ArticlePreparator
from report_generator import ReportGenerator
from dealcloud_uploader import DealCloudUploader


class DLRScanner:
    """Main orchestrator for the DLRScanner pipeline."""

    def __init__(self, use_deterministic_parser=None, batch_size=None, article_type=None, logger=None):
        """
        Initialize DLRScanner with all components.

        Args:
            use_deterministic_parser: Use pattern-based parser (default: True, or from env)
            batch_size: Number of articles per batch for entity extraction (default: 10, or from env)
            article_type: Type of articles - "Actual" or "Testing" (default from ARTICLE_TYPE env var or "Testing")
            logger: Optional logger instance
        """
        load_dotenv()
        self.logger = logger or self._setup_logging()

        # Configuration
        if use_deterministic_parser is None:
            use_deterministic_parser = os.getenv('USE_DETERMINISTIC_PARSER', 'true').lower() == 'true'
        self.use_deterministic_parser = use_deterministic_parser

        if batch_size is None:
            batch_size = int(os.getenv('ENTITY_EXTRACTION_BATCH_SIZE', '10'))
        self.batch_size = batch_size

        if article_type is None:
            article_type = os.getenv('ARTICLE_TYPE', 'Testing')
        self.article_type = article_type

        # Initialize components lazily
        self._fetcher = None
        self._parser = None
        self._extractor = None
        self._validator = None
        self._preparator = None
        self._reporter = None
        self._uploader = None

    def _setup_logging(self):
        """Set up logging for the scanner."""
        today = datetime.now().strftime("%Y%m%d")

        # Ensure logs directory exists
        os.makedirs("logs", exist_ok=True)

        logger = logging.getLogger('dlr_scanner')
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

            # File handler
            file_handler = logging.FileHandler(f"logs/dlr_scanner_{today}.log")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        return logger

    @property
    def fetcher(self):
        if self._fetcher is None:
            self._fetcher = GmxFetcher(logger=self.logger)
        return self._fetcher

    @property
    def parser(self):
        if self._parser is None:
            if self.use_deterministic_parser:
                self._parser = DeterministicNewsletterParser(logger=self.logger)
                self.logger.info("Using deterministic (pattern-based) newsletter parser")
            else:
                self._parser = NewsletterParser(logger=self.logger)
                self.logger.info("Using AI-based newsletter parser")
        return self._parser

    @property
    def extractor(self):
        if self._extractor is None:
            self._extractor = EntityExtractor(logger=self.logger)
        return self._extractor

    @property
    def validator(self):
        if self._validator is None:
            self._validator = ValidationOrchestrator(logger=self.logger)
        return self._validator

    @property
    def preparator(self):
        if self._preparator is None:
            self._preparator = ArticlePreparator(article_type=self.article_type, logger=self.logger)
        return self._preparator

    @property
    def reporter(self):
        if self._reporter is None:
            self._reporter = ReportGenerator(logger=self.logger)
        return self._reporter

    @property
    def uploader(self):
        if self._uploader is None:
            self._uploader = DealCloudUploader(logger=self.logger)
        return self._uploader

    def run(
        self,
        days_back=None,
        limit=None,
        sender_filter=None,
        skip_validation=False,
        output_path=None,
        save_report=True,
        upload=False
    ):
        """
        Run the full DLRScanner pipeline.

        Args:
            days_back: Days to look back for emails (default from env)
            limit: Max emails to fetch (default from env)
            sender_filter: List of sender addresses to filter
            skip_validation: Skip entity validation step
            output_path: Path for output JSON file
            save_report: Whether to save processing report
            upload: Upload articles to DealCloud

        Returns:
            Tuple of (prepared_articles, report)
        """
        start_time = datetime.now()
        self.logger.info("=" * 60)
        self.logger.info("Starting DLRScanner Pipeline")
        self.logger.info("=" * 60)

        # Load defaults from environment
        days_back = days_back or int(os.getenv('DAYS_BACK', 1))
        limit = limit or int(os.getenv('EMAIL_FETCH_COUNT', 10))

        # Parse sender filter from env if not provided
        if sender_filter is None:
            filter_str = os.getenv('NEWSLETTER_SOURCES', '')
            if filter_str:
                sender_filter = [s.strip() for s in filter_str.split(',') if s.strip()]

        # Step 1: Fetch emails
        self.logger.info(f"Step 1: Fetching emails (days_back={days_back}, limit={limit})")
        try:
            emails = self.fetcher.fetch_stored_emails(
                days_back=days_back,
                limit=limit,
                sender_filter=sender_filter
            )
            emails_fetched = len(emails)
            self.logger.info(f"Fetched {emails_fetched} emails")
        except Exception as e:
            self.logger.error(f"Error fetching emails: {e}")
            emails = []
            emails_fetched = 0

        if not emails:
            self.logger.warning("No emails to process")
            end_time = datetime.now()
            report = self._generate_empty_report(start_time, end_time)
            return [], report

        # Step 2: Parse newsletters into articles
        self.logger.info("Step 2: Parsing newsletters into articles")
        articles = self.parser.parse_newsletters(emails)
        parser_stats = self.parser.get_stats()
        self.logger.info(f"Extracted {len(articles)} articles")

        if not articles:
            self.logger.warning("No articles extracted")
            end_time = datetime.now()
            report = self._generate_empty_report(start_time, end_time, emails_fetched, parser_stats)
            return [], report

        # Step 3: Extract entities from articles
        self.logger.info(f"Step 3: Extracting entities from articles (batch_size={self.batch_size})")
        articles_with_entities = self.extractor.extract_from_articles_batched(articles, batch_size=self.batch_size)
        extractor_stats = self.extractor.get_stats()
        self.logger.info(f"Entity extraction complete")

        # Step 4: Validate entities (optional)
        if skip_validation:
            self.logger.info("Step 4: Skipping validation (--no-validate)")
            validated_articles = articles_with_entities
            # Add empty entry IDs
            for article in validated_articles:
                article["hotel_entry_ids"] = [None] * len(article.get("hotels", []))
                article["company_entry_ids"] = [None] * len(article.get("companies", []))
                article["contact_entry_ids"] = [None] * len(article.get("contacts", []))
            validation_summary = {
                "total_hotels": 0, "matched_hotels": 0, "hotel_match_rate": 0,
                "total_companies": 0, "matched_companies": 0, "company_match_rate": 0,
                "total_contacts": 0, "matched_contacts": 0, "contact_match_rate": 0
            }
        else:
            self.logger.info("Step 4: Validating entities against DealCloud")
            validated_articles = self.validator.validate_articles(articles_with_entities)
            validation_summary = self.validator.get_validation_summary(validated_articles)
            self.logger.info(f"Validation complete")

        # Step 5: Prepare articles for DealCloud
        self.logger.info("Step 5: Preparing articles for DealCloud")
        prepared_articles = self.preparator.prepare_articles(validated_articles)
        prepared_summary = self.preparator.get_summary(prepared_articles)

        # Export to JSON
        export_path = self.preparator.export_to_json(prepared_articles, output_path)
        self.logger.info(f"Exported articles to {export_path}")

        # Step 6: Upload to DealCloud (optional)
        upload_stats = None
        if upload:
            self.logger.info("Step 6: Uploading articles to DealCloud")
            try:
                upload_stats = self.uploader.upload_articles(prepared_articles)
                self.logger.info(f"Upload complete: {upload_stats['uploaded']}/{upload_stats['total_articles']} articles uploaded")
            except Exception as e:
                self.logger.error(f"Upload failed: {str(e)}")
                upload_stats = {
                    'total_articles': len(prepared_articles),
                    'uploaded': 0,
                    'failed': len(prepared_articles),
                    'entry_ids': [],
                    'success_rate': 0,
                    'error': str(e)
                }

        # Step 7: Generate report
        end_time = datetime.now()
        step_num = 7 if upload else 6
        self.logger.info(f"Step {step_num}: Generating report")

        report = self.reporter.generate_processing_report(
            emails_fetched=emails_fetched,
            parser_stats=parser_stats,
            extractor_stats=extractor_stats,
            validation_summary=validation_summary,
            prepared_summary=prepared_summary,
            start_time=start_time,
            end_time=end_time,
            upload_stats=upload_stats
        )

        if save_report:
            self.reporter.save_report(report)
            self.reporter.print_report(report)

        self.logger.info("=" * 60)
        self.logger.info("DLRScanner Pipeline Complete")
        self.logger.info("=" * 60)

        return prepared_articles, report

    def _generate_empty_report(self, start_time, end_time, emails_fetched=0, parser_stats=None):
        """Generate a report for empty/failed runs."""
        return self.reporter.generate_processing_report(
            emails_fetched=emails_fetched,
            parser_stats=parser_stats or {"newsletters_processed": 0, "articles_extracted": 0, "failed_processing": 0, "failed_newsletters": []},
            extractor_stats={"articles_processed": 0, "hotels_extracted": 0, "companies_extracted": 0, "contacts_extracted": 0, "failed_processing": 0, "failed_articles": []},
            validation_summary={"total_hotels": 0, "matched_hotels": 0, "hotel_match_rate": 0, "total_companies": 0, "matched_companies": 0, "company_match_rate": 0, "total_contacts": 0, "matched_contacts": 0, "contact_match_rate": 0},
            prepared_summary={"total_articles": 0, "articles_with_hotels": 0, "articles_with_companies": 0, "articles_with_contacts": 0, "total_hotel_references": 0, "total_company_references": 0, "total_contact_references": 0, "unique_sources": []},
            start_time=start_time,
            end_time=end_time
        )


def main():
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(
        description="DLRScanner - Scan hotel industry newsletters and extract article data"
    )
    parser.add_argument(
        '--days-back', '-d',
        type=int,
        default=None,
        help='Number of days to look back for emails (default: from DAYS_BACK env var or 1)'
    )
    parser.add_argument(
        '--limit', '-l',
        type=int,
        default=None,
        help='Maximum number of emails to fetch (default: from EMAIL_FETCH_COUNT env var or 10)'
    )
    parser.add_argument(
        '--no-validate',
        action='store_true',
        help='Skip entity validation step'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Output JSON file path (default: data/articles_YYYYMMDD.json)'
    )
    parser.add_argument(
        '--no-report',
        action='store_true',
        help='Do not save processing report'
    )
    parser.add_argument(
        '--use-ai-parser',
        action='store_true',
        help='Use AI-based parser instead of deterministic parser'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=None,
        help='Number of articles per batch for entity extraction (default: 10)'
    )
    parser.add_argument(
        '--type',
        type=str,
        choices=['Actual', 'Testing'],
        default=None,
        help='Article type: "Actual" for production, "Testing" for test data (default: from ARTICLE_TYPE env var or "Testing")'
    )
    parser.add_argument(
        '--upload',
        action='store_true',
        help='Upload articles to DealCloud after processing'
    )

    args = parser.parse_args()

    # Run the scanner
    scanner = DLRScanner(
        use_deterministic_parser=not args.use_ai_parser,
        batch_size=args.batch_size,
        article_type=args.type
    )
    articles, report = scanner.run(
        days_back=args.days_back,
        limit=args.limit,
        skip_validation=args.no_validate,
        output_path=args.output,
        save_report=not args.no_report,
        upload=args.upload
    )

    return 0 if articles else 1


if __name__ == "__main__":
    sys.exit(main())
