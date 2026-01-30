"""
Download DealCloud data for validation using AWHEmailScanner's downloader
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add AWHEmailScanner to path
awh_path = os.getenv('AWH_EMAILSCANNER_PATH', '../AWHEmailScanner/src')
awh_path = os.path.abspath(awh_path)
sys.path.insert(0, awh_path)

# Change to AWHEmailScanner directory so data downloads to the right place
awh_dir = os.path.dirname(awh_path)
os.chdir(awh_dir)

print(f"Changed to AWHEmailScanner directory: {awh_dir}")
print(f"Data will be downloaded to: {os.path.join(awh_dir, 'data')}")
print()

# Check for required credentials
if not all([
    os.getenv('DEALCLOUD_SITE_URL'),
    os.getenv('DEALCLOUD_CLIENT_ID'),
    os.getenv('DEALCLOUD_CLIENT_SECRET')
]):
    print("=" * 60)
    print("ERROR: Missing DealCloud credentials")
    print("=" * 60)
    print()
    print("Please update the .env file with your DealCloud credentials:")
    print("  DEALCLOUD_SITE_URL")
    print("  DEALCLOUD_CLIENT_ID")
    print("  DEALCLOUD_CLIENT_SECRET")
    print()
    print("You can find these in your DealCloud account settings.")
    sys.exit(1)

print("DealCloud credentials found. Starting download...")
print()

# Import and run the downloader
try:
    from dealcloud_data_downloader import download_data

    success = download_data()

    if success:
        print()
        print("=" * 60)
        print("SUCCESS: DealCloud data downloaded successfully!")
        print("=" * 60)
        print()
        print("Downloaded files:")
        data_dir = os.path.join(awh_dir, 'data')
        for file in ['hotel_data.csv', 'company_data.csv', 'contact_data.csv',
                     'deal_data.csv', 'deal_process_data.json', 'email_data.csv']:
            file_path = os.path.join(data_dir, file)
            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                print(f"  - {file} ({size:,} bytes)")

        print()
        print("You can now run the DLR scanner with validation enabled.")
    else:
        print()
        print("=" * 60)
        print("WARNING: Some downloads may have failed")
        print("=" * 60)
        print("Check the error messages above.")
        sys.exit(1)

except ImportError as e:
    print(f"Error importing AWHEmailScanner modules: {e}")
    print(f"Make sure AWHEmailScanner is at: {awh_path}")
    sys.exit(1)
except Exception as e:
    print(f"Error downloading data: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
