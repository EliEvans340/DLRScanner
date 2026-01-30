# DealCloud Articles Object Schema

This document specifies the exact fields to create in DealCloud for the Articles object.

## Object Name
**Articles** (or **Article** - singular form if preferred)

---

## Field Specifications

### 1. Headline
- **Field Type:** Text (Single Line)
- **Max Length:** 500 characters
- **Required:** Yes
- **Description:** The article headline or title from the newsletter
- **Example:** "Marriott Acquires New Property in Miami Beach"

### 2. ArticleText
- **Field Type:** Text (Multi-line) or Rich Text
- **Max Length:** 10,000+ characters (or unlimited if available)
- **Required:** Yes
- **Description:** The complete text content of the article
- **Example:** Full article body from the newsletter

### 3. Source
- **Field Type:** Text (Single Line)
- **Max Length:** 200 characters
- **Required:** Yes
- **Description:** The newsletter name or email subject line where this article originated
- **Example:** "Daily Lodging Report - January 30, 2026"

### 4. PublishDate
- **Field Type:** Date/Time
- **Required:** Yes
- **Description:** The date and time when the article/newsletter was published
- **Format:** ISO 8601 (YYYY-MM-DDTHH:MM:SS)
- **Example:** 2026-01-30T16:50:57+00:00

### 5. Type
- **Field Type:** Choice List / Dropdown / Picklist
- **Required:** Yes
- **Options:**
  - `Actual` - Production article from real newsletter processing
  - `Testing` - Test article for system validation
- **Default Value:** `Testing` (recommended for safety)
- **Description:** Indicates whether this is a production article or test data
- **Usage:** Allows easy filtering to separate production data from test runs

### 6. Hotels
- **Field Type:** Multi-Reference (Lookup)
- **References:** Hotels Object
- **Required:** No
- **Description:** List of hotel Entry IDs mentioned in this article
- **Example:** [424166, 424979, 428245]
- **Note:** Only matched/validated hotels are included; unmatched hotels are stored in metadata

### 7. Companies
- **Field Type:** Multi-Reference (Lookup)
- **References:** Companies Object
- **Required:** No
- **Description:** List of company Entry IDs mentioned in this article
- **Example:** [37688214, 10455610, 431589]

### 8. Contacts
- **Field Type:** Multi-Reference (Lookup)
- **References:** Contacts Object
- **Required:** No
- **Description:** List of contact Entry IDs mentioned in this article
- **Example:** [8721789, 8721722, 37411861]

---

## Additional Recommended Fields (Optional)

### 9. ArticleNumber
- **Field Type:** Number (Integer)
- **Description:** Sequential article number within the newsletter (for ordering)
- **Example:** 1, 2, 3...

### 10. ProcessedDate
- **Field Type:** Date/Time
- **Auto-populate:** Current timestamp
- **Description:** When this article was processed by DLRScanner

### 11. MatchQuality
- **Field Type:** Text or Choice List
- **Options:** "High", "Medium", "Low"
- **Description:** Overall quality of entity matching for this article
- **Calculation:** Based on percentage of entities matched

---

## Field Summary Table

| Field Name | Type | Required | Max Length | Lookup To |
|------------|------|----------|------------|-----------|
| Headline | Text | Yes | 500 | - |
| ArticleText | Multi-line Text | Yes | 10,000+ | - |
| Source | Text | Yes | 200 | - |
| PublishDate | Date/Time | Yes | - | - |
| Type | Choice List | Yes | - | - |
| Hotels | Multi-Reference | No | - | Hotels |
| Companies | Multi-Reference | No | - | Companies |
| Contacts | Multi-Reference | No | - | Contacts |

---

## DealCloud Setup Instructions

### Step 1: Create the Articles Object
1. Go to **Settings** → **Data Model** → **Objects**
2. Click **New Object**
3. Name: `Articles` or `Article`
4. Save

### Step 2: Add Fields
For each field above:
1. Click **Add Field** on the Articles object
2. Select the appropriate **Field Type**
3. Enter the **Field Name** exactly as specified
4. Set **Required** status
5. For Multi-References, select the target object
6. For Type field:
   - Create Choice List with values: `Actual`, `Testing`
   - Set default to `Testing`

### Step 3: Configure Permissions
1. Set appropriate read/write permissions
2. Consider restricting delete permissions for `Actual` type articles

### Step 4: Create Views
Recommended list views:
- **All Actual Articles** (Filter: Type = "Actual")
- **All Test Articles** (Filter: Type = "Testing")
- **Recent Articles** (Sort by: PublishDate DESC)
- **Articles with Hotels** (Filter: Hotels is not empty)

---

## DLRScanner Configuration

### Setting Article Type

**Option 1: Environment Variable (Recommended)**
```bash
# In .env file
ARTICLE_TYPE=Testing  # or "Actual" for production
```

**Option 2: Command Line**
```bash
# For testing
python src/dlr_scanner.py --type Testing

# For production
python src/dlr_scanner.py --type Actual
```

**Default Behavior:**
- If not specified, defaults to `Testing` for safety
- Prevents accidental pollution of production data

---

## JSON Output Format

Articles are exported to `data/articles_YYYYMMDD.json` with this structure:

```json
{
  "exported_at": "2026-01-30T12:38:27.802898",
  "total_articles": 51,
  "articles": [
    {
      "ArticleText": "Full article text here...",
      "Headline": "Article headline",
      "Hotels": [424166, 424979],
      "Companies": [37688214, 10455610],
      "Contacts": [8721789],
      "Source": "FW: Daily Lodging Report",
      "PublishDate": "2026-01-30T16:50:57+00:00",
      "Type": "Testing",
      "_metadata": {
        "article_number": 1,
        "source_from": "sender@example.com",
        "processed_at": "2026-01-30T12:00:33.611088",
        "original_hotels": [...],
        "original_companies": [...],
        "original_contacts": [...]
      }
    }
  ]
}
```

**Note:** The `_metadata` field is for internal tracking only and should not be uploaded to DealCloud.

---

## Data Upload Process

1. Run DLRScanner with desired type: `python src/dlr_scanner.py --type Actual`
2. Review the output JSON file: `data/articles_YYYYMMDD.json`
3. Use DealCloud's Import tool or API to upload the articles
4. Map JSON fields to DealCloud fields:
   - `ArticleText` → ArticleText field
   - `Headline` → Headline field
   - `Hotels` → Hotels multi-reference (array of Entry IDs)
   - `Companies` → Companies multi-reference
   - `Contacts` → Contacts multi-reference
   - `Source` → Source field
   - `PublishDate` → PublishDate field
   - `Type` → Type choice field

---

## Best Practices

1. **Always test first:** Run with `--type Testing` before production runs
2. **Review matches:** Check the CSV export to validate entity matching quality
3. **Clean test data:** Periodically delete articles with Type="Testing"
4. **Monitor match rates:** Track hotel/company/contact match percentages
5. **Backup data:** Export DealCloud data before large imports

---

## Questions?

For technical support or questions about this schema, refer to:
- `README.md` - General DLRScanner documentation
- `PROMPTS_DOCUMENTATION.md` - AI processing details
- Project source code in `src/` directory
