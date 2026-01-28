"""
Mailgun Email Fetcher for DLRScanner

Fetches stored emails from Mailgun using the REST API.
"""

import os
import logging
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv


class MailgunFetcher:
    def __init__(self, api_key=None, domain=None, logger=None):
        """
        Initialize the Mailgun fetcher.

        Args:
            api_key: Mailgun API key (or from MAILGUN_API_KEY env var)
            domain: Mailgun domain (or from MAILGUN_DOMAIN env var)
            logger: Optional logger instance
        """
        load_dotenv()

        self.api_key = api_key or os.getenv('MAILGUN_API_KEY')
        self.domain = domain or os.getenv('MAILGUN_DOMAIN')
        self.logger = logger or self._setup_logging()

        if not self.api_key:
            raise ValueError("Mailgun API key is required. Set MAILGUN_API_KEY environment variable.")
        if not self.domain:
            raise ValueError("Mailgun domain is required. Set MAILGUN_DOMAIN environment variable.")

        self.base_url = f"https://api.mailgun.net/v3/{self.domain}"
        self.auth = ("api", self.api_key)

    def _setup_logging(self):
        """Set up logging for the fetcher."""
        today = datetime.now().strftime("%Y%m%d")

        logger = logging.getLogger('mailgun_fetcher')
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            # Ensure logs directory exists
            os.makedirs("logs", exist_ok=True)

            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler = logging.FileHandler(f"logs/mailgun_fetcher_{today}.log")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

            # Also log to console
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        return logger

    def fetch_stored_emails(self, days_back=1, limit=10, sender_filter=None):
        """
        Fetch stored emails from Mailgun.

        Args:
            days_back: Number of days to look back for emails
            limit: Maximum number of emails to fetch
            sender_filter: Optional list of sender email addresses to filter by

        Returns:
            List of tuples: (from_, subject, date, body_text, body_html)
        """
        self.logger.info(f"Fetching stored emails (days_back={days_back}, limit={limit})")

        # Calculate the begin date
        begin_date = datetime.now() - timedelta(days=days_back)
        begin_timestamp = begin_date.timestamp()

        # Query for stored events
        events_url = f"{self.base_url}/events"
        params = {
            "event": "stored",
            "begin": begin_timestamp,
            "limit": limit
        }

        try:
            response = requests.get(events_url, auth=self.auth, params=params)
            response.raise_for_status()
            events_data = response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching events from Mailgun: {e}")
            return []

        events = events_data.get("items", [])
        self.logger.info(f"Found {len(events)} stored events")

        emails = []
        for event in events:
            try:
                # Get the storage URL for the message
                storage = event.get("storage", {})
                message_url = storage.get("url")

                if not message_url:
                    self.logger.warning(f"No storage URL for event: {event.get('id')}")
                    continue

                # Fetch the full message
                msg_response = requests.get(message_url, auth=self.auth)
                msg_response.raise_for_status()
                message = msg_response.json()

                from_ = message.get("from", message.get("sender", ""))
                subject = message.get("subject", "")
                date = message.get("Date", event.get("timestamp", ""))
                body_text = message.get("body-plain", "")
                body_html = message.get("body-html", "")

                # Apply sender filter if provided
                if sender_filter:
                    sender_match = False
                    for allowed_sender in sender_filter:
                        if allowed_sender.lower() in from_.lower():
                            sender_match = True
                            break
                    if not sender_match:
                        self.logger.debug(f"Skipping email from {from_} - not in sender filter")
                        continue

                emails.append((from_, subject, date, body_text, body_html))
                self.logger.info(f"Fetched email: {subject[:50]}...")

            except requests.exceptions.RequestException as e:
                self.logger.error(f"Error fetching message: {e}")
                continue
            except Exception as e:
                self.logger.error(f"Error processing event: {e}")
                continue

        self.logger.info(f"Successfully fetched {len(emails)} emails")
        return emails

    def fetch_emails_by_recipient(self, recipient, days_back=1, limit=10):
        """
        Fetch stored emails sent to a specific recipient.

        Args:
            recipient: Email address of the recipient
            days_back: Number of days to look back
            limit: Maximum number of emails to fetch

        Returns:
            List of tuples: (from_, subject, date, body_text, body_html)
        """
        self.logger.info(f"Fetching emails for recipient: {recipient}")

        begin_date = datetime.now() - timedelta(days=days_back)
        begin_timestamp = begin_date.timestamp()

        events_url = f"{self.base_url}/events"
        params = {
            "event": "stored",
            "begin": begin_timestamp,
            "limit": limit,
            "recipient": recipient
        }

        try:
            response = requests.get(events_url, auth=self.auth, params=params)
            response.raise_for_status()
            events_data = response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching events from Mailgun: {e}")
            return []

        events = events_data.get("items", [])
        self.logger.info(f"Found {len(events)} stored events for {recipient}")

        emails = []
        for event in events:
            try:
                storage = event.get("storage", {})
                message_url = storage.get("url")

                if not message_url:
                    continue

                msg_response = requests.get(message_url, auth=self.auth)
                msg_response.raise_for_status()
                message = msg_response.json()

                from_ = message.get("from", message.get("sender", ""))
                subject = message.get("subject", "")
                date = message.get("Date", event.get("timestamp", ""))
                body_text = message.get("body-plain", "")
                body_html = message.get("body-html", "")

                emails.append((from_, subject, date, body_text, body_html))
                self.logger.info(f"Fetched email: {subject[:50]}...")

            except Exception as e:
                self.logger.error(f"Error processing event: {e}")
                continue

        return emails


# Convenience function for direct usage
def fetch_newsletters(days_back=None, limit=None, sender_filter=None):
    """
    Convenience function to fetch newsletter emails.

    Args:
        days_back: Number of days to look back (default from DAYS_BACK env var)
        limit: Maximum emails to fetch (default from EMAIL_FETCH_COUNT env var)
        sender_filter: List of sender addresses to filter by

    Returns:
        List of tuples: (from_, subject, date, body_text, body_html)
    """
    load_dotenv()

    days_back = days_back or int(os.getenv('DAYS_BACK', 1))
    limit = limit or int(os.getenv('EMAIL_FETCH_COUNT', 10))

    fetcher = MailgunFetcher()
    return fetcher.fetch_stored_emails(days_back=days_back, limit=limit, sender_filter=sender_filter)
