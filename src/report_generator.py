"""
Report Generator for DLRScanner

Generates processing reports for newsletter scanning operations.
"""

import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv


class ReportGenerator:
    """Generates processing reports."""

    def __init__(self, logger=None):
        """
        Initialize the Report Generator.

        Args:
            logger: Optional logger instance
        """
        load_dotenv()
        self.logger = logger or self._setup_logging()

    def _setup_logging(self):
        """Set up logging for the report generator."""
        today = datetime.now().strftime("%Y%m%d")

        logger = logging.getLogger('report_generator')
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            os.makedirs("logs", exist_ok=True)

            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler = logging.FileHandler(f"logs/report_generator_{today}.log")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def generate_processing_report(
        self,
        emails_fetched,
        parser_stats,
        extractor_stats,
        validation_summary,
        prepared_summary,
        start_time,
        end_time,
        upload_stats=None
    ):
        """
        Generate a comprehensive processing report.

        Args:
            emails_fetched: Number of emails fetched
            parser_stats: Stats from NewsletterParser
            extractor_stats: Stats from EntityExtractor
            validation_summary: Summary from ValidationOrchestrator
            prepared_summary: Summary from ArticlePreparator
            start_time: Processing start time
            end_time: Processing end time
            upload_stats: Optional stats from DealCloudUploader

        Returns:
            Report dict
        """
        duration = (end_time - start_time).total_seconds()

        report = {
            "report_generated_at": datetime.now().isoformat(),
            "processing_summary": {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": round(duration, 2)
            },
            "email_fetching": {
                "emails_fetched": emails_fetched
            },
            "newsletter_parsing": parser_stats,
            "entity_extraction": extractor_stats,
            "validation": validation_summary,
            "article_preparation": prepared_summary
        }

        if upload_stats:
            report["dealcloud_upload"] = upload_stats

        return report

    def format_report_text(self, report):
        """
        Format report as human-readable text.

        Args:
            report: Report dict

        Returns:
            Formatted text string
        """
        lines = []
        lines.append("=" * 60)
        lines.append("DLRScanner Processing Report")
        lines.append("=" * 60)
        lines.append("")

        # Processing summary
        ps = report.get("processing_summary", {})
        lines.append("PROCESSING SUMMARY")
        lines.append("-" * 40)
        lines.append(f"  Start Time:     {ps.get('start_time', 'N/A')}")
        lines.append(f"  End Time:       {ps.get('end_time', 'N/A')}")
        lines.append(f"  Duration:       {ps.get('duration_seconds', 0)} seconds")
        lines.append("")

        # Email fetching
        ef = report.get("email_fetching", {})
        lines.append("EMAIL FETCHING")
        lines.append("-" * 40)
        lines.append(f"  Emails Fetched: {ef.get('emails_fetched', 0)}")
        lines.append("")

        # Newsletter parsing
        np = report.get("newsletter_parsing", {})
        lines.append("NEWSLETTER PARSING")
        lines.append("-" * 40)
        lines.append(f"  Newsletters Processed: {np.get('newsletters_processed', 0)}")
        lines.append(f"  Articles Extracted:    {np.get('articles_extracted', 0)}")
        lines.append(f"  Failed Processing:     {np.get('failed_processing', 0)}")
        if np.get('failed_newsletters'):
            lines.append(f"  Failed Newsletters:")
            for fn in np.get('failed_newsletters', []):
                lines.append(f"    - {fn}")
        lines.append("")

        # Entity extraction
        ee = report.get("entity_extraction", {})
        lines.append("ENTITY EXTRACTION")
        lines.append("-" * 40)
        lines.append(f"  Articles Processed:    {ee.get('articles_processed', 0)}")
        lines.append(f"  Hotels Extracted:      {ee.get('hotels_extracted', 0)}")
        lines.append(f"  Companies Extracted:   {ee.get('companies_extracted', 0)}")
        lines.append(f"  Contacts Extracted:    {ee.get('contacts_extracted', 0)}")
        lines.append(f"  Failed Processing:     {ee.get('failed_processing', 0)}")
        lines.append("")

        # Validation
        v = report.get("validation", {})
        lines.append("VALIDATION RESULTS")
        lines.append("-" * 40)
        lines.append(f"  Hotels:    {v.get('matched_hotels', 0)}/{v.get('total_hotels', 0)} matched "
                    f"({v.get('hotel_match_rate', 0)*100:.1f}%)")
        lines.append(f"  Companies: {v.get('matched_companies', 0)}/{v.get('total_companies', 0)} matched "
                    f"({v.get('company_match_rate', 0)*100:.1f}%)")
        lines.append(f"  Contacts:  {v.get('matched_contacts', 0)}/{v.get('total_contacts', 0)} matched "
                    f"({v.get('contact_match_rate', 0)*100:.1f}%)")
        lines.append("")

        # Article preparation
        ap = report.get("article_preparation", {})
        lines.append("PREPARED ARTICLES")
        lines.append("-" * 40)
        lines.append(f"  Total Articles:           {ap.get('total_articles', 0)}")
        lines.append(f"  With Hotel References:    {ap.get('articles_with_hotels', 0)}")
        lines.append(f"  With Company References:  {ap.get('articles_with_companies', 0)}")
        lines.append(f"  With Contact References:  {ap.get('articles_with_contacts', 0)}")
        lines.append(f"  Total Hotel Refs:         {ap.get('total_hotel_references', 0)}")
        lines.append(f"  Total Company Refs:       {ap.get('total_company_references', 0)}")
        lines.append(f"  Total Contact Refs:       {ap.get('total_contact_references', 0)}")
        if ap.get('unique_sources'):
            lines.append(f"  Sources:")
            for src in ap.get('unique_sources', []):
                lines.append(f"    - {src[:60]}...")
        lines.append("")

        # DealCloud upload (if performed)
        upload = report.get("dealcloud_upload")
        if upload:
            lines.append("DEALCLOUD UPLOAD")
            lines.append("-" * 40)
            lines.append(f"  Total Articles:     {upload.get('total_articles', 0)}")
            lines.append(f"  Successfully Uploaded: {upload.get('uploaded', 0)}")
            lines.append(f"  Failed:             {upload.get('failed', 0)}")
            lines.append(f"  Success Rate:       {upload.get('success_rate', 0):.1f}%")
            if upload.get('error'):
                lines.append(f"  Error: {upload.get('error')}")
            lines.append("")

        lines.append("=" * 60)

        return "\n".join(lines)

    def save_report(self, report, output_dir="logs"):
        """
        Save report to files (JSON and text).

        Args:
            report: Report dict
            output_dir: Output directory

        Returns:
            Tuple of (json_path, text_path)
        """
        os.makedirs(output_dir, exist_ok=True)
        today = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save JSON report
        json_path = os.path.join(output_dir, f"report_{today}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # Save text report
        text_path = os.path.join(output_dir, f"report_{today}.txt")
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(self.format_report_text(report))

        self.logger.info(f"Report saved to {json_path} and {text_path}")
        return json_path, text_path

    def print_report(self, report):
        """
        Print report to console.

        Args:
            report: Report dict
        """
        print(self.format_report_text(report))


# Convenience function
def generate_report(
    emails_fetched,
    parser_stats,
    extractor_stats,
    validation_summary,
    prepared_summary,
    start_time,
    end_time,
    save=True,
    print_console=True
):
    """
    Convenience function to generate and output a processing report.

    Returns:
        Report dict
    """
    generator = ReportGenerator()

    report = generator.generate_processing_report(
        emails_fetched=emails_fetched,
        parser_stats=parser_stats,
        extractor_stats=extractor_stats,
        validation_summary=validation_summary,
        prepared_summary=prepared_summary,
        start_time=start_time,
        end_time=end_time
    )

    if save:
        generator.save_report(report)

    if print_console:
        generator.print_report(report)

    return report
