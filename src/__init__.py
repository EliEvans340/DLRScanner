"""
DLRScanner - Hotel Industry Newsletter Scanner

Scans daily hotel industry newsletters, extracts articles,
identifies hotels/companies/contacts, validates against DealCloud,
and prepares Article records.
"""

from .dlr_scanner import DLRScanner
from .mailgun_fetcher import MailgunFetcher, fetch_newsletters
from .newsletter_parser import NewsletterParser, parse_newsletter_email
from .entity_extractor import EntityExtractor, extract_article_entities
from .validation_orchestrator import ValidationOrchestrator
from .article_preparator import ArticlePreparator, prepare_for_dealcloud, export_articles
from .report_generator import ReportGenerator, generate_report

__version__ = "1.0.0"

__all__ = [
    "DLRScanner",
    "MailgunFetcher",
    "fetch_newsletters",
    "NewsletterParser",
    "parse_newsletter_email",
    "EntityExtractor",
    "extract_article_entities",
    "ValidationOrchestrator",
    "ArticlePreparator",
    "prepare_for_dealcloud",
    "export_articles",
    "ReportGenerator",
    "generate_report"
]
