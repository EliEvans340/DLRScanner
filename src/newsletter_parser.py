"""
Newsletter Parser for DLRScanner

Uses Gemini AI to parse newsletter emails into individual articles.
"""

import os
import json
import logging
import traceback
from datetime import datetime
import google.generativeai as genai
import typing_extensions as typing
from dotenv import load_dotenv


class ArticleInfo(typing.TypedDict):
    """Schema for a parsed article."""
    article_number: int
    headline: str
    article_text: str


class NewsletterParser:
    def __init__(self, api_key=None, model_name=None, instructions_path=None, logger=None):
        """
        Initialize the Newsletter Parser.

        Args:
            api_key: Google API key (or from GOOGLE_API_KEY env var)
            model_name: Gemini model to use (or from GEMINI_MODEL env var)
            instructions_path: Path to parser instructions file
            logger: Optional logger instance
        """
        load_dotenv()

        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("Google API key is required. Set GOOGLE_API_KEY environment variable.")

        # Configure Gemini
        genai.configure(api_key=self.api_key)

        # Load instructions
        if instructions_path is None:
            instructions_path = os.path.join(
                os.path.dirname(__file__), '..', 'config', 'newsletter_parser_instructions.txt'
            )
        self.instructions = self._load_instructions(instructions_path)

        # Initialize model
        self.model_name = model_name or os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
        self.model = genai.GenerativeModel(self.model_name)

        # Set up logging
        self.logger = logger or self._setup_logging()

        # Statistics
        self.stats = {
            "newsletters_processed": 0,
            "articles_extracted": 0,
            "failed_processing": 0,
            "failed_newsletters": []
        }

    def _setup_logging(self):
        """Set up logging for the parser."""
        today = datetime.now().strftime("%Y%m%d")

        logger = logging.getLogger('newsletter_parser')
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            os.makedirs("logs", exist_ok=True)

            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler = logging.FileHandler(f"logs/newsletter_parser_{today}.log")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def _load_instructions(self, instructions_path):
        """Load instructions from file."""
        try:
            with open(instructions_path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            # Return default instructions if file not found
            return """Parse this newsletter email and extract individual articles.
Return a JSON array of objects with: article_number, headline, article_text"""
        except Exception as e:
            return ""

    def parse_newsletter(self, from_, subject, date, body_text, body_html=None):
        """
        Parse a single newsletter email into articles.

        Args:
            from_: Sender email address
            subject: Email subject
            date: Email date
            body_text: Plain text body
            body_html: HTML body (optional, used if text is empty)

        Returns:
            List of ArticleInfo dicts with article_number, headline, article_text
        """
        self.logger.info(f"Parsing newsletter: {subject}")

        # Use text body, fall back to HTML if empty
        body = body_text if body_text and body_text.strip() else body_html

        if not body:
            self.logger.warning(f"Empty newsletter body for: {subject}")
            return []

        # Construct prompt
        email_content = f"From: {from_}\nSubject: {subject}\nDate: {date}\n\nNewsletter Content:\n{body}"
        prompt = self.instructions + "\n\nNewsletter Email to Parse:\n" + email_content

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=list[ArticleInfo]
                )
            )

            if not response.text or not response.text.strip():
                self.logger.warning(f"Empty response from Gemini for newsletter: {subject}")
                return []

            articles = json.loads(response.text)

            if not isinstance(articles, list):
                self.logger.error(f"Unexpected response format (not a list) for: {subject}")
                self.stats["failed_processing"] += 1
                self.stats["failed_newsletters"].append(f"{subject} - Unexpected format")
                return []

            # Add metadata to each article
            for article in articles:
                article["source_subject"] = subject
                article["source_from"] = from_
                article["source_date"] = date

            self.stats["newsletters_processed"] += 1
            self.stats["articles_extracted"] += len(articles)
            self.logger.info(f"Extracted {len(articles)} articles from: {subject}")

            return articles

        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing error for {subject}: {e}")
            self.logger.error(traceback.format_exc())
            self.stats["failed_processing"] += 1
            self.stats["failed_newsletters"].append(f"{subject} - JSON error")
            return []

        except Exception as e:
            self.logger.error(f"Error processing newsletter {subject}: {e}")
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
    parser = NewsletterParser()
    return parser.parse_newsletter(from_, subject, date, body_text, body_html)
