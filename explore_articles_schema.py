#!/usr/bin/env python3
"""
DealCloud Articles Schema Explorer

Retrieves detailed schema and fields for the Articles object.

Usage:
    python explore_articles_schema.py [--object-name OBJECT_NAME]

Arguments:
    --object-name: Name of the object to explore (default: "Articles")
"""

import json
import os
import sys
import argparse
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dealcloud_explorer import get_client, find_object_by_name, get_object_fields, format_field_info, setup_logging


def main():
    """Explore Articles object schema in detail."""
    parser = argparse.ArgumentParser(description='Explore DealCloud Articles schema')
    parser.add_argument('--object-name', default='Articles', help='Object name to explore (default: Articles)')
    args = parser.parse_args()

    logger = setup_logging('explore_articles_schema')

    logger.info("=" * 80)
    logger.info(f"DealCloud Schema Explorer - {args.object_name}")
    logger.info("=" * 80)

    try:
        # Connect to DealCloud
        logger.info("Connecting to DealCloud...")
        dc = get_client()
        logger.info("Connected successfully!")

        # Find the object
        logger.info(f"\nSearching for '{args.object_name}' object...")
        obj = find_object_by_name(dc, args.object_name)

        if not obj:
            logger.error(f"\n[X] Object '{args.object_name}' not found")
            logger.error("Run 'python explore_dealcloud_objects.py' to see all available objects")
            sys.exit(1)

        # Display object info
        obj_id = getattr(obj, 'id', 'N/A')
        api_name = getattr(obj, 'apiName', None) or getattr(obj, 'name', 'Unknown')
        singular = getattr(obj, 'singularName', api_name)
        plural = getattr(obj, 'pluralName', singular)

        logger.info(f"[OK] Found object: {api_name}")
        print("\n" + "=" * 80)
        print("OBJECT INFORMATION")
        print("=" * 80)
        print(f"Object ID: {obj_id}")
        print(f"API Name: {api_name}")
        print(f"Singular: {singular}")
        print(f"Plural: {plural}")

        # Get fields
        logger.info(f"\nRetrieving fields for '{api_name}'...")
        try:
            fields = get_object_fields(dc, api_name)
        except Exception as e:
            logger.error(f"Failed to get fields: {str(e)}")
            logger.info("Trying alternative object names...")

            # Try plural form
            try:
                fields = get_object_fields(dc, plural)
                logger.info(f"Success using plural form: {plural}")
            except:
                # Try singular form
                try:
                    fields = get_object_fields(dc, singular)
                    logger.info(f"Success using singular form: {singular}")
                except:
                    logger.error("Unable to retrieve fields using any object name variant")
                    sys.exit(1)

        logger.info(f"[OK] Found {len(fields)} fields\n")

        # Display fields
        print("\n" + "=" * 80)
        print("FIELD DETAILS")
        print("=" * 80)

        # Expected fields from our schema
        expected_fields = {
            'ArticleText': 'Text (Multi-line)',
            'Headline': 'Text (Single-line)',
            'Hotels': 'Multi-Reference --> Hotels',
            'Companies': 'Multi-Reference --> Companies',
            'Contacts': 'Multi-Reference --> Contacts',
            'Source': 'Text (Single-line)',
            'PublishDate': 'Date/Time',
            'Type': 'Choice (Actual, Testing)'
        }

        found_fields = {}

        for field in fields:
            print("\n" + format_field_info(field, verbose=True))
            print("-" * 80)

            # Handle Pydantic model
            field_name = getattr(field, 'name', None) or getattr(field, 'apiName', '')
            found_fields[field_name] = field

        # Compare with expected schema
        print("\n" + "=" * 80)
        print("SCHEMA COMPARISON")
        print("=" * 80)

        # Type code mapping
        TYPE_CODES = {
            1: 'Text',
            2: 'Choice/Text',
            3: 'Number',
            4: 'Date/Time',
            5: 'Reference',
            6: 'Boolean',
            7: 'User Reference'
        }

        missing_fields = []
        matched_fields = []
        extra_fields = []

        # Check expected fields
        for expected_name, expected_type in expected_fields.items():
            if expected_name in found_fields:
                matched_fields.append(expected_name)
                field = found_fields[expected_name]
                field_type_code = getattr(field, 'fieldType', None) or getattr(field, 'type', 'Unknown')
                field_type = TYPE_CODES.get(field_type_code, f'Type {field_type_code}')

                print(f"[OK] {expected_name}")
                print(f"  Expected: {expected_type}")
                print(f"  Actual: {field_type}")

                # Check type-specific details
                if 'Reference' in expected_type or field_type_code in [5, 7]:
                    entry_lists = getattr(field, 'entryLists', None)
                    if entry_lists:
                        print(f"  Entry Lists: {entry_lists}")

                if 'Choice' in expected_type or field_type_code == 2:
                    choice_values = getattr(field, 'choiceValues', None)
                    if choice_values:
                        choice_names = [cv.name if hasattr(cv, 'name') else str(cv) for cv in choice_values]
                        print(f"  Choices: {', '.join(choice_names)}")

                print()
            else:
                missing_fields.append(expected_name)

        # Check for extra fields
        for field_name in found_fields:
            if field_name not in expected_fields:
                extra_fields.append(field_name)

        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Total Fields Found: {len(fields)}")
        print(f"Expected Fields Matched: {len(matched_fields)}/{len(expected_fields)}")

        if missing_fields:
            print(f"\n[X] Missing Fields ({len(missing_fields)}):")
            for field_name in missing_fields:
                print(f"  - {field_name} ({expected_fields[field_name]})")
        else:
            print("\n[OK] All expected fields present!")

        if extra_fields:
            print(f"\nExtra Fields ({len(extra_fields)}):")
            for field_name in extra_fields:
                field = found_fields[field_name]
                field_type_code = getattr(field, 'fieldType', None) or getattr(field, 'type', 'Unknown')
                field_type = TYPE_CODES.get(field_type_code, f'Type {field_type_code}')
                print(f"  + {field_name} ({field_type})")

        # Save to JSON
        os.makedirs('data', exist_ok=True)
        output_path = 'data/articles_schema.json'

        # Convert Pydantic models to dicts for JSON serialization
        obj_dict = {
            'id': getattr(obj, 'id', None),
            'name': getattr(obj, 'name', None),
            'apiName': getattr(obj, 'apiName', None),
            'singularName': getattr(obj, 'singularName', None),
            'pluralName': getattr(obj, 'pluralName', None)
        }

        fields_dicts = []
        for field in fields:
            # Try to convert Pydantic model to dict
            if hasattr(field, 'model_dump'):
                field_dict = field.model_dump()
            elif hasattr(field, 'dict'):
                field_dict = field.dict()
            else:
                # Manual conversion for older versions
                field_dict = {
                    'name': getattr(field, 'name', None),
                    'fieldType': getattr(field, 'fieldType', None),
                    'isRequired': getattr(field, 'isRequired', None),
                    'displayName': getattr(field, 'displayName', None)
                }
            fields_dicts.append(field_dict)

        output_data = {
            'retrieved_at': datetime.now().isoformat(),
            'object': obj_dict,
            'total_fields': len(fields),
            'fields': fields_dicts,
            'comparison': {
                'expected_fields': expected_fields,
                'matched_fields': matched_fields,
                'missing_fields': missing_fields,
                'extra_fields': extra_fields
            }
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"\n[OK] Schema saved to: {output_path}")
        print("=" * 80)

        # Exit with error code if fields are missing
        if missing_fields:
            logger.warning("Schema validation failed - missing required fields")
            sys.exit(1)

    except ImportError as e:
        logger.error(f"\n[X] Missing dependency: {str(e)}")
        logger.error("Run: pip install dealcloud-sdk")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"\n[X] Configuration error: {str(e)}")
        logger.error("Check your .env file for DealCloud credentials")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n[X] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
