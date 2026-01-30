"""
DealCloud Uploader for DLRScanner

Uploads prepared articles to DealCloud Articles object.
Based on AWHEmailScanner's upload pattern.
"""

import os
import logging
import traceback
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv


class DealCloudUploader:
    """Uploads articles to DealCloud."""

    def __init__(self, logger=None):
        """
        Initialize the DealCloud uploader.

        Args:
            logger: Optional logger instance
        """
        load_dotenv()
        self.logger = logger or self._setup_logging()

        # Initialize DealCloud client
        try:
            from dealcloud_sdk import DealCloud
            self.dc = DealCloud(
                site_url=os.getenv('DEALCLOUD_SITE_URL'),
                client_id=os.getenv('DEALCLOUD_CLIENT_ID'),
                client_secret=os.getenv('DEALCLOUD_CLIENT_SECRET'),
            )
            self.logger.info("Connected to DealCloud")
        except ImportError:
            raise ImportError("dealcloud-sdk is not installed. Run: pip install dealcloud-sdk")
        except Exception as e:
            raise RuntimeError(f"Failed to connect to DealCloud: {str(e)}")

        # Get choice field IDs (Type and Source)
        self.type_choice_ids = self._get_choice_ids('Type')
        self.source_choice_ids = self._get_choice_ids('Source')
        self.logger.info(f"Type choice IDs: {self.type_choice_ids}")
        self.logger.info(f"Source choice IDs: {self.source_choice_ids}")

    def _setup_logging(self):
        """Set up logging for the uploader."""
        today = datetime.now().strftime("%Y%m%d")

        logger = logging.getLogger('dealcloud_uploader')
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            os.makedirs("logs", exist_ok=True)

            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler = logging.FileHandler(f"logs/dealcloud_uploader_{today}.log")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def _get_choice_ids(self, field_name):
        """Get choice value IDs for a choice field."""
        try:
            fields = self.dc.get_fields('Article')
            for field in fields:
                if field.name == field_name:
                    choice_map = {}
                    if field.choiceValues:
                        for cv in field.choiceValues:
                            choice_map[cv.name] = cv.id
                    return choice_map
            self.logger.warning(f"{field_name} field not found in Article object")
            return {}
        except Exception as e:
            self.logger.warning(f"Failed to get {field_name} choice IDs: {str(e)}")
            return {}

    def _prepare_articles_for_upload(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert prepared articles to DealCloud entry format.

        Args:
            articles: List of prepared articles from ArticlePreparator

        Returns:
            List of dicts in DealCloud entry format
        """
        prepared = []

        for article in articles:
            entry = {}

            # Map fields
            if article.get('ArticleText'):
                entry['ArticleText'] = article['ArticleText']

            if article.get('Headline'):
                entry['Headline'] = article['Headline']

            # ArticleNumber from metadata
            if article.get('_metadata') and article['_metadata'].get('article_number'):
                entry['ArticleNumber'] = article['_metadata']['article_number']

            if article.get('Source'):
                # Source is a choice field - try to map to choice value ID
                source_name = article['Source']
                source_id = self.source_choice_ids.get(source_name)
                if source_id:
                    entry['Source'] = source_id
                else:
                    # If source not in choices, use the first available choice
                    # or try the source name directly (may fail)
                    if self.source_choice_ids:
                        # Use first choice as default
                        default_choice_id = list(self.source_choice_ids.values())[0]
                        entry['Source'] = default_choice_id
                        self.logger.warning(f"Source '{source_name}' not in choices, using default")
                    else:
                        self.logger.warning(f"No Source choices available, skipping Source field")

            if article.get('PublishDate'):
                # Remove timezone from date (DealCloud doesn't accept it)
                publish_date = article['PublishDate']
                if '+' in publish_date or publish_date.endswith('Z'):
                    # Strip timezone info
                    publish_date = publish_date.split('+')[0].split('Z')[0]
                entry['PublishDate'] = publish_date

            # Map Type name to choice value ID
            if article.get('Type'):
                type_name = article['Type']
                type_id = self.type_choice_ids.get(type_name)
                if type_id:
                    entry['Type'] = type_id
                else:
                    self.logger.warning(f"Unknown Type value: {type_name}")

            # Multi-reference fields (Hotels, Companies, Contacts)
            # Only include if not empty
            if article.get('Hotels'):
                entry['Hotels'] = article['Hotels']

            if article.get('Companies'):
                entry['Companies'] = article['Companies']

            if article.get('Contacts'):
                entry['Contacts'] = article['Contacts']

            prepared.append(entry)

        return prepared

    def upload_articles(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Upload articles to DealCloud.

        Args:
            articles: List of prepared article dicts

        Returns:
            Dict with upload statistics
        """
        if not articles:
            self.logger.info("No articles to upload")
            return {
                'total_articles': 0,
                'uploaded': 0,
                'failed': 0,
                'entry_ids': [],
                'success_rate': 0
            }

        total = len(articles)
        self.logger.info(f"Starting upload of {total} articles to DealCloud")

        try:
            # Prepare articles for upload
            prepared_articles = self._prepare_articles_for_upload(articles)

            # Upload to DealCloud
            responses = self.dc.insert_data('Article', prepared_articles)

            # Process responses
            uploaded = 0
            failed = 0
            entry_ids = []
            error_messages = []

            for i, response in enumerate(responses):
                if isinstance(response, dict):
                    # Check for errors
                    if 'Errors' in response and response['Errors']:
                        failed += 1
                        error_details = []
                        for error in response['Errors']:
                            error_details.append(
                                f"Field: {error.get('field', 'Unknown')}, "
                                f"Code: {error.get('code', 'Unknown')}, "
                                f"Description: {error.get('description', 'Unknown')}"
                            )

                        headline = articles[i].get('Headline', 'Unknown')[:50]
                        error_msg = f"Error uploading '{headline}': {', '.join(error_details)}"
                        error_messages.append(error_msg)
                        self.logger.error(error_msg)
                    else:
                        # Success
                        uploaded += 1
                        entry_id = response.get('EntryId')
                        if entry_id:
                            entry_ids.append(entry_id)

                        headline = articles[i].get('Headline', 'Unknown')[:50]
                        self.logger.info(f"Uploaded: {headline} (ID: {entry_id})")

            # Summary
            stats = {
                'total_articles': total,
                'uploaded': uploaded,
                'failed': failed,
                'entry_ids': entry_ids,
                'success_rate': (uploaded / total * 100) if total > 0 else 0
            }

            if error_messages:
                stats['error_messages'] = error_messages

            self.logger.info(f"Upload complete: {uploaded}/{total} successful ({stats['success_rate']:.1f}%)")

            return stats

        except Exception as e:
            error_msg = f"Error uploading to DealCloud: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())

            return {
                'total_articles': total,
                'uploaded': 0,
                'failed': total,
                'entry_ids': [],
                'success_rate': 0,
                'error': error_msg
            }

    def test_connection(self) -> bool:
        """
        Test DealCloud connection.

        Returns:
            True if connection is working
        """
        try:
            objects = self.dc.get_objects()
            self.logger.info(f"Connection test successful: Found {len(objects)} objects")
            return True
        except Exception as e:
            self.logger.error(f"Connection test failed: {str(e)}")
            return False


def upload_to_dealcloud(articles: List[Dict[str, Any]], logger=None) -> Dict[str, Any]:
    """
    Convenience function to upload articles to DealCloud.

    Args:
        articles: List of prepared article dicts
        logger: Optional logger instance

    Returns:
        Upload statistics dict
    """
    uploader = DealCloudUploader(logger=logger)
    return uploader.upload_articles(articles)
