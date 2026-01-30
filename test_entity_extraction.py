#!/usr/bin/env python3
"""
Test Entity Extraction with Updated Instructions

Tests the new requirements:
1. Full hotel names (brand + location)
2. Skipping development projects
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from entity_extractor import EntityExtractor


def main():
    """Test entity extraction with sample articles."""

    print("=" * 80)
    print("Entity Extraction Test - Updated Requirements")
    print("=" * 80)

    # Initialize extractor
    extractor = EntityExtractor()

    # Test Case 1: Existing operating hotels with full names
    test_article_1 = {
        "article_number": 1,
        "headline": "Dreamscape Hospitality Assumes Management",
        "article_text": """Dreamscape Hospitality has assumed management of three Marriott-branded hotels
        across Oklahoma and Louisiana. The newly added properties include the 90-suite Residence Inn Tulsa South,
        the 76-suite SpringHill Suites Tulsa, and the 89-room Courtyard Lafayette Airport.
        All three hotels are owned by Verge Mobile.""",
        "source_subject": "Test Article",
        "source_from": "test@example.com",
        "source_date": "2026-01-30"
    }

    # Test Case 2: Development project (should extract NO hotels)
    test_article_2 = {
        "article_number": 2,
        "headline": "JW Marriott Conversion in Louisville",
        "article_text": """Developers are eyeing a downtown Louisville office tower for a $185 million
        conversion into a JW Marriott. Ghoman Hotels & Resorts, alongside building owner KennMar, plans to
        turn the Fifth Third Bank Building, at 401 S. Fourth Street, into a 418-room hotel, having secured
        franchise approval for the luxury hotel brand. Set to open in late 2027 or 2028, the converted
        26-story office tower would also include 15,000 square feet of meeting, event, and ballroom space.""",
        "source_subject": "Test Article",
        "source_from": "test@example.com",
        "source_date": "2026-01-30"
    }

    # Test Case 3: Mix of existing hotel + development mention
    test_article_3 = {
        "article_number": 3,
        "headline": "Hyatt Lodge Renovation",
        "article_text": """The Hyatt Lodge Oak Brook, in Oak Brook, Illinois, is currently undergoing
        a renovation of their guestrooms and corridor spaces. The property will remain open during construction.""",
        "source_subject": "Test Article",
        "source_from": "test@example.com",
        "source_date": "2026-01-30"
    }

    test_articles = [test_article_1, test_article_2, test_article_3]

    print("\nProcessing 3 test articles...")
    print()

    # Extract entities
    results = extractor.extract_from_articles_batched(test_articles, batch_size=3)

    # Display results
    for i, result in enumerate(results, 1):
        print("=" * 80)
        print(f"TEST CASE {i}: {result['headline']}")
        print("=" * 80)

        hotels = result.get('hotels', [])
        companies = result.get('companies', [])

        print(f"\nHotels extracted: {len(hotels)}")
        if hotels:
            for j, hotel in enumerate(hotels, 1):
                print(f"  {j}. Name: {hotel.get('name', 'N/A')}")
                print(f"     City: {hotel.get('city', 'N/A')}")
                print(f"     State: {hotel.get('state', 'N/A')}")
                if hotel.get('brand'):
                    print(f"     Brand: {hotel.get('brand')}")
        else:
            print("  (No hotels extracted)")

        print(f"\nCompanies extracted: {len(companies)}")
        if companies:
            for j, company in enumerate(companies, 1):
                print(f"  {j}. {company.get('name', 'N/A')} - {company.get('role', 'N/A')}")

        print()

    # Validation
    print("=" * 80)
    print("VALIDATION")
    print("=" * 80)

    case1_hotels = results[0].get('hotels', [])
    case2_hotels = results[1].get('hotels', [])
    case3_hotels = results[2].get('hotels', [])

    print("\nTest Case 1 (Operating Hotels):")
    if len(case1_hotels) == 3:
        print("  [OK] Extracted 3 hotels as expected")

        # Check for full names
        names = [h.get('name', '') for h in case1_hotels]
        full_names_check = all([
            'Residence Inn Tulsa South' in str(names) or 'Tulsa South' in str(names),
            'SpringHill Suites Tulsa' in str(names) or 'Suites Tulsa' in str(names),
            'Courtyard Lafayette Airport' in str(names) or 'Lafayette Airport' in str(names)
        ])

        if full_names_check:
            print("  [OK] Hotel names include location identifiers")
        else:
            print("  [WARNING] Some hotel names may be missing location identifiers")
            print(f"  Names extracted: {names}")
    else:
        print(f"  [FAIL] Expected 3 hotels, got {len(case1_hotels)}")

    print("\nTest Case 2 (Development Project):")
    if len(case2_hotels) == 0:
        print("  [OK] Correctly extracted 0 hotels (development project)")
    else:
        print(f"  [FAIL] Expected 0 hotels, got {len(case2_hotels)} (should skip development projects)")
        print(f"  Hotels extracted: {[h.get('name') for h in case2_hotels]}")

    print("\nTest Case 3 (Existing Hotel with Renovation):")
    if len(case3_hotels) == 1:
        print("  [OK] Extracted 1 hotel as expected")
        hotel_name = case3_hotels[0].get('name', '')
        if 'Oak Brook' in hotel_name or 'Hyatt Lodge Oak Brook' in hotel_name:
            print(f"  [OK] Hotel name includes location: {hotel_name}")
        else:
            print(f"  [WARNING] Hotel name may be incomplete: {hotel_name}")
    else:
        print(f"  [FAIL] Expected 1 hotel, got {len(case3_hotels)}")

    print("\n" + "=" * 80)


if __name__ == '__main__':
    main()
