"""
Article Preparator for DLRScanner

Transforms validated articles into DealCloud Articles schema format.
"""

import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv


class ArticlePreparator:
    """Prepares articles for DealCloud upload."""

    # DealCloud Articles object field mapping
    DEALCLOUD_SCHEMA = {
        "ArticleText": "article_text",      # Full article content
        "Headline": "headline",              # Article headline
        "Hotels": "hotel_entry_ids",         # Multi-Reference to Hotel Entry IDs
        "Companies": "company_entry_ids",    # Multi-Reference to Company Entry IDs
        "Contacts": "contact_entry_ids",     # Multi-Reference to Contact Entry IDs
        "Source": "source_subject",          # Newsletter subject
        "PublishDate": "source_date"         # Newsletter date
    }

    def __init__(self, logger=None):
        """
        Initialize the Article Preparator.

        Args:
            logger: Optional logger instance
        """
        load_dotenv()
        self.logger = logger or self._setup_logging()

    def _setup_logging(self):
        """Set up logging for the preparator."""
        today = datetime.now().strftime("%Y%m%d")

        logger = logging.getLogger('article_preparator')
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            os.makedirs("logs", exist_ok=True)

            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler = logging.FileHandler(f"logs/article_preparator_{today}.log")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def _parse_date(self, date_str):
        """
        Parse date string to ISO format.

        Args:
            date_str: Date string in various formats

        Returns:
            ISO formatted date string or original string if parsing fails
        """
        if not date_str:
            return datetime.now().isoformat()

        # Common date formats to try
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%a, %d %b %Y %H:%M:%S %z",  # RFC 2822 (email format)
            "%a, %d %b %Y %H:%M:%S",
            "%d %b %Y %H:%M:%S",
            "%B %d, %Y",
            "%m/%d/%Y",
            "%d/%m/%Y"
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(str(date_str).strip(), fmt)
                return parsed.isoformat()
            except ValueError:
                continue

        # If all parsing fails, return as-is
        return str(date_str)

    def _filter_valid_ids(self, entry_ids):
        """
        Filter out None values from Entry ID list.

        Args:
            entry_ids: List of Entry IDs (may contain None)

        Returns:
            List of valid (non-None) Entry IDs
        """
        if not entry_ids:
            return []
        return [eid for eid in entry_ids if eid is not None]

    def prepare_article(self, article):
        """
        Transform a single article to DealCloud schema.

        Args:
            article: Validated article dict

        Returns:
            Dict in DealCloud Articles schema format
        """
        prepared = {
            "ArticleText": article.get("article_text", ""),
            "Headline": article.get("headline", ""),
            "Hotels": self._filter_valid_ids(article.get("hotel_entry_ids", [])),
            "Companies": self._filter_valid_ids(article.get("company_entry_ids", [])),
            "Contacts": self._filter_valid_ids(article.get("contact_entry_ids", [])),
            "Source": article.get("source_subject", ""),
            "PublishDate": self._parse_date(article.get("source_date"))
        }

        # Add metadata for tracking (not uploaded to DealCloud)
        prepared["_metadata"] = {
            "article_number": article.get("article_number"),
            "source_from": article.get("source_from"),
            "processed_at": datetime.now().isoformat(),
            "original_hotels": article.get("hotels", []),
            "original_companies": article.get("companies", []),
            "original_contacts": article.get("contacts", [])
        }

        return prepared

    def prepare_articles(self, articles):
        """
        Transform multiple articles to DealCloud schema.

        Args:
            articles: List of validated article dicts

        Returns:
            List of dicts in DealCloud Articles schema format
        """
        prepared_articles = []

        for article in articles:
            prepared = self.prepare_article(article)
            prepared_articles.append(prepared)

        self.logger.info(f"Prepared {len(prepared_articles)} articles for DealCloud")
        return prepared_articles

    def export_to_json(self, articles, output_path=None):
        """
        Export prepared articles to JSON file.

        Args:
            articles: List of prepared article dicts
            output_path: Output file path (default: data/articles_YYYYMMDD.json)

        Returns:
            Path to the output file
        """
        if output_path is None:
            today = datetime.now().strftime("%Y%m%d")
            os.makedirs("data", exist_ok=True)
            output_path = f"data/articles_{today}.json"

        # Prepare output structure
        output = {
            "exported_at": datetime.now().isoformat(),
            "total_articles": len(articles),
            "articles": articles
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Exported {len(articles)} articles to {output_path}")
        return output_path

    def get_summary(self, articles):
        """
        Get a summary of prepared articles.

        Args:
            articles: List of prepared article dicts

        Returns:
            Summary statistics dict
        """
        total = len(articles)
        with_hotels = sum(1 for a in articles if a.get("Hotels"))
        with_companies = sum(1 for a in articles if a.get("Companies"))
        with_contacts = sum(1 for a in articles if a.get("Contacts"))

        total_hotel_refs = sum(len(a.get("Hotels", [])) for a in articles)
        total_company_refs = sum(len(a.get("Companies", [])) for a in articles)
        total_contact_refs = sum(len(a.get("Contacts", [])) for a in articles)

        sources = set(a.get("Source", "") for a in articles if a.get("Source"))

        return {
            "total_articles": total,
            "articles_with_hotels": with_hotels,
            "articles_with_companies": with_companies,
            "articles_with_contacts": with_contacts,
            "total_hotel_references": total_hotel_refs,
            "total_company_references": total_company_refs,
            "total_contact_references": total_contact_refs,
            "unique_sources": list(sources)
        }


# Convenience functions
def prepare_for_dealcloud(articles):
    """
    Convenience function to prepare articles for DealCloud.

    Args:
        articles: List of validated article dicts

    Returns:
        List of prepared articles in DealCloud schema
    """
    preparator = ArticlePreparator()
    return preparator.prepare_articles(articles)


def export_articles(articles, output_path=None):
    """
    Convenience function to export articles to JSON.

    Args:
        articles: List of article dicts (validated or prepared)
        output_path: Optional output file path

    Returns:
        Path to the exported file
    """
    preparator = ArticlePreparator()

    # Check if articles are already prepared
    if articles and "ArticleText" in articles[0]:
        prepared = articles
    else:
        prepared = preparator.prepare_articles(articles)

    return preparator.export_to_json(prepared, output_path)
