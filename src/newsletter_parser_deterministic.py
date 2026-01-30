"""
Deterministic Newsletter Parser for DLRScanner

Uses pattern matching to parse Daily Lodging Report newsletters.
Much faster than AI-based parsing (~50-150x speed improvement).
"""

import os
import re
import logging
from datetime import datetime
import typing_extensions as typing


class ArticleInfo(typing.TypedDict):
    """Schema for a parsed article."""
    article_number: int
    headline: str
    article_text: str


class DeterministicNewsletterParser:
    """Fast pattern-based parser for Daily Lodging Report newsletters."""

    def __init__(self, logger=None):
        """
        Initialize the Deterministic Newsletter Parser.

        Args:
            logger: Optional logger instance
        """
        self.logger = logger or self._setup_logging()

        # Statistics
        self.stats = {
            "newsletters_processed": 0,
            "articles_extracted": 0,
            "failed_processing": 0,
            "failed_newsletters": []
        }

        # Patterns for filtering footer content
        self.footer_patterns = [
            r"Did someone forward",
            r"Pick Your Subscription",
            r"Make Sure Your",
            r"Manage preferences",
            r"Skift,",
            r"Hotel and Lodging Performance",
            r"https?://[^\s]+\.(jpg|jpeg|png|gif)",  # Image URLs
            r"View this email in your browser",
            r"Unsubscribe from this list",
            r"Update subscription preferences"
        ]

        # Section headers to skip when standalone
        self.section_headers = [
            "Personnel News",
            "Market Update",
            "Industry News"
        ]

    def _setup_logging(self):
        """Set up logging for the parser."""
        today = datetime.now().strftime("%Y%m%d")

        logger = logging.getLogger('newsletter_parser_deterministic')
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            os.makedirs("logs", exist_ok=True)

            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler = logging.FileHandler(f"logs/newsletter_parser_deterministic_{today}.log")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def _is_footer_content(self, text):
        """Check if text matches footer patterns."""
        for pattern in self.footer_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _is_section_header(self, text):
        """Check if text is a standalone section header."""
        text_stripped = text.strip()
        if len(text_stripped) > 100:  # Too long to be a header
            return False
        return text_stripped in self.section_headers

    def _generate_headline(self, article_text):
        """
        Generate a headline from article text.

        Tries to extract the first sentence or first 80-100 characters.
        """
        if not article_text:
            return "Unknown Article"

        # Try to get first sentence (up to first period, exclamation, or question mark)
        sentence_match = re.match(r'^([^.!?]+[.!?])', article_text)
        if sentence_match:
            headline = sentence_match.group(1).strip()
            if len(headline) <= 150:
                return headline

        # Fall back to first 100 characters
        if len(article_text) > 100:
            return article_text[:100].strip() + "..."

        return article_text.strip()

    def _find_start_marker(self, body_text):
        """
        Find the start of the Daily Lodging Report content.

        Returns the index after "Daily Lodging Report for [DATE]"
        """
        # Look for the start marker
        pattern = r"Daily Lodging Report for\s+\w+\s+\d{1,2},\s+\d{4}"
        match = re.search(pattern, body_text, re.IGNORECASE)

        if match:
            return match.end()

        # Fallback: try simpler pattern
        pattern_simple = r"Daily Lodging Report"
        match_simple = re.search(pattern_simple, body_text, re.IGNORECASE)

        if match_simple:
            return match_simple.end()

        # If no marker found, start from beginning
        self.logger.warning("Could not find 'Daily Lodging Report' marker, parsing from start")
        return 0

    def _skip_header_paragraphs(self, paragraphs):
        """
        Skip the first few header paragraphs (editor name, market summary).

        Returns the index to start reading articles from.
        """
        skip_count = 0

        for i, para in enumerate(paragraphs):
            para_lower = para.lower()

            # Skip editor line
            if "alan r. woinski" in para_lower or "editor" in para_lower:
                skip_count = i + 1
                continue

            # Skip market summary (contains stock market info)
            if any(marker in para_lower for marker in ["djia", "lodging stocks", "market"]):
                skip_count = i + 1
                continue

            # Stop skipping once we hit substantive content
            if len(para) > 100 and skip_count > 0:
                break

        return skip_count

    def _is_valid_article(self, text):
        """
        Check if a paragraph is a valid article.

        Articles should:
        - Be at least 100 characters
        - Not be footer content
        - Not be standalone section headers
        """
        if not text or len(text.strip()) < 100:
            return False

        if self._is_footer_content(text):
            return False

        if self._is_section_header(text):
            return False

        return True

    def parse_newsletter(self, from_, subject, date, body_text, body_html=None):
        """
        Parse a single newsletter email into articles using pattern matching.

        Args:
            from_: Sender email address
            subject: Email subject
            date: Email date
            body_text: Plain text body
            body_html: HTML body (optional, used if text is empty)

        Returns:
            List of ArticleInfo dicts with article_number, headline, article_text
        """
        self.logger.info(f"Parsing newsletter (deterministic): {subject}")

        # Use text body, fall back to HTML if empty
        body = body_text if body_text and body_text.strip() else body_html

        if not body:
            self.logger.warning(f"Empty newsletter body for: {subject}")
            return []

        try:
            # Step 1: Find start marker
            start_pos = self._find_start_marker(body)
            content = body[start_pos:]

            # Step 2: Split by double newlines (article separator)
            paragraphs = re.split(r'\n\s*\n', content)

            # Clean up paragraphs (strip whitespace)
            paragraphs = [p.strip() for p in paragraphs if p.strip()]

            # Step 3: Skip header paragraphs
            article_start_index = self._skip_header_paragraphs(paragraphs)
            article_paragraphs = paragraphs[article_start_index:]

            # Step 4: Filter out footer content and invalid articles
            # Stop processing once we hit "Hotel and Lodging Performance" section
            valid_articles = []
            for para in article_paragraphs:
                # Check if we've hit the footer section - stop processing entirely
                if "Hotel and Lodging Performance" in para:
                    self.logger.info("Reached 'Hotel and Lodging Performance' section - stopping article extraction")
                    break

                if self._is_valid_article(para):
                    valid_articles.append(para)

            # Step 5: Generate headlines and create ArticleInfo objects
            articles = []
            for i, article_text in enumerate(valid_articles, start=1):
                headline = self._generate_headline(article_text)

                article = {
                    "article_number": i,
                    "headline": headline,
                    "article_text": article_text,
                    "source_subject": subject,
                    "source_from": from_,
                    "source_date": date
                }
                articles.append(article)

            # Update statistics
            self.stats["newsletters_processed"] += 1
            self.stats["articles_extracted"] += len(articles)

            self.logger.info(f"Extracted {len(articles)} articles from: {subject}")

            return articles

        except Exception as e:
            self.logger.error(f"Error processing newsletter {subject}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self.stats["failed_processing"] += 1
            self.stats["failed_newsletters"].append(f"{subject} - Processing error")
            return []

    def parse_newsletters(self, emails):
        """
        Parse multiple newsletter emails.

        Args:
            emails: List of tuples (from_, subject, date, body_text, body_html)

        Returns:
            List of all extracted articles
        """
        all_articles = []

        for from_, subject, date, body_text, body_html in emails:
            articles = self.parse_newsletter(from_, subject, date, body_text, body_html)
            all_articles.extend(articles)

        self.logger.info(f"Total articles extracted: {len(all_articles)} from {len(emails)} newsletters")
        return all_articles

    def get_stats(self):
        """Get processing statistics."""
        return self.stats.copy()


# Convenience function
def parse_newsletter_email(from_, subject, date, body_text, body_html=None):
    """
    Convenience function to parse a single newsletter.

    Returns:
        List of ArticleInfo dicts
    """
    parser = DeterministicNewsletterParser()
    return parser.parse_newsletter(from_, subject, date, body_text, body_html)
