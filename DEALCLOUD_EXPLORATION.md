# DealCloud Schema Exploration

This document explains how to use the DealCloud exploration scripts to verify the Articles object schema before implementing data upload functionality.

## Overview

The DealCloud exploration scripts help you:
1. Verify connection to DealCloud API
2. List all available objects in DealCloud
3. Inspect the Articles object schema in detail
4. Validate that the schema matches our requirements

## Prerequisites

### 1. Install Dependencies

Install the required DealCloud SDK:

```bash
pip install dealcloud-sdk
```

Or install all dependencies:

```bash
pip install -r requirements.txt
```

### 2. Configure Credentials

Add your DealCloud credentials to the `.env` file:

```bash
# DealCloud API Configuration
DEALCLOUD_SITE_URL=awhpartners.dealcloud.com
DEALCLOUD_CLIENT_ID=1020196
DEALCLOUD_CLIENT_SECRET=your_client_secret_here
```

You can get these credentials from:
- **Site URL**: Your DealCloud site (e.g., `yourcompany.dealcloud.com`)
- **Client ID & Secret**: DealCloud Settings → API → Create API Client

## Exploration Scripts

### 1. List All Objects

**Script:** `explore_dealcloud_objects.py`

**Purpose:** Lists all objects in DealCloud to verify the Articles object exists.

**Usage:**
```bash
python explore_dealcloud_objects.py
```

**Output:**
- Lists all DealCloud objects with their IDs, API names, and display names
- Highlights the Articles object if found
- Saves results to `data/dealcloud_objects.json`

**Example Output:**
```
================================================================================
DEALCLOUD OBJECTS
================================================================================

Object ID: 12345
  API Name: Articles
  Singular: Article
  Plural: Articles ← ARTICLES OBJECT FOUND!

Object ID: 67890
  API Name: Hotels
  Singular: Hotel
  Plural: Hotels

...

================================================================================
SUMMARY
================================================================================
Total Objects: 15

✓ Articles object(s) FOUND: 1
  - Articles (ID: 12345)

✓ Results saved to: data/dealcloud_objects.json
```

### 2. Explore Articles Schema

**Script:** `explore_articles_schema.py`

**Purpose:** Gets detailed schema and fields for the Articles object.

**Usage:**
```bash
# Default: explores "Articles" object
python explore_articles_schema.py

# Specify different object name
python explore_articles_schema.py --object-name "Article"
```

**Output:**
- Object information (ID, API name, display names)
- Detailed field information:
  - Field name (API name and display name)
  - Field type (Text, Multi-Reference, Date, Choice, etc.)
  - Required/Optional status
  - Max length (for text fields)
  - Reference object (for multi-reference fields)
  - Choice values (for choice fields)
- Comparison with expected schema
- Lists missing fields, matched fields, and extra fields
- Saves schema to `data/articles_schema.json`

**Example Output:**
```
================================================================================
OBJECT INFORMATION
================================================================================
Object ID: 12345
API Name: Articles
Singular: Article
Plural: Articles

================================================================================
FIELD DETAILS
================================================================================

Field: ArticleText
  Display Name: Article Text
  Type: MultiLineText
  Required: Yes
  Max Length: 50000
--------------------------------------------------------------------------------

Field: Headline
  Display Name: Headline
  Type: Text
  Required: Yes
  Max Length: 500
--------------------------------------------------------------------------------

Field: Hotels
  Display Name: Hotels
  Type: MultiReference
  Required: No
  References: Hotels
--------------------------------------------------------------------------------

...

================================================================================
SCHEMA COMPARISON
================================================================================
✓ ArticleText
  Expected: Text (Multi-line)
  Actual: MultiLineText

✓ Headline
  Expected: Text (Single-line)
  Actual: Text

✓ Hotels
  Expected: Multi-Reference → Hotels
  Actual: MultiReference
  References: Hotels

...

================================================================================
SUMMARY
================================================================================
Total Fields Found: 10
Expected Fields Matched: 8/8

✓ All expected fields present!

Extra Fields (2):
  + CreatedDate (DateTime)
  + ModifiedDate (DateTime)

✓ Schema saved to: data/articles_schema.json
```

### 3. Verify Schema (Automated)

**Script:** `verify_articles_schema.py`

**Purpose:** Automated validation that the Articles schema matches our requirements. Useful for CI/CD pipelines.

**Usage:**
```bash
# Default: verifies "Articles" object
python verify_articles_schema.py

# Show detailed field comparison
python verify_articles_schema.py --verbose

# Verify different object name
python verify_articles_schema.py --object-name "Article"
```

**Exit Codes:**
- `0`: Schema validation passed (all fields match)
- `1`: Schema validation failed (missing fields or type mismatches)
- `2`: Connection or configuration error

**Output:**
- Concise pass/fail status for each field
- Detailed issues for failed fields
- Summary with pass/fail count
- Saves report to `data/schema_verification_report.json`

**Example Output (Success):**
```
================================================================================
DealCloud Schema Verifier - Articles
================================================================================
✓ Connected to DealCloud
✓ Found object: Articles
✓ Retrieved 10 fields

================================================================================
FIELD VERIFICATION
================================================================================

✓ ArticleText
✓ Headline
✓ Hotels
✓ Companies
✓ Contacts
✓ Source
✓ PublishDate
✓ Type

================================================================================
VERIFICATION SUMMARY
================================================================================
Fields Verified: 8/8

✓ Schema verification PASSED
  All required fields are correctly configured
  → Ready to proceed with data upload

✓ Verification report saved to: data/schema_verification_report.json
```

**Example Output (Failed):**
```
================================================================================
FIELD VERIFICATION
================================================================================

✓ ArticleText
✓ Headline
✗ Hotels
  - Reference mismatch: expected 'Hotels', got 'Hotel'
✗ Type
  - Missing choice values: ['Testing']
✗ PublishDate
  - Field 'PublishDate' not found in DealCloud

================================================================================
VERIFICATION SUMMARY
================================================================================
Fields Verified: 5/8

✗ Schema verification FAILED
  → Fix the issues above in DealCloud before uploading data
```

## Workflow

### Step 1: Verify Connection

First, verify you can connect to DealCloud and see all objects:

```bash
python explore_dealcloud_objects.py
```

**What to check:**
- Script connects successfully
- Articles object appears in the list
- Note the exact API name (might be "Article" or "Articles")

### Step 2: Inspect Schema

Examine the Articles schema in detail:

```bash
python explore_articles_schema.py
```

**What to check:**
- All 8 required fields are present:
  - ArticleText
  - Headline
  - Hotels
  - Companies
  - Contacts
  - Source
  - PublishDate
  - Type
- Field types match the expected types
- Multi-reference fields point to the correct objects (Hotels, Companies, Contacts)
- Type field has choice values: "Actual" and "Testing"

### Step 3: Automated Validation

Run the automated verification:

```bash
python verify_articles_schema.py --verbose
```

**What to check:**
- Exit code is 0 (schema validation passed)
- All 8 fields show ✓ (passed)
- No issues reported

### Step 4: Fix Issues (If Needed)

If verification fails:

1. Review the issues reported in the output
2. Go to DealCloud Settings → Data Model → Objects → Articles
3. Fix the reported issues:
   - Add missing fields
   - Correct field types
   - Fix reference targets
   - Add missing choice values
4. Re-run verification until it passes

## Common Issues & Solutions

### Issue: "Object 'Articles' not found"

**Cause:** The Articles object hasn't been created yet, or has a different name.

**Solution:**
1. Run `python explore_dealcloud_objects.py` to see all objects
2. Create the Articles object in DealCloud (Settings → Data Model → Objects)
3. Or use the correct object name with `--object-name` parameter

### Issue: "Missing required DealCloud credentials"

**Cause:** DealCloud credentials not set in `.env` file.

**Solution:**
1. Copy `.env.template` to `.env`
2. Fill in your DealCloud credentials:
   ```bash
   DEALCLOUD_SITE_URL=yoursite.dealcloud.com
   DEALCLOUD_CLIENT_ID=your_client_id
   DEALCLOUD_CLIENT_SECRET=your_client_secret
   ```

### Issue: "dealcloud-sdk is not installed"

**Cause:** DealCloud SDK package not installed.

**Solution:**
```bash
pip install dealcloud-sdk
```

### Issue: "Type mismatch" or "Reference mismatch"

**Cause:** Field exists but has wrong type or reference target.

**Solution:**
1. Go to DealCloud → Settings → Data Model → Objects → Articles
2. Find the problematic field
3. Edit the field to match the expected type/reference
4. Re-run verification

### Issue: "Missing choice values"

**Cause:** Type field exists but doesn't have "Actual" and "Testing" choices.

**Solution:**
1. Go to DealCloud → Settings → Data Model → Objects → Articles
2. Edit the "Type" field
3. Add choice values: "Actual" and "Testing"
4. Set default to "Testing" (recommended)
5. Re-run verification

### Issue: Connection timeout or authentication error

**Cause:** Invalid credentials, wrong site URL, or network issues.

**Solution:**
1. Verify your site URL (should be `yoursite.dealcloud.com`, no https://)
2. Verify your client ID and secret are correct
3. Check if you can access DealCloud in your browser
4. Contact DealCloud support if credentials are correct but connection fails

## Output Files

All exploration scripts save their results to the `data/` directory:

### `data/dealcloud_objects.json`
- Complete list of all DealCloud objects
- Created by: `explore_dealcloud_objects.py`
- Useful for: Finding object IDs and API names

### `data/articles_schema.json`
- Detailed Articles object schema
- All fields with types, requirements, and references
- Created by: `explore_articles_schema.py`
- Useful for: Reference when implementing upload scripts

### `data/schema_verification_report.json`
- Automated verification results
- Pass/fail status for each field
- Detailed issue descriptions
- Created by: `verify_articles_schema.py`
- Useful for: CI/CD integration, troubleshooting

## Next Steps

Once schema verification passes (all ✓):

1. **You're ready to implement data upload!** The Articles object is correctly configured.

2. **Create upload script:**
   - Reference the AWHEmailScanner's `dealcloud_uploader.py` for patterns
   - Use the field mapping from `src/article_preparator.py`
   - Implement batch upload with error handling

3. **Add upload to main scanner:**
   - Add `--upload` flag to `dlr_scanner.py`
   - Upload prepared articles after processing
   - Log upload results

4. **Test with Testing type first:**
   ```bash
   python src/dlr_scanner.py --type Testing --upload
   ```

5. **Verify uploads in DealCloud:**
   - Go to DealCloud → Articles
   - Filter by Type = "Testing"
   - Check article content, headlines, and entity references

6. **Switch to production:**
   ```bash
   python src/dlr_scanner.py --type Actual --upload
   ```

## Utility Module

All scripts use the `src/dealcloud_explorer.py` utility module, which provides:

- `get_client()`: Create authenticated DealCloud client
- `find_object_by_name(name)`: Find object by API or display name
- `get_object_fields(object_name)`: Get all fields for an object
- `format_field_info(field)`: Pretty-print field information
- `validate_credentials()`: Check if credentials are configured

You can import these utilities in your own scripts:

```python
from src.dealcloud_explorer import get_client, find_object_by_name

# Connect to DealCloud
dc = get_client()

# Find Articles object
articles_obj = find_object_by_name(dc, "Articles")
```

## Support

For questions or issues:

1. Check the "Common Issues & Solutions" section above
2. Review the main README.md for general DLRScanner documentation
3. Check DEALCLOUD_SCHEMA.md for schema specifications
4. Review the script source code for implementation details

## References

- **DEALCLOUD_SCHEMA.md**: Detailed field specifications for Articles object
- **src/article_preparator.py**: Field mapping from scanner output to DealCloud schema
- **AWHEmailScanner**: Reference implementation for DealCloud upload patterns
