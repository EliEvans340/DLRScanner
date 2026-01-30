"""Export DLRScanner results to CSV for easy review"""
import json
import csv
import glob
import sys
from datetime import datetime

# Get the most recent articles JSON file
json_files = sorted(glob.glob('data/articles_*.json'), reverse=True)
if not json_files:
    print("No articles JSON files found!")
    sys.exit(1)

json_file = json_files[0]
print(f"Reading: {json_file}")

with open(json_file, 'r', encoding='utf-8') as f:
    data = json.load(f)
    articles = data['articles']

# Generate output filename
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
csv_file = f"data/articles_export_{timestamp}.csv"

# Prepare CSV data
csv_rows = []

for i, article in enumerate(articles, 1):
    # Get metadata
    metadata = article.get('_metadata', {})

    # Get matched entities
    hotel_ids = article.get('Hotels', [])
    company_ids = article.get('Companies', [])
    contact_ids = article.get('Contacts', [])

    # Get original entities
    orig_hotels = metadata.get('original_hotels', [])
    orig_companies = metadata.get('original_companies', [])
    orig_contacts = metadata.get('original_contacts', [])

    # Count matches
    matched_hotels = sum(1 for h in hotel_ids if h is not None) if isinstance(hotel_ids, list) else 0
    matched_companies = sum(1 for c in company_ids if c is not None) if isinstance(company_ids, list) else 0
    matched_contacts = sum(1 for c in contact_ids if c is not None) if isinstance(contact_ids, list) else 0

    # Create lists of matched entity names
    hotel_names = []
    hotel_matches = []
    for idx, hotel in enumerate(orig_hotels):
        name = hotel.get('name', 'N/A')
        city = hotel.get('city', '')
        state = hotel.get('state', '')
        location = f"{city}, {state}".strip(', ') if city or state else ''
        full_name = f"{name} ({location})" if location else name
        hotel_names.append(full_name)

        if idx < len(hotel_ids) and hotel_ids[idx]:
            hotel_matches.append(f"{full_name} [ID:{hotel_ids[idx]}]")

    company_names = []
    company_matches = []
    for idx, company in enumerate(orig_companies):
        name = company.get('name', 'N/A')
        role = company.get('role', '')
        full_name = f"{name} ({role})" if role else name
        company_names.append(full_name)

        if idx < len(company_ids) and company_ids[idx]:
            company_matches.append(f"{full_name} [ID:{company_ids[idx]}]")

    contact_names = []
    contact_matches = []
    for idx, contact in enumerate(orig_contacts):
        name = contact.get('name', 'N/A')
        title = contact.get('title', '')
        company = contact.get('company', '')
        full_name = f"{name} - {title} at {company}".strip(' - at ')
        contact_names.append(full_name)

        if idx < len(contact_ids) and contact_ids[idx]:
            contact_matches.append(f"{full_name} [ID:{contact_ids[idx]}]")

    row = {
        'Article_Number': metadata.get('article_number', i),
        'Type': article.get('Type', 'Testing'),
        'Source': article.get('Source', '')[:60],
        'Headline': article.get('Headline', '')[:100],
        'Article_Text': article.get('ArticleText', '')[:200] + '...' if len(article.get('ArticleText', '')) > 200 else article.get('ArticleText', ''),
        'Publish_Date': article.get('PublishDate', ''),

        # Counts
        'Total_Hotels': len(orig_hotels),
        'Matched_Hotels': matched_hotels,
        'Total_Companies': len(orig_companies),
        'Matched_Companies': matched_companies,
        'Total_Contacts': len(orig_contacts),
        'Matched_Contacts': matched_contacts,

        # Entity lists
        'Hotels_Extracted': '; '.join(hotel_names),
        'Hotels_Matched': '; '.join(hotel_matches) if hotel_matches else 'None',
        'Companies_Extracted': '; '.join(company_names),
        'Companies_Matched': '; '.join(company_matches) if company_matches else 'None',
        'Contacts_Extracted': '; '.join(contact_names),
        'Contacts_Matched': '; '.join(contact_matches) if contact_matches else 'None',
    }

    csv_rows.append(row)

# Write CSV
print(f"Exporting {len(csv_rows)} articles to CSV...")
with open(csv_file, 'w', newline='', encoding='utf-8') as f:
    fieldnames = [
        'Article_Number', 'Type', 'Source', 'Headline', 'Article_Text', 'Publish_Date',
        'Total_Hotels', 'Matched_Hotels', 'Total_Companies', 'Matched_Companies',
        'Total_Contacts', 'Matched_Contacts',
        'Hotels_Extracted', 'Hotels_Matched',
        'Companies_Extracted', 'Companies_Matched',
        'Contacts_Extracted', 'Contacts_Matched'
    ]

    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(csv_rows)

print(f"Exported to: {csv_file}")
print()
print("Summary:")
print(f"  Total articles: {len(csv_rows)}")
print(f"  Total hotels extracted: {sum(row['Total_Hotels'] for row in csv_rows)}")
print(f"  Total hotels matched: {sum(row['Matched_Hotels'] for row in csv_rows)}")
print(f"  Total companies extracted: {sum(row['Total_Companies'] for row in csv_rows)}")
print(f"  Total companies matched: {sum(row['Matched_Companies'] for row in csv_rows)}")
print(f"  Total contacts extracted: {sum(row['Total_Contacts'] for row in csv_rows)}")
print(f"  Total contacts matched: {sum(row['Matched_Contacts'] for row in csv_rows)}")
