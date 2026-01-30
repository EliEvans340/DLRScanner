"""
GMX Email Fetcher for DLRScanner

Fetches emails from GMX using IMAP.
"""

import os
import logging
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import chardet
import traceback
import re
from email.utils import parsedate_to_datetime


class GmxFetcher:
    def __init__(self, email_address=None, password=None, logger=None):
        """
        Initialize the GMX fetcher.

        Args:
            email_address: GMX email address (or from GMX_EMAIL env var)
            password: GMX password (or from GMX_PASSWORD env var)
            logger: Optional logger instance
        """
        load_dotenv()

        self.email_address = email_address or os.getenv('GMX_EMAIL')
        self.password = password or os.getenv('GMX_PASSWORD')
        self.logger = logger or self._setup_logging()

        if not self.email_address:
            raise ValueError("Email is required. Set GMX_EMAIL environment variable.")
        if not self.password:
            raise ValueError("Password is required. Set GMX_PASSWORD environment variable.")

        # Determine IMAP server based on email domain
        domain = self.email_address.split('@')[1].lower()
        if 'gmx' in domain:
            self.imap_server = "imap.gmx.com"
        elif 'mail.com' in domain:
            self.imap_server = "imap.mail.com"
        elif 'mailbox.org' in domain:
            self.imap_server = "imap.mailbox.org"
        else:
            # Default to GMX
            self.imap_server = "imap.gmx.com"
            self.logger.warning(f"Unknown email domain: {domain}, defaulting to GMX server")

    def _setup_logging(self):
        """Set up logging for the fetcher."""
        today = datetime.now().strftime("%Y%m%d")

        logger = logging.getLogger('gmx_fetcher')
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            os.makedirs("logs", exist_ok=True)

            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler = logging.FileHandler(f"logs/gmx_fetcher_{today}.log")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        return logger

    def _connect_to_imap(self):
        """Connect to GMX IMAP server with fallback."""
        try:
            # Try port 993 first (SSL)
            self.logger.info(f"Attempting connection to {self.imap_server} with SSL (port 993)...")
            mail = imaplib.IMAP4_SSL(self.imap_server, timeout=30)
        except Exception as e:
            # Fallback to port 143 with STARTTLS
            self.logger.warning(f"SSL connection failed: {str(e)}")
            self.logger.info(f"Attempting connection to {self.imap_server} without SSL (port 143)...")
            mail = imaplib.IMAP4(self.imap_server, timeout=30)
            mail.starttls()

        # Authentication
        self.logger.info(f"Logging in as {self.email_address}...")
        mail.login(self.email_address, self.password)
        self.logger.info("Successfully connected to GMX email account")
        return mail

    def _decode_payload(self, payload, charset):
        """Decode email payload with fallback encodings."""
        encodings = [charset, 'utf-8', 'iso-8859-1', 'windows-1252']
        for encoding in encodings:
            try:
                if encoding:
                    return payload.decode(encoding)
            except (UnicodeDecodeError, AttributeError, LookupError):
                continue
        # Last resort
        return payload.decode('utf-8', errors='replace')

    def _decode_header_value(self, header_value):
        """Decode email header value."""
        if header_value is None:
            return ""

        decoded_parts = decode_header(header_value)
        decoded_string = ""

        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                decoded_string += part.decode(encoding or 'utf-8', errors='ignore')
            else:
                decoded_string += part

        return decoded_string

    def _parse_date_flexible(self, date_str):
        """
        Parse date string with multiple format attempts.

        Args:
            date_str: Date string to parse

        Returns:
            timezone-aware datetime object or None if parsing fails
        """
        # Clean up the date string
        date_str = date_str.strip()

        # Try RFC 2822 format first (standard email format)
        # BUT: parsedate_to_datetime has a bug where it ignores "PM"/"AM" in some formats
        # So only use it if the string doesn't contain AM/PM markers
        if ' AM' not in date_str.upper() and ' PM' not in date_str.upper():
            try:
                return parsedate_to_datetime(date_str)
            except (ValueError, TypeError, AttributeError):
                pass

        # Try common forwarded email formats
        # Format: "Thursday, January 29, 2026 5:29:13 PM (UTC-05:00) Eastern Time (US & Canada)"
        # Format: "Thursday, January 29, 2026 5:29 PM"
        formats_to_try = [
            "%A, %B %d, %Y %I:%M:%S %p",  # Thursday, January 29, 2026 5:29:13 PM
            "%A, %B %d, %Y %I:%M %p",      # Thursday, January 29, 2026 5:29 PM
            "%A, %B %d, %Y %I:%M:%S%p",    # No space before AM/PM
            "%A, %B %d, %Y %I:%M%p",       # No space before AM/PM
            "%B %d, %Y %I:%M:%S %p",       # January 29, 2026 5:29:13 PM
            "%B %d, %Y %I:%M %p",          # January 29, 2026 5:29 PM
            "%m/%d/%Y %I:%M:%S %p",        # 1/29/2026 5:29:13 PM
            "%m/%d/%Y %I:%M %p",           # 1/29/2026 5:29 PM
            "%Y-%m-%d %H:%M:%S",           # 2026-01-29 17:29:13
            "%Y-%m-%d",                    # 2026-01-29
        ]

        # Extract just the date/time part before timezone info
        # Remove patterns like "(UTC-05:00) Eastern Time (US & Canada)"
        clean_date = re.sub(r'\s*\(UTC[^)]*\).*$', '', date_str)
        clean_date = clean_date.strip()

        for fmt in formats_to_try:
            try:
                # Parse the date and make it timezone-aware (assume UTC if no timezone)
                dt = datetime.strptime(clean_date, fmt)
                self.logger.debug(f"Successfully parsed '{clean_date}' with format '{fmt}' -> {dt} (hour: {dt.hour})")
                # Make it timezone-aware by assuming UTC
                dt_with_tz = dt.replace(tzinfo=timezone.utc)
                self.logger.debug(f"After adding timezone: {dt_with_tz}")
                return dt_with_tz
            except (ValueError, TypeError):
                continue

        return None

    def _get_earliest_date(self, msg, body_text=""):
        """
        Extract the earliest date from an email, handling forwarded messages.

        For forwarded emails, this will find the original sent date rather than
        the forward date by parsing the email body for original date headers.

        Args:
            msg: Email message object
            body_text: Email body text (optional, used to find original dates)

        Returns:
            Date string (earliest date found)
        """
        dates_found = []

        # Get the primary Date header
        primary_date = msg.get("Date", "")
        if primary_date:
            dates_found.append(('primary_header', primary_date))

        # Parse email body for original date in forwarded message headers
        # Look for patterns like "Sent: Thursday, January 29, 2026 5:29:13 PM (UTC-05:00)"
        if body_text:
            # Match date lines that appear in forwarded email headers
            # Pattern for "Sent: <date>" - capture everything until newline or end
            sent_pattern = r'(?:^|\n)Sent:\s*([^\n]+?)(?:\n|$)'
            sent_matches = re.findall(sent_pattern, body_text, re.MULTILINE | re.IGNORECASE)

            for match in sent_matches:
                dates_found.append(('body_sent', match))

        # Parse all found dates and find the earliest
        earliest_date = None
        earliest_datetime = None
        earliest_source = None

        for source, date_str in dates_found:
            parsed_date = self._parse_date_flexible(date_str)

            if parsed_date:
                self.logger.debug(f"Parsed date from {source}: {date_str} -> {parsed_date} (tz: {parsed_date.tzinfo})")

                try:
                    if earliest_datetime is None or parsed_date < earliest_datetime:
                        earliest_datetime = parsed_date
                        earliest_date = date_str
                        earliest_source = source
                except TypeError as e:
                    self.logger.error(f"Cannot compare dates - earliest: {earliest_datetime} ({type(earliest_datetime)}), parsed: {parsed_date} ({type(parsed_date)}): {e}")
                    # If we can't compare, convert both to naive and compare
                    if earliest_datetime and earliest_datetime.tzinfo:
                        earliest_dt_naive = earliest_datetime.replace(tzinfo=None)
                    else:
                        earliest_dt_naive = earliest_datetime

                    if parsed_date.tzinfo:
                        parsed_dt_naive = parsed_date.replace(tzinfo=None)
                    else:
                        parsed_dt_naive = parsed_date

                    if earliest_dt_naive is None or parsed_dt_naive < earliest_dt_naive:
                        earliest_datetime = parsed_date
                        earliest_date = date_str
                        earliest_source = source
            else:
                self.logger.debug(f"Could not parse date from {source}: {date_str}")

        # Return the earliest date found, or the primary date as fallback
        if earliest_date and earliest_source != 'primary_header':
            self.logger.info(f"Using earliest date from {earliest_source}: {earliest_date}")
            # Convert to RFC 2822 format for consistency
            return earliest_datetime.strftime("%a, %d %b %Y %H:%M:%S +0000")

        return primary_date

    def _get_email_body(self, msg):
        """Extract text and HTML body from email message."""
        body_text = ""
        body_html = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                if "attachment" not in content_disposition:
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            # Use chardet to detect encoding
                            detected = chardet.detect(payload)
                            charset = detected.get('encoding')

                            try:
                                decoded_payload = self._decode_payload(payload, charset)
                            except Exception as e:
                                self.logger.warning(f"Failed to decode payload: {e}")
                                decoded_payload = payload.decode('utf-8', errors='replace')

                            if content_type == "text/plain":
                                body_text += decoded_payload
                            elif content_type == "text/html":
                                body_html += decoded_payload
                    except Exception as e:
                        self.logger.warning(f"Error decoding email part: {e}")
                        self.logger.debug(traceback.format_exc())
        else:
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    # Use chardet to detect encoding
                    detected = chardet.detect(payload)
                    charset = detected.get('encoding')

                    try:
                        decoded_payload = self._decode_payload(payload, charset)
                    except Exception as e:
                        self.logger.warning(f"Failed to decode payload: {e}")
                        decoded_payload = payload.decode('utf-8', errors='replace')

                    if msg.get_content_type() == "text/plain":
                        body_text = decoded_payload
                    elif msg.get_content_type() == "text/html":
                        body_html = decoded_payload
            except Exception as e:
                self.logger.warning(f"Error decoding email body: {e}")
                self.logger.debug(traceback.format_exc())

        return body_text, body_html

    def fetch_stored_emails(self, days_back=1, limit=10, sender_filter=None):
        """
        Fetch emails from GMX inbox.

        Args:
            days_back: Number of days to look back for emails
            limit: Maximum number of emails to fetch
            sender_filter: Optional list of sender email addresses to filter by

        Returns:
            List of tuples: (from_, subject, date, body_text, body_html)
        """
        self.logger.info(f"Fetching emails from GMX (days_back={days_back}, limit={limit})")

        emails = []

        try:
            mail = self._connect_to_imap()
            mail.select("INBOX")

            since_date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
            search_criteria = f'(SINCE {since_date})'

            status, messages = mail.search(None, search_criteria)

            if status != "OK":
                self.logger.error("Failed to search emails")
                return []

            email_ids = messages[0].split()
            email_ids.reverse()

            count = 0
            for email_id in email_ids:
                if count >= limit:
                    break

                try:
                    status, msg_data = mail.fetch(email_id, "(RFC822)")

                    if status != "OK":
                        continue

                    msg = email.message_from_bytes(msg_data[0][1])

                    from_ = self._decode_header_value(msg.get("From", ""))
                    subject = self._decode_header_value(msg.get("Subject", ""))

                    if sender_filter:
                        sender_match = False
                        for allowed_sender in sender_filter:
                            if allowed_sender.lower() in from_.lower():
                                sender_match = True
                                break
                        if not sender_match:
                            self.logger.debug(f"Skipping email from {from_} - not in sender filter")
                            continue

                    # Get body first so we can parse it for original dates
                    body_text, body_html = self._get_email_body(msg)

                    # Extract earliest date (handles forwarded emails)
                    date = self._get_earliest_date(msg, body_text)

                    emails.append((from_, subject, date, body_text, body_html))
                    self.logger.info(f"Fetched email: {subject[:50]}...")

                    count += 1

                except Exception as e:
                    self.logger.error(f"Error processing email {email_id}: {e}")
                    continue

            mail.close()
            mail.logout()

        except imaplib.IMAP4.error as e:
            self.logger.error(f"IMAP error: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Error connecting to GMX: {e}")
            return []

        self.logger.info(f"Successfully fetched {len(emails)} emails")
        return emails

    def fetch_emails_by_recipient(self, recipient, days_back=1, limit=10):
        """
        Fetch emails sent to a specific recipient (for GMX, this is the inbox).

        Args:
            recipient: Email address of the recipient (ignored for GMX, uses inbox)
            days_back: Number of days to look back
            limit: Maximum number of emails to fetch

        Returns:
            List of tuples: (from_, subject, date, body_text, body_html)
        """
        self.logger.info(f"Fetching emails for recipient: {recipient}")
        return self.fetch_stored_emails(days_back=days_back, limit=limit)


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

    fetcher = GmxFetcher()
    return fetcher.fetch_stored_emails(days_back=days_back, limit=limit, sender_filter=sender_filter)
