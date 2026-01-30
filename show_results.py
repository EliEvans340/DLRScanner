"""Display validation results in a formatted table"""
import json
import sys
import glob

# Get the most recent articles JSON file
json_files = sorted(glob.glob('data/articles_*.json'), reverse=True)
if not json_files:
    print("No articles JSON files found!")
    sys.exit(1)

json_file = json_files[0]
print(f"Reading: {json_file}\n")

with open(json_file, 'r', encoding='utf-8') as f:
    data = json.load(f)
    articles = data['articles']

# Count validated entities
hotels_validated = 0
companies_validated = 0
contacts_validated = 0
total_hotels = 0
total_companies = 0
total_contacts = 0

validated_hotels = []
validated_companies = []
validated_contacts = []
unmatched_hotels = []

for article in articles:
    # Count hotels - check if Hotels array has EntryIDs
    hotel_ids = article.get('Hotels', [])
    if isinstance(hotel_ids, list) and hotel_ids:
        if '_metadata' in article and 'original_hotels' in article['_metadata']:
            orig_hotels = article['_metadata']['original_hotels']
            for i, hotel in enumerate(orig_hotels):
                total_hotels += 1
                if i < len(hotel_ids) and hotel_ids[i] is not None:
                    hotels_validated += 1
                    validated_hotels.append({
                        'name': hotel.get('name', 'N/A'),
                        'city': hotel.get('city', 'N/A'),
                        'state': hotel.get('state', 'N/A'),
                        'entry_id': hotel_ids[i]
                    })
                else:
                    unmatched_hotels.append({
                        'name': hotel.get('name', 'N/A'),
                        'city': hotel.get('city', 'N/A'),
                        'state': hotel.get('state', 'N/A')
                    })

    # Count companies - EntryIDs are in Companies array
    company_ids = article.get('Companies', [])
    if '_metadata' in article and 'original_companies' in article['_metadata']:
        orig_companies = article['_metadata']['original_companies']
        for i, company in enumerate(orig_companies):
            total_companies += 1
            if i < len(company_ids) and company_ids[i] is not None:
                companies_validated += 1
                validated_companies.append({
                    'name': company.get('name', 'N/A'),
                    'role': company.get('role', 'N/A'),
                    'entry_id': company_ids[i]
                })

    # Count contacts - EntryIDs are in Contacts array
    contact_ids = article.get('Contacts', [])
    if '_metadata' in article and 'original_contacts' in article['_metadata']:
        orig_contacts = article['_metadata']['original_contacts']
        for i, contact in enumerate(orig_contacts):
            total_contacts += 1
            if i < len(contact_ids) and contact_ids[i] is not None:
                contacts_validated += 1
                validated_contacts.append({
                    'name': contact.get('name', 'N/A'),
                    'title': contact.get('title', 'N/A'),
                    'company': contact.get('company', 'N/A'),
                    'entry_id': contact_ids[i]
                })

print('=' * 80)
print('VALIDATION SUMMARY')
print('=' * 80)
print(f'Hotels:    {hotels_validated}/{total_hotels} matched ({100*hotels_validated/total_hotels if total_hotels else 0:.1f}%)')
print(f'Companies: {companies_validated}/{total_companies} matched ({100*companies_validated/total_companies if total_companies else 0:.1f}%)')
print(f'Contacts:  {contacts_validated}/{total_contacts} matched ({100*contacts_validated/total_contacts if total_contacts else 0:.1f}%)')
print()

if validated_hotels:
    print('=' * 80)
    print(f'VALIDATED HOTELS ({len(validated_hotels)} total)')
    print('=' * 80)
    for i, hotel in enumerate(validated_hotels, 1):
        name = hotel['name'][:40]
        city = hotel['city'][:18]
        print(f'{i:2}. {name:<40} | {city:<18} | ID: {hotel["entry_id"]}')
    print()

print('=' * 80)
print(f'VALIDATED COMPANIES ({len(validated_companies)} total)')
print('=' * 80)
for i, company in enumerate(validated_companies[:20], 1):
    name = company['name'][:40]
    role = company['role'][:15]
    print(f'{i:2}. {name:<40} | {role:<15} | ID: {company["entry_id"]}')
if len(validated_companies) > 20:
    print(f'... and {len(validated_companies) - 20} more')
print()

print('=' * 80)
print(f'VALIDATED CONTACTS ({len(validated_contacts)} total)')
print('=' * 80)
if validated_contacts:
    for i, contact in enumerate(validated_contacts, 1):
        name = contact['name'][:30]
        title = contact['title'][:25]
        company = contact['company'][:20]
        print(f'{i}. {name:<30} | {title:<25} | {company:<20} | ID: {contact["entry_id"]}')
else:
    print('No contacts validated')
print()

if unmatched_hotels:
    print('=' * 80)
    print(f'UNMATCHED HOTELS ({len(unmatched_hotels)} total)')
    print('=' * 80)
    for i, hotel in enumerate(unmatched_hotels[:15], 1):
        name = hotel['name'][:40]
        city = hotel['city'][:18]
        print(f'{i:2}. {name:<40} | {city:<18}')
    if len(unmatched_hotels) > 15:
        print(f'... and {len(unmatched_hotels) - 15} more')
