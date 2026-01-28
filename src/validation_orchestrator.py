"""
Validation Orchestrator for DLRScanner

Orchestrates entity validation using AWHEmailScanner validators.
Transforms DLRScanner article data to validator format and maps results back.
"""

import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv


class ValidationOrchestrator:
    def __init__(self, logger=None):
        """
        Initialize the validation orchestrator.

        Args:
            logger: Optional logger instance
        """
        load_dotenv()

        self.logger = logger or self._setup_logging()

        # Add AWHEmailScanner to path
        awh_path = os.getenv('AWH_EMAILSCANNER_PATH', '../AWHEmailScanner/src')
        awh_path = os.path.abspath(awh_path)

        if awh_path not in sys.path:
            sys.path.insert(0, awh_path)
            self.logger.info(f"Added AWHEmailScanner to path: {awh_path}")

        # Set validation data path
        self.data_path = os.getenv('VALIDATION_DATA_PATH', '../AWHEmailScanner/data')
        self.data_path = os.path.abspath(self.data_path)

        # Import validators lazily to handle path setup
        self._hotel_validator = None
        self._company_validator = None
        self._contact_validator = None

    def _setup_logging(self):
        """Set up logging for the orchestrator."""
        today = datetime.now().strftime("%Y%m%d")

        logger = logging.getLogger('validation_orchestrator')
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            os.makedirs("logs", exist_ok=True)

            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler = logging.FileHandler(f"logs/validation_{today}.log")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def _import_validators(self):
        """Import validator modules from AWHEmailScanner."""
        try:
            from hotel_validator_v2 import validate_hotels_v2
            self._hotel_validator = validate_hotels_v2
            self.logger.info("Imported hotel_validator_v2")
        except ImportError as e:
            self.logger.warning(f"Could not import hotel_validator_v2: {e}")
            self._hotel_validator = None

        try:
            from company_validator import validate_companies
            self._company_validator = validate_companies
            self.logger.info("Imported company_validator")
        except ImportError as e:
            self.logger.warning(f"Could not import company_validator: {e}")
            self._company_validator = None

        try:
            from contact_validator import validate_contacts
            self._contact_validator = validate_contacts
            self.logger.info("Imported contact_validator")
        except ImportError as e:
            self.logger.warning(f"Could not import contact_validator: {e}")
            self._contact_validator = None

    def _transform_to_validator_format(self, articles):
        """
        Transform DLRScanner articles to AWHEmailScanner validator format.

        AWHEmailScanner validators expect:
        - hotel_details: [{name, city, state, brand, keys, address}]
        - brokerage_company: [company_names]
        - brokers: [contact_names]

        Args:
            articles: List of article dicts with hotels, companies, contacts

        Returns:
            List of dicts in validator-compatible format
        """
        validator_results = []

        for article in articles:
            result = {
                # Original article data
                "article_number": article.get("article_number"),
                "headline": article.get("headline"),
                "article_text": article.get("article_text"),
                "source_subject": article.get("source_subject"),
                "source_from": article.get("source_from"),
                "source_date": article.get("source_date"),

                # Transform hotels to hotel_details format
                "hotel_details": [
                    {
                        "name": h.get("name", ""),
                        "city": h.get("city", ""),
                        "state": h.get("state", ""),
                        "brand": h.get("brand", ""),
                        "keys": "",  # Not extracted from newsletters
                        "address": ""  # Not extracted from newsletters
                    }
                    for h in article.get("hotels", [])
                ],

                # Transform companies to brokerage_company format
                "brokerage_company": [
                    c.get("name", "") for c in article.get("companies", [])
                ],

                # Store company roles separately for reference
                "_company_roles": [
                    c.get("role", "") for c in article.get("companies", [])
                ],

                # Transform contacts to brokers format
                "brokers": [
                    c.get("name", "") for c in article.get("contacts", [])
                ],

                # Store contact details separately for reference
                "_contact_details": [
                    {"title": c.get("title", ""), "company": c.get("company", "")}
                    for c in article.get("contacts", [])
                ]
            }

            validator_results.append(result)

        return validator_results

    def _map_validation_results(self, validated_results, original_articles):
        """
        Map validation results back to article format.

        Args:
            validated_results: Results from validators with Entry IDs
            original_articles: Original article data

        Returns:
            Articles with validated Entry IDs added
        """
        output = []

        for i, validated in enumerate(validated_results):
            article = original_articles[i].copy() if i < len(original_articles) else {}

            # Map hotel Entry IDs
            hotel_entry_ids = validated.get("Hotel - Entry ID", [])
            article["hotel_entry_ids"] = hotel_entry_ids

            # Map company Entry IDs
            company_entry_ids = validated.get("Company - Entry ID", [])
            article["company_entry_ids"] = company_entry_ids

            # Map contact Entry IDs (validators use "Broker - Entry ID")
            contact_entry_ids = validated.get("Broker - Entry ID", [])
            article["contact_entry_ids"] = contact_entry_ids

            output.append(article)

        return output

    def validate_articles(self, articles):
        """
        Validate entities in articles using AWHEmailScanner validators.

        Args:
            articles: List of article dicts with hotels, companies, contacts

        Returns:
            Articles with validated Entry IDs added
        """
        self.logger.info(f"Starting validation for {len(articles)} articles")

        # Import validators if not done yet
        if self._hotel_validator is None and self._company_validator is None:
            self._import_validators()

        # Transform to validator format
        validator_data = self._transform_to_validator_format(articles)
        self.logger.info("Transformed articles to validator format")

        # Validate hotels
        if self._hotel_validator:
            try:
                embeddings_path = os.path.join(self.data_path, "hotel_embeddings.json")
                validator_data = self._hotel_validator(
                    validator_data,
                    self.logger,
                    embeddings_file_path=embeddings_path
                )
                self.logger.info("Hotel validation complete")
            except Exception as e:
                self.logger.error(f"Hotel validation error: {e}")
                # Initialize empty Entry IDs
                for result in validator_data:
                    if "Hotel - Entry ID" not in result:
                        result["Hotel - Entry ID"] = [None] * len(result.get("hotel_details", []))
        else:
            self.logger.warning("Hotel validator not available")
            for result in validator_data:
                result["Hotel - Entry ID"] = [None] * len(result.get("hotel_details", []))

        # Validate companies
        if self._company_validator:
            try:
                # Company validator expects data file at data/company_data.csv
                original_cwd = os.getcwd()
                os.chdir(os.path.dirname(self.data_path) or '.')

                validator_data = self._company_validator(validator_data, self.logger)
                self.logger.info("Company validation complete")

                os.chdir(original_cwd)
            except Exception as e:
                self.logger.error(f"Company validation error: {e}")
                for result in validator_data:
                    if "Company - Entry ID" not in result:
                        result["Company - Entry ID"] = [None] * len(result.get("brokerage_company", []))
        else:
            self.logger.warning("Company validator not available")
            for result in validator_data:
                result["Company - Entry ID"] = [None] * len(result.get("brokerage_company", []))

        # Validate contacts
        if self._contact_validator:
            try:
                original_cwd = os.getcwd()
                os.chdir(os.path.dirname(self.data_path) or '.')

                validator_data = self._contact_validator(validator_data, self.logger)
                self.logger.info("Contact validation complete")

                os.chdir(original_cwd)
            except Exception as e:
                self.logger.error(f"Contact validation error: {e}")
                for result in validator_data:
                    if "Broker - Entry ID" not in result:
                        result["Broker - Entry ID"] = [None] * len(result.get("brokers", []))
        else:
            self.logger.warning("Contact validator not available")
            for result in validator_data:
                result["Broker - Entry ID"] = [None] * len(result.get("brokers", []))

        # Map results back to article format
        validated_articles = self._map_validation_results(validator_data, articles)
        self.logger.info("Validation complete, results mapped back to articles")

        return validated_articles

    def get_validation_summary(self, articles):
        """
        Get a summary of validation results.

        Args:
            articles: Validated articles

        Returns:
            Dict with validation statistics
        """
        total_hotels = 0
        matched_hotels = 0
        total_companies = 0
        matched_companies = 0
        total_contacts = 0
        matched_contacts = 0

        for article in articles:
            hotel_ids = article.get("hotel_entry_ids", [])
            total_hotels += len(hotel_ids)
            matched_hotels += sum(1 for h in hotel_ids if h is not None)

            company_ids = article.get("company_entry_ids", [])
            total_companies += len(company_ids)
            matched_companies += sum(1 for c in company_ids if c is not None)

            contact_ids = article.get("contact_entry_ids", [])
            total_contacts += len(contact_ids)
            matched_contacts += sum(1 for c in contact_ids if c is not None)

        return {
            "total_hotels": total_hotels,
            "matched_hotels": matched_hotels,
            "hotel_match_rate": matched_hotels / total_hotels if total_hotels > 0 else 0,
            "total_companies": total_companies,
            "matched_companies": matched_companies,
            "company_match_rate": matched_companies / total_companies if total_companies > 0 else 0,
            "total_contacts": total_contacts,
            "matched_contacts": matched_contacts,
            "contact_match_rate": matched_contacts / total_contacts if total_contacts > 0 else 0
        }
