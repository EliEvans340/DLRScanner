"""
Re-run entity extraction and validation on existing parsed articles
"""
import json
import sys
import os
sys.path.insert(0, 'src')

from entity_extractor import EntityExtractor
from validation_orchestrator import ValidationOrchestrator
from article_preparator import ArticlePreparator
from report_generator import ReportGenerator
from datetime import datetime

print("Loading existing articles...")
with open('data/articles_20260128.json', 'r') as f:
    data = json.load(f)
    articles = data['articles']

print(f"Loaded {len(articles)} articles")
print()

# Convert from DealCloud format back to internal format
print("Converting articles to internal format...")
internal_articles = []
for i, article in enumerate(articles, 1):
    internal = {
        "article_number": i,
        "headline": article.get("Headline", ""),
        "article_text": article.get("ArticleText", ""),
        "source_subject": article.get("Source", ""),
        "source_from": article.get("_metadata", {}).get("source_from", ""),
        "source_date": article.get("PublishDate", "")
    }
    internal_articles.append(internal)

# Step 1: Extract entities
print("="*60)
print("Step 1: Extracting entities...")
print("="*60)
extractor = EntityExtractor()
articles_with_entities = extractor.extract_from_articles(internal_articles)
extractor_stats = extractor.get_stats()

print(f"\nExtracted:")
print(f"  Hotels: {extractor_stats['hotels_extracted']}")
print(f"  Companies: {extractor_stats['companies_extracted']}")
print(f"  Contacts: {extractor_stats['contacts_extracted']}")
print(f"  Failed: {extractor_stats['failed_processing']}")
print()

# Step 2: Validate entities
print("="*60)
print("Step 2: Validating entities against DealCloud...")
print("="*60)
validator = ValidationOrchestrator()
validated_articles = validator.validate_articles(articles_with_entities)
validation_summary = validator.get_validation_summary(validated_articles)

print(f"\nValidation Results:")
print(f"  Hotels: {validation_summary['matched_hotels']}/{validation_summary['total_hotels']} matched ({validation_summary['hotel_match_rate']:.1%})")
print(f"  Companies: {validation_summary['matched_companies']}/{validation_summary['total_companies']} matched ({validation_summary['company_match_rate']:.1%})")
print(f"  Contacts: {validation_summary['matched_contacts']}/{validation_summary['total_contacts']} matched ({validation_summary['contact_match_rate']:.1%})")
print()

# Step 3: Prepare for DealCloud
print("="*60)
print("Step 3: Preparing articles for DealCloud...")
print("="*60)
preparator = ArticlePreparator()
prepared_articles = preparator.prepare_articles(validated_articles)
prepared_summary = preparator.get_summary(prepared_articles)

output_path = preparator.export_to_json(prepared_articles)
print(f"\nExported to: {output_path}")
print(f"  Total articles: {prepared_summary['total_articles']}")
print(f"  With hotels: {prepared_summary['articles_with_hotels']}")
print(f"  With companies: {prepared_summary['articles_with_companies']}")
print(f"  With contacts: {prepared_summary['articles_with_contacts']}")
print()

# Generate report
print("="*60)
print("Generating report...")
print("="*60)
reporter = ReportGenerator()
report = reporter.generate_processing_report(
    emails_fetched=2,
    parser_stats={"newsletters_processed": 1, "articles_extracted": 15, "failed_processing": 1, "failed_newsletters": []},
    extractor_stats=extractor_stats,
    validation_summary=validation_summary,
    prepared_summary=prepared_summary,
    start_time=datetime.now(),
    end_time=datetime.now()
)

reporter.save_report(report)
reporter.print_report(report)

print("\nDone!")
