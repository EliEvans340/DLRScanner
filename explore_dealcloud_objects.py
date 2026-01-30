#!/usr/bin/env python3
"""
DealCloud Objects Explorer

Lists all objects in DealCloud to verify the Articles object exists.

Usage:
    python explore_dealcloud_objects.py
"""

import json
import os
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dealcloud_explorer import get_client, setup_logging


def main():
    """List all DealCloud objects."""
    logger = setup_logging('explore_objects')

    logger.info("=" * 80)
    logger.info("DealCloud Objects Explorer")
    logger.info("=" * 80)

    try:
        # Connect to DealCloud
        logger.info("Connecting to DealCloud...")
        dc = get_client()
        logger.info("Connected successfully!")

        # Get all objects
        logger.info("\nRetrieving objects...")
        objects = dc.get_objects()

        if not objects:
            logger.warning("No objects found in DealCloud")
            return

        logger.info(f"Found {len(objects)} objects\n")

        # Display objects
        logger.info("=" * 80)
        logger.info("DEALCLOUD OBJECTS")
        logger.info("=" * 80)

        articles_found = False
        articles_objects = []

        for obj in objects:
            # Get object details from Pydantic model
            obj_id = getattr(obj, 'id', 'N/A')
            api_name = getattr(obj, 'apiName', None) or getattr(obj, 'name', 'Unknown')
            singular = getattr(obj, 'singularName', api_name)
            plural = getattr(obj, 'pluralName', singular)

            # Check if this is the Articles object
            is_articles = any([
                'article' in str(api_name).lower(),
                'article' in str(singular).lower(),
                'article' in str(plural).lower()
            ])

            if is_articles:
                articles_found = True
                articles_objects.append(obj)
                marker = " <-- ARTICLES OBJECT FOUND!"
            else:
                marker = ""

            # Display object info
            print(f"\nObject ID: {obj_id}")
            print(f"  API Name: {api_name}")
            print(f"  Singular: {singular}")
            print(f"  Plural: {plural}{marker}")

        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Total Objects: {len(objects)}")

        if articles_found:
            print(f"\n[OK] Articles object(s) FOUND: {len(articles_objects)}")
            for obj in articles_objects:
                api_name = getattr(obj, 'apiName', None) or getattr(obj, 'name', 'Unknown')
                obj_id = getattr(obj, 'id', 'N/A')
                print(f"  - {api_name} (ID: {obj_id})")
        else:
            print("\n[X] No Articles object found")
            print("  --> You may need to create the Articles object in DealCloud")

        # Save to JSON
        os.makedirs('data', exist_ok=True)
        output_path = 'data/dealcloud_objects.json'

        # Convert Pydantic models to dicts for JSON serialization
        objects_dicts = []
        for obj in objects:
            obj_dict = {
                'id': getattr(obj, 'id', None),
                'name': getattr(obj, 'name', None),
                'apiName': getattr(obj, 'apiName', None),
                'singularName': getattr(obj, 'singularName', None),
                'pluralName': getattr(obj, 'pluralName', None),
                'entryListType': getattr(obj, 'entryListType', None),
                'entryListSubType': getattr(obj, 'entryListSubType', None),
                'entryListId': getattr(obj, 'entryListId', None)
            }
            objects_dicts.append(obj_dict)

        output_data = {
            'retrieved_at': datetime.now().isoformat(),
            'total_objects': len(objects),
            'articles_found': articles_found,
            'objects': objects_dicts
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"\n[OK] Results saved to: {output_path}")
        print("=" * 80)

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
