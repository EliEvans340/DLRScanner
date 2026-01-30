"""
DealCloud Explorer Utility Module

Provides reusable utilities for connecting to DealCloud and exploring schema.
"""

import os
import logging
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv


def get_client():
    """
    Create an authenticated DealCloud client.

    Returns:
        DealCloud: Authenticated DealCloud client instance

    Raises:
        ValueError: If required credentials are missing
        ImportError: If dealcloud-sdk is not installed
    """
    try:
        from dealcloud_sdk import DealCloud
    except ImportError:
        raise ImportError(
            "dealcloud-sdk is not installed. Install it with: pip install dealcloud-sdk"
        )

    load_dotenv()

    # Get credentials from environment
    site_url = os.getenv('DEALCLOUD_SITE_URL')
    client_id = os.getenv('DEALCLOUD_CLIENT_ID')
    client_secret = os.getenv('DEALCLOUD_CLIENT_SECRET')

    # Validate credentials
    missing = []
    if not site_url:
        missing.append('DEALCLOUD_SITE_URL')
    if not client_id:
        missing.append('DEALCLOUD_CLIENT_ID')
    if not client_secret:
        missing.append('DEALCLOUD_CLIENT_SECRET')

    if missing:
        raise ValueError(
            f"Missing required DealCloud credentials: {', '.join(missing)}\n"
            f"Please set them in your .env file."
        )

    # Create and return client
    try:
        dc = DealCloud(
            site_url=site_url,
            client_id=client_id,
            client_secret=client_secret,
        )
        return dc
    except Exception as e:
        raise RuntimeError(f"Failed to connect to DealCloud: {str(e)}")


def find_object_by_name(dc, name: str, case_sensitive: bool = False) -> Optional[Any]:
    """
    Find a DealCloud object by its API name or display name.

    Args:
        dc: DealCloud client instance
        name: Object name to search for (API name or display name)
        case_sensitive: Whether to use case-sensitive matching (default: False)

    Returns:
        Object model if found, None otherwise
    """
    try:
        objects = dc.get_objects()

        search_name = name if case_sensitive else name.lower()

        for obj in objects:
            # Handle Pydantic model attributes
            obj_api_name = getattr(obj, 'apiName', '') or getattr(obj, 'name', '')
            obj_singular = getattr(obj, 'singularName', '')
            obj_plural = getattr(obj, 'pluralName', '')

            compare_api = obj_api_name if case_sensitive else obj_api_name.lower()
            compare_singular = obj_singular if case_sensitive else obj_singular.lower()
            compare_plural = obj_plural if case_sensitive else obj_plural.lower()

            if search_name in [compare_api, compare_singular, compare_plural]:
                return obj

        return None
    except Exception as e:
        logging.error(f"Error finding object '{name}': {str(e)}")
        return None


def get_object_fields(dc, object_name: str) -> List[Dict[str, Any]]:
    """
    Get all fields for a DealCloud object.

    Args:
        dc: DealCloud client instance
        object_name: Name of the object (API name or display name)

    Returns:
        List of field dictionaries

    Raises:
        RuntimeError: If unable to retrieve fields
    """
    try:
        fields = dc.get_fields(object_name)
        return fields
    except Exception as e:
        raise RuntimeError(f"Failed to get fields for object '{object_name}': {str(e)}")


def format_field_info(field: Any, verbose: bool = True) -> str:
    """
    Format field information as a readable string.

    Args:
        field: Field object from DealCloud API (Pydantic model or dict)
        verbose: Include detailed information (default: True)

    Returns:
        Formatted string representation of the field
    """
    # DealCloud field type codes
    TYPE_CODES = {
        1: 'Text',
        2: 'Choice/Text',
        3: 'Number',
        4: 'Date/Time',
        5: 'Reference',
        6: 'Boolean',
        7: 'User Reference',
        8: 'Calculated',
        9: 'Attachment'
    }

    # Handle both Pydantic models and dicts
    def get_field_attr(obj, *attrs):
        for attr in attrs:
            if hasattr(obj, attr):
                val = getattr(obj, attr, None)
                if val is not None:
                    return val
            elif isinstance(obj, dict) and attr in obj:
                return obj.get(attr)
        return None

    # Extract basic field info
    field_name = get_field_attr(field, 'name', 'apiName') or 'Unknown'
    display_name = get_field_attr(field, 'displayName', 'display_name') or field_name
    field_type_code = get_field_attr(field, 'fieldType', 'type', 'field_type')
    field_type = TYPE_CODES.get(field_type_code, f'Type {field_type_code}')
    required = get_field_attr(field, 'isRequired', 'required', 'is_required') or False

    # Build output string
    lines = []
    lines.append(f"Field: {field_name}")

    if verbose:
        if display_name != field_name:
            lines.append(f"  Display Name: {display_name}")
        lines.append(f"  Type: {field_type}")
        lines.append(f"  Required: {'Yes' if required else 'No'}")

        # Add type-specific details
        # For reference fields (type 5 or 7), show entry lists
        if field_type_code in [5, 7]:
            entry_lists = get_field_attr(field, 'entryLists', 'entry_lists')
            if entry_lists:
                lines.append(f"  Entry Lists: {entry_lists}")

        # For choice fields, show choice values
        choice_values = get_field_attr(field, 'choiceValues', 'choices', 'choice_values')
        if choice_values:
            # Extract names from ChoiceValue objects or plain strings
            choice_names = []
            for cv in choice_values:
                if hasattr(cv, 'name'):
                    choice_names.append(cv.name)
                else:
                    choice_names.append(str(cv))
            if choice_names:
                choice_str = ', '.join(choice_names)
                lines.append(f"  Choices: {choice_str}")

        # For numeric fields
        if field_type_code == 3:
            is_money = get_field_attr(field, 'isMoney', 'is_money')
            if is_money:
                lines.append(f"  Is Money: Yes")
    else:
        lines[0] = f"{field_name} ({field_type})" + (" *required*" if required else "")

    return '\n'.join(lines)


def validate_credentials() -> bool:
    """
    Validate that all required DealCloud credentials are set.

    Returns:
        True if all credentials are present, False otherwise
    """
    load_dotenv()

    site_url = os.getenv('DEALCLOUD_SITE_URL')
    client_id = os.getenv('DEALCLOUD_CLIENT_ID')
    client_secret = os.getenv('DEALCLOUD_CLIENT_SECRET')

    return all([site_url, client_id, client_secret])


def setup_logging(name: str = 'dealcloud_explorer', level: int = logging.INFO) -> logging.Logger:
    """
    Set up logging for DealCloud exploration scripts.

    Args:
        name: Logger name
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
