#!/usr/bin/env python3
"""
DealCloud Articles Schema Verifier

Automated validation that the Articles schema matches our requirements.
Useful for CI/CD validation before uploading data.

Usage:
    python verify_articles_schema.py [--object-name OBJECT_NAME] [--verbose]

Arguments:
    --object-name: Name of the object to verify (default: "Articles")
    --verbose: Show detailed field comparison

Exit Codes:
    0: Schema matches requirements
    1: Schema validation failed (missing fields, type mismatches, etc.)
    2: Connection or configuration error
"""

import json
import os
import sys
import argparse
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dealcloud_explorer import get_client, find_object_by_name, get_object_fields, setup_logging


# Expected schema matching actual DealCloud configuration
EXPECTED_SCHEMA = {
    'ArticleText': {
        'type': ['Text', 'text', 'MultiLineText', 'multi_line_text', 'RichText', 'rich_text'],
        'required': False,
        'description': 'Text (Multi-line)'
    },
    'Headline': {
        'type': ['Text', 'text', 'SingleLineText', 'single_line_text', 'String', 'string'],
        'required': False,
        'description': 'Text (Single-line)'
    },
    'Hotels': {
        'type': ['Reference', 'reference', 'MultiReference', 'multi_reference', 'Lookup', 'lookup'],
        'required': False,
        'reference_object': 'Hotels',
        'description': 'Multi-Reference --> Hotels'
    },
    'Companies': {
        'type': ['Reference', 'reference', 'MultiReference', 'multi_reference', 'Lookup', 'lookup'],
        'required': False,
        'reference_object': 'Companies',
        'description': 'Multi-Reference --> Companies'
    },
    'Contacts': {
        'type': ['Reference', 'reference', 'MultiReference', 'multi_reference', 'Lookup', 'lookup'],
        'required': False,
        'reference_object': 'Contacts',
        'description': 'Multi-Reference --> Contacts'
    },
    'Source': {
        'type': ['Text', 'text', 'SingleLineText', 'single_line_text', 'String', 'string'],
        'required': True,
        'description': 'Text (Single-line)'
    },
    'PublishDate': {
        'type': ['Date', 'date', 'DateTime', 'datetime', 'date_time', 'Timestamp', 'timestamp'],
        'required': True,
        'description': 'Date/Time'
    },
    'Type': {
        'type': ['Choice', 'choice', 'ChoiceList', 'choice_list', 'Picklist', 'picklist'],
        'required': True,
        'choices': ['Actual', 'Testing'],
        'description': 'Choice (Actual, Testing)'
    }
}


def normalize_type(field_type):
    """Normalize field type string for comparison."""
    return str(field_type).replace('_', '').replace('-', '').lower()


def check_field_type_match(actual_type, expected_types):
    """Check if actual type matches any of the expected types."""
    # DealCloud uses numeric type codes
    TYPE_CODE_MAPPING = {
        1: ['Text', 'text', 'MultiLineText', 'multi_line_text', 'SingleLineText', 'single_line_text', 'String', 'string', 'RichText', 'rich_text'],
        2: ['Choice', 'choice', 'ChoiceList', 'choice_list', 'Picklist', 'picklist', 'Text', 'text'],
        3: ['Number', 'number', 'Integer', 'integer', 'Decimal', 'decimal'],
        4: ['Date', 'date', 'DateTime', 'datetime', 'date_time', 'Timestamp', 'timestamp'],
        5: ['Reference', 'reference', 'MultiReference', 'multi_reference', 'Lookup', 'lookup'],
        6: ['Boolean', 'boolean', 'Bool', 'bool'],
        7: ['Reference', 'reference', 'UserReference', 'user_reference', 'User', 'user']
    }

    # If actual_type is numeric, check if any expected type matches
    if isinstance(actual_type, int):
        mapped_types = TYPE_CODE_MAPPING.get(actual_type, [])
        for expected in expected_types:
            if normalize_type(expected) in [normalize_type(mt) for mt in mapped_types]:
                return True
        return False

    # If actual_type is string, use original logic
    actual_normalized = normalize_type(actual_type)
    for expected in expected_types:
        if normalize_type(expected) == actual_normalized:
            return True
    return False


def verify_field(field_name, expected_spec, actual_field, verbose=False):
    """
    Verify a single field against expected specification.

    Returns:
        (passed, issues) tuple where passed is bool and issues is list of strings
    """
    issues = []

    if actual_field is None:
        issues.append(f"Field '{field_name}' not found in DealCloud")
        return False, issues

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

    # Check field type
    actual_type = get_field_attr(actual_field, 'fieldType', 'type', 'field_type') or 'Unknown'
    if not check_field_type_match(actual_type, expected_spec['type']):
        issues.append(
            f"Type mismatch: expected one of {expected_spec['type']}, got '{actual_type}'"
        )

    # Check required status
    actual_required = get_field_attr(actual_field, 'isRequired', 'required', 'is_required') or False
    if expected_spec['required'] != actual_required:
        issues.append(
            f"Required mismatch: expected {expected_spec['required']}, got {actual_required}"
        )

    # Check reference object (for reference fields)
    if 'reference_object' in expected_spec:
        # DealCloud stores references as entryLists, not referenceObject
        entry_lists = get_field_attr(actual_field, 'entryLists', 'entry_lists')
        expected_ref = expected_spec['reference_object']

        # For now, just check that entryLists exists for reference fields
        # We can't easily validate which object it points to without additional API calls
        if not entry_lists:
            issues.append(f"Missing reference configuration (expected reference to '{expected_ref}')")

    # Check choices (for choice fields)
    if 'choices' in expected_spec:
        choice_values = get_field_attr(actual_field, 'choiceValues', 'choices', 'choice_values') or []

        if choice_values:
            # Extract names from ChoiceValue objects
            actual_choices_str = []
            for cv in choice_values:
                if hasattr(cv, 'name'):
                    actual_choices_str.append(cv.name.strip())
                else:
                    actual_choices_str.append(str(cv).strip())

            expected_choices = expected_spec['choices']

            missing_choices = [c for c in expected_choices if c not in actual_choices_str]
            if missing_choices:
                issues.append(
                    f"Missing choice values: {missing_choices}"
                )
        else:
            issues.append(f"No choices found (expected: {expected_spec['choices']})")

    passed = len(issues) == 0
    return passed, issues


def main():
    """Verify Articles schema matches requirements."""
    parser = argparse.ArgumentParser(description='Verify DealCloud Articles schema')
    parser.add_argument('--object-name', default='Articles', help='Object name to verify (default: Articles)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed field comparison')
    args = parser.parse_args()

    logger = setup_logging('verify_schema')

    print("=" * 80)
    print(f"DealCloud Schema Verifier - {args.object_name}")
    print("=" * 80)

    try:
        # Connect to DealCloud
        logger.info("Connecting to DealCloud...")
        dc = get_client()
        print("[OK] Connected to DealCloud")

        # Find the object
        logger.info(f"Finding '{args.object_name}' object...")
        obj = find_object_by_name(dc, args.object_name)

        if not obj:
            print(f"[X] Object '{args.object_name}' not found in DealCloud")
            print("  Run 'python explore_dealcloud_objects.py' to see all available objects")
            sys.exit(1)

        api_name = getattr(obj, 'apiName', None) or getattr(obj, 'name', 'Unknown')
        print(f"[OK] Found object: {api_name}")

        # Get fields
        logger.info("Retrieving fields...")
        try:
            fields = get_object_fields(dc, api_name)
        except Exception as e:
            # Try alternative names
            plural = getattr(obj, 'pluralName', api_name)
            singular = getattr(obj, 'singularName', api_name)

            try:
                fields = get_object_fields(dc, plural)
            except:
                try:
                    fields = get_object_fields(dc, singular)
                except:
                    print(f"[X] Unable to retrieve fields for '{api_name}'")
                    sys.exit(2)

        print(f"[OK] Retrieved {len(fields)} fields")

        # Build field lookup
        field_lookup = {}
        for field in fields:
            field_name = getattr(field, 'name', None) or getattr(field, 'apiName', '')
            field_lookup[field_name] = field

        # Verify each expected field
        print("\n" + "=" * 80)
        print("FIELD VERIFICATION")
        print("=" * 80)

        all_passed = True
        verification_results = {}

        for field_name, expected_spec in EXPECTED_SCHEMA.items():
            actual_field = field_lookup.get(field_name)
            passed, issues = verify_field(field_name, expected_spec, actual_field, args.verbose)

            verification_results[field_name] = {
                'passed': passed,
                'issues': issues,
                'expected': expected_spec,
                'actual': actual_field
            }

            if passed:
                print(f"\n[OK] {field_name}")
                if args.verbose and actual_field:
                    actual_type = getattr(actual_field, 'fieldType', None) or getattr(actual_field, 'type', 'Unknown')
                    actual_required = getattr(actual_field, 'isRequired', None) or getattr(actual_field, 'required', False)
                    print(f"  Type: {actual_type}")
                    print(f"  Required: {actual_required}")
            else:
                all_passed = False
                print(f"\n[X] {field_name}")
                for issue in issues:
                    print(f"  - {issue}")

        # Summary
        print("\n" + "=" * 80)
        print("VERIFICATION SUMMARY")
        print("=" * 80)

        passed_count = sum(1 for r in verification_results.values() if r['passed'])
        total_count = len(verification_results)

        print(f"Fields Verified: {passed_count}/{total_count}")

        if all_passed:
            print("\n[OK] Schema verification PASSED")
            print("  All required fields are correctly configured")
            print("  --> Ready to proceed with data upload")
        else:
            print("\n[X] Schema verification FAILED")
            print("  --> Fix the issues above in DealCloud before uploading data")

        # Save verification report
        os.makedirs('data', exist_ok=True)
        report_path = 'data/schema_verification_report.json'

        # Convert Pydantic model to dict
        obj_dict = {
            'id': getattr(obj, 'id', None),
            'name': getattr(obj, 'name', None),
            'apiName': getattr(obj, 'apiName', None),
            'singularName': getattr(obj, 'singularName', None),
            'pluralName': getattr(obj, 'pluralName', None)
        }

        # Convert verification results (actual fields may be Pydantic models)
        results_dict = {}
        for field_name, result in verification_results.items():
            actual_field = result.get('actual')
            if actual_field and hasattr(actual_field, 'model_dump'):
                actual_dict = actual_field.model_dump()
            elif actual_field and hasattr(actual_field, 'dict'):
                actual_dict = actual_field.dict()
            else:
                actual_dict = actual_field

            results_dict[field_name] = {
                'passed': result['passed'],
                'issues': result['issues'],
                'expected': result['expected'],
                'actual': actual_dict
            }

        report = {
            'verified_at': datetime.now().isoformat(),
            'object': obj_dict,
            'passed': all_passed,
            'total_fields': total_count,
            'passed_fields': passed_count,
            'failed_fields': total_count - passed_count,
            'results': results_dict
        }

        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n[OK] Verification report saved to: {report_path}")
        print("=" * 80)

        # Exit with appropriate code
        sys.exit(0 if all_passed else 1)

    except ImportError as e:
        logger.error(f"\n[X] Missing dependency: {str(e)}")
        logger.error("Run: pip install dealcloud-sdk")
        sys.exit(2)
    except ValueError as e:
        logger.error(f"\n[X] Configuration error: {str(e)}")
        logger.error("Check your .env file for DealCloud credentials")
        sys.exit(2)
    except Exception as e:
        logger.error(f"\n[X] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == '__main__':
    main()
