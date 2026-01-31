"""
Email File Reader for DLRScanner

Reads .eml and .msg files from local filesystem and extracts email data.
"""

import os
import logging
import email
from email.header import decode_header
from datetime import datetime
import glob
import chardet
from typing import Tuple, List

# Import extract_msg for .msg file support
try:
    import extract_msg
    MSG_SUPPORT = True
except ImportError:
    MSG_SUPPORT = False


class EmailFileReader:
    """Reads .eml and .msg files and extracts email data."""

    def __init__(self, logger=None):
        """
        Initialize the Email File Reader.

        Args:
            logger: Optional logger instance
        """
        self.logger = logger or self._setup_logging()

        if not MSG_SUPPORT:
            self.logger.warning("extract-msg not installed. .msg file support disabled.")

    def _setup_logging(self):
        """Set up logging for the file reader."""
        today = datetime.now().strftime("%Y%m%d")

        logger = logging.getLogger('email_file_reader')
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            os.makedirs("logs", exist_ok=True)

            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler = logging.FileHandler(f"logs/email_file_reader_{today}.log")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

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

        return body_text, body_html

    def _read_msg_file(self, file_path: str) -> Tuple[str, str, str, str, str]:
        """
        Read a single .msg file and extract email data.

        Args:
            file_path: Path to .msg file

        Returns:
            Tuple of (from_, subject, date, body_text, body_html)

        Raises:
            ImportError: If extract-msg not installed
            Exception: If file cannot be read or parsed
        """
        if not MSG_SUPPORT:
            raise ImportError("extract-msg library not installed. Install with: pip install extract-msg")

        try:
            # Open .msg file
            msg = extract_msg.Message(file_path)

            # Extract headers
            from_ = msg.sender or ""
            subject = msg.subject or ""
            date = msg.date or ""

            # Convert date to string if datetime object
            if hasattr(date, 'strftime'):
                date = date.strftime("%a, %d %b %Y %H:%M:%S +0000")

            # Extract body
            body_text = msg.body or ""
            body_html = msg.htmlBody or ""

            # Close the message
            msg.close()

            self.logger.debug(f"Read MSG file: {subject[:50]}... from {file_path}")

            return (from_, subject, date, body_text, body_html)

        except Exception as e:
            self.logger.error(f"Error reading MSG file {file_path}: {e}")
            raise

    def read_email_file(self, file_path: str) -> Tuple[str, str, str, str, str]:
        """
        Read a single email file (.eml or .msg) and extract email data.

        Automatically detects file type based on extension.

        Args:
            file_path: Path to .eml or .msg file

        Returns:
            Tuple of (from_, subject, date, body_text, body_html)

        Raises:
            FileNotFoundError: If file doesn't exist
            Exception: If file cannot be read or parsed
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Email file not found: {file_path}")

        # Detect file type
        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.msg':
            return self._read_msg_file(file_path)
        elif ext == '.eml':
            return self._read_eml_file(file_path)
        else:
            # Try .eml format as default
            self.logger.warning(f"Unknown file extension '{ext}', trying .eml format")
            return self._read_eml_file(file_path)

    def _read_eml_file(self, file_path: str) -> Tuple[str, str, str, str, str]:
        """
        Read a single .eml file and extract email data.

        Args:
            file_path: Path to .eml file

        Returns:
            Tuple of (from_, subject, date, body_text, body_html)

        Raises:
            Exception: If file cannot be read or parsed
        """
        try:
            # Read file with binary mode
            with open(file_path, 'rb') as f:
                msg = email.message_from_binary_file(f)

            # Extract headers
            from_ = self._decode_header_value(msg.get("From", ""))
            subject = self._decode_header_value(msg.get("Subject", ""))
            date = msg.get("Date", "")

            # Extract body
            body_text, body_html = self._get_email_body(msg)

            self.logger.debug(f"Read EML file: {subject[:50]}... from {file_path}")

            return (from_, subject, date, body_text, body_html)

        except Exception as e:
            self.logger.error(f"Error reading EML file {file_path}: {e}")
            raise

    def read_eml_file(self, file_path: str) -> Tuple[str, str, str, str, str]:
        """
        Deprecated: Use read_email_file() instead.
        Kept for backward compatibility.
        """
        return self.read_email_file(file_path)

    def scan_folder(self, folder_path: str, pattern: str = None) -> List[str]:
        """
        Scan a folder for email files (.eml and .msg).

        Args:
            folder_path: Path to folder to scan
            pattern: File pattern to match (default: None, which scans for both *.eml and *.msg)

        Returns:
            List of absolute paths to email files

        Raises:
            FileNotFoundError: If folder doesn't exist
        """
        if not os.path.exists(folder_path):
            raise FileNotFoundError(f"Folder not found: {folder_path}")

        if not os.path.isdir(folder_path):
            raise ValueError(f"Not a directory: {folder_path}")

        files = []

        if pattern:
            # Use provided pattern
            search_pattern = os.path.join(folder_path, pattern)
            files = glob.glob(search_pattern)
        else:
            # Scan for both .eml and .msg files
            eml_files = glob.glob(os.path.join(folder_path, "*.eml"))
            msg_files = glob.glob(os.path.join(folder_path, "*.msg"))
            files = eml_files + msg_files

        # Convert to absolute paths and sort
        files = [os.path.abspath(f) for f in files]
        files.sort()

        eml_count = sum(1 for f in files if f.lower().endswith('.eml'))
        msg_count = sum(1 for f in files if f.lower().endswith('.msg'))

        self.logger.info(f"Found {len(files)} email files in {folder_path} ({eml_count} .eml, {msg_count} .msg)")

        return files


# Convenience function
def read_eml_files(folder_path: str, pattern: str = "*.eml", logger=None) -> List[Tuple[str, str, str, str, str]]:
    """
    Convenience function to read all .eml files from a folder.

    Args:
        folder_path: Path to folder
        pattern: File pattern (default: "*.eml")
        logger: Optional logger instance

    Returns:
        List of tuples: (from_, subject, date, body_text, body_html)
    """
    reader = EmailFileReader(logger=logger)
    files = reader.scan_folder(folder_path, pattern)

    emails = []
    for file_path in files:
        try:
            email_data = reader.read_eml_file(file_path)
            emails.append(email_data)
        except Exception as e:
            if logger:
                logger.error(f"Failed to read {file_path}: {e}")

    return emails
