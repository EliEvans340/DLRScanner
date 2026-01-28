"""
Entity Extractor for DLRScanner

Uses Gemini AI to extract hotels, companies, and contacts from articles.
"""

import os
import json
import logging
import traceback
from datetime import datetime
import google.generativeai as genai
import typing_extensions as typing
from dotenv import load_dotenv


class HotelEntity(typing.TypedDict):
    """Schema for extracted hotel."""
    name: str
    city: typing.NotRequired[str]
    state: typing.NotRequired[str]
    brand: typing.NotRequired[str]


class CompanyEntity(typing.TypedDict):
    """Schema for extracted company."""
    name: str
    role: typing.NotRequired[str]


class ContactEntity(typing.TypedDict):
    """Schema for extracted contact."""
    name: str
    title: typing.NotRequired[str]
    company: typing.NotRequired[str]


class ArticleEntities(typing.TypedDict):
    """Schema for all entities extracted from an article."""
    hotels: list[HotelEntity]
    companies: list[CompanyEntity]
    contacts: list[ContactEntity]


class EntityExtractor:
    def __init__(self, api_key=None, model_name=None, instructions_path=None, logger=None):
        """
        Initialize the Entity Extractor.

        Args:
            api_key: Google API key (or from GOOGLE_API_KEY env var)
            model_name: Gemini model to use (or from GEMINI_MODEL env var)
            instructions_path: Path to extractor instructions file
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
                os.path.dirname(__file__), '..', 'config', 'entity_extractor_instructions.txt'
            )
        self.instructions = self._load_instructions(instructions_path)

        # Initialize model
        self.model_name = model_name or os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
        self.model = genai.GenerativeModel(self.model_name)

        # Set up logging
        self.logger = logger or self._setup_logging()

        # Statistics
        self.stats = {
            "articles_processed": 0,
            "hotels_extracted": 0,
            "companies_extracted": 0,
            "contacts_extracted": 0,
            "failed_processing": 0,
            "failed_articles": []
        }

    def _setup_logging(self):
        """Set up logging for the extractor."""
        today = datetime.now().strftime("%Y%m%d")

        logger = logging.getLogger('entity_extractor')
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            os.makedirs("logs", exist_ok=True)

            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler = logging.FileHandler(f"logs/entity_extractor_{today}.log")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def _load_instructions(self, instructions_path):
        """Load instructions from file."""
        try:
            with open(instructions_path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            return """Extract hotels, companies, and contacts from this article.
Return JSON with: hotels (name, city, state, brand), companies (name, role), contacts (name, title, company)"""
        except Exception:
            return ""

    def extract_entities(self, article):
        """
        Extract entities from a single article.

        Args:
            article: Dict with at least 'article_text' and 'headline' keys

        Returns:
            Dict with 'hotels', 'companies', 'contacts' lists, plus original article data
        """
        headline = article.get('headline', 'Unknown')
        article_text = article.get('article_text', '')

        self.logger.info(f"Extracting entities from: {headline[:50]}...")

        if not article_text:
            self.logger.warning(f"Empty article text for: {headline}")
            return {
                **article,
                "hotels": [],
                "companies": [],
                "contacts": []
            }

        # Construct prompt
        prompt = self.instructions + f"\n\nArticle Headline: {headline}\n\nArticle Text:\n{article_text}"

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=ArticleEntities
                )
            )

            if not response.text or not response.text.strip():
                self.logger.warning(f"Empty response for article: {headline}")
                return {
                    **article,
                    "hotels": [],
                    "companies": [],
                    "contacts": []
                }

            entities = json.loads(response.text)

            # Ensure all required keys exist
            hotels = entities.get('hotels', [])
            companies = entities.get('companies', [])
            contacts = entities.get('contacts', [])

            # Update statistics
            self.stats["articles_processed"] += 1
            self.stats["hotels_extracted"] += len(hotels)
            self.stats["companies_extracted"] += len(companies)
            self.stats["contacts_extracted"] += len(contacts)

            self.logger.info(
                f"Extracted from '{headline[:30]}...': "
                f"{len(hotels)} hotels, {len(companies)} companies, {len(contacts)} contacts"
            )

            # Return combined article data with entities
            return {
                **article,
                "hotels": hotels,
                "companies": companies,
                "contacts": contacts
            }

        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing error for {headline}: {e}")
            self.logger.error(traceback.format_exc())
            self.stats["failed_processing"] += 1
            self.stats["failed_articles"].append(f"{headline} - JSON error")
            return {
                **article,
                "hotels": [],
                "companies": [],
                "contacts": []
            }

        except Exception as e:
            self.logger.error(f"Error extracting entities from {headline}: {e}")
            self.logger.error(traceback.format_exc())
            self.stats["failed_processing"] += 1
            self.stats["failed_articles"].append(f"{headline} - Processing error")
            return {
                **article,
                "hotels": [],
                "companies": [],
                "contacts": []
            }

    def extract_from_articles(self, articles):
        """
        Extract entities from multiple articles.

        Args:
            articles: List of article dicts (from newsletter_parser)

        Returns:
            List of articles with extracted entities
        """
        results = []

        for article in articles:
            result = self.extract_entities(article)
            results.append(result)

        self.logger.info(
            f"Entity extraction complete: {self.stats['articles_processed']} articles, "
            f"{self.stats['hotels_extracted']} hotels, "
            f"{self.stats['companies_extracted']} companies, "
            f"{self.stats['contacts_extracted']} contacts"
        )

        return results

    def get_stats(self):
        """Get extraction statistics."""
        return self.stats.copy()


# Convenience function
def extract_article_entities(article):
    """
    Convenience function to extract entities from a single article.

    Args:
        article: Dict with 'article_text' and 'headline'

    Returns:
        Article dict with 'hotels', 'companies', 'contacts' lists added
    """
    extractor = EntityExtractor()
    return extractor.extract_entities(article)
