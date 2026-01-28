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

from mailgun_fetcher import MailgunFetcher
from newsletter_parser import NewsletterParser
from entity_extractor import EntityExtractor
from validation_orchestrator import ValidationOrchestrator
from article_preparator import ArticlePreparator
from report_generator import ReportGenerator


class DLRScanner:
    """Main orchestrator for the DLRScanner pipeline."""

    def __init__(self, logger=None):
        """
        Initialize DLRScanner with all components.

        Args:
            logger: Optional logger instance
        """
        load_dotenv()
        self.logger = logger or self._setup_logging()

        # Initialize components lazily
        self._fetcher = None
        self._parser = None
        self._extractor = None
        self._validator = None
        self._preparator = None
        self._reporter = None

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
            self._fetcher = MailgunFetcher(logger=self.logger)
        return self._fetcher

    @property
    def parser(self):
        if self._parser is None:
            self._parser = NewsletterParser(logger=self.logger)
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
            self._preparator = ArticlePreparator(logger=self.logger)
        return self._preparator

    @property
    def reporter(self):
        if self._reporter is None:
            self._reporter = ReportGenerator(logger=self.logger)
        return self._reporter

    def run(
        self,
        days_back=None,
        limit=None,
        sender_filter=None,
        skip_validation=False,
        output_path=None,
        save_report=True
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
        self.logger.info("Step 3: Extracting entities from articles")
        articles_with_entities = self.extractor.extract_from_articles(articles)
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

        # Step 6: Generate report
        end_time = datetime.now()
        self.logger.info("Step 6: Generating report")

        report = self.reporter.generate_processing_report(
            emails_fetched=emails_fetched,
            parser_stats=parser_stats,
            extractor_stats=extractor_stats,
            validation_summary=validation_summary,
            prepared_summary=prepared_summary,
            start_time=start_time,
            end_time=end_time
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

    args = parser.parse_args()

    # Run the scanner
    scanner = DLRScanner()
    articles, report = scanner.run(
        days_back=args.days_back,
        limit=args.limit,
        skip_validation=args.no_validate,
        output_path=args.output,
        save_report=not args.no_report
    )

    return 0 if articles else 1


if __name__ == "__main__":
    sys.exit(main())
