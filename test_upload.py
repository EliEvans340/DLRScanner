#!/usr/bin/env python3
"""
Test DealCloud Upload

Tests uploading a few articles to DealCloud with Type="Testing".
"""

import json
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dealcloud_uploader import DealCloudUploader


def main():
    """Test upload of a few articles."""

    # Load latest articles file
    articles_file = 'data/articles_20260130.json'

    print("=" * 60)
    print("DealCloud Upload Test")
    print("=" * 60)
    print(f"\nLoading articles from: {articles_file}")

    with open(articles_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    all_articles = data.get('articles', [])
    print(f"Found {len(all_articles)} articles in file")

    # Take first 3 articles for testing
    test_articles = all_articles[:3]
    print(f"Testing with first {len(test_articles)} articles")

    # Ensure they're marked as Testing type
    for article in test_articles:
        article['Type'] = 'Testing'

    print("\nArticles to upload:")
    for i, article in enumerate(test_articles, 1):
        headline = article.get('Headline', 'No headline')[:50]
        print(f"  {i}. {headline}...")

    # Create uploader and test connection
    print("\nConnecting to DealCloud...")
    try:
        uploader = DealCloudUploader()
        print("[OK] Connected successfully")
    except Exception as e:
        print(f"[X] Connection failed: {str(e)}")
        return 1

    # Test connection
    print("\nTesting connection...")
    if uploader.test_connection():
        print("[OK] Connection test passed")
    else:
        print("[X] Connection test failed")
        return 1

    # Upload articles
    print(f"\nUploading {len(test_articles)} articles...")
    try:
        stats = uploader.upload_articles(test_articles)

        print("\n" + "=" * 60)
        print("UPLOAD RESULTS")
        print("=" * 60)
        print(f"Total Articles:        {stats['total_articles']}")
        print(f"Successfully Uploaded: {stats['uploaded']}")
        print(f"Failed:                {stats['failed']}")
        print(f"Success Rate:          {stats['success_rate']:.1f}%")

        if stats['entry_ids']:
            print(f"\nEntry IDs created:")
            for entry_id in stats['entry_ids']:
                print(f"  - {entry_id}")

        print("=" * 60)

        if stats['uploaded'] > 0:
            print("\n[OK] Upload test successful!")
            print("Check DealCloud Articles object to verify the test articles")
            return 0
        else:
            print("\n[X] Upload test failed - no articles uploaded")
            return 1

    except Exception as e:
        print(f"\n[X] Upload failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
