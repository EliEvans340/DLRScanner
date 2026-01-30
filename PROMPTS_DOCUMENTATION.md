# DLRScanner - Gemini API Prompts Documentation

This document shows the exact prompts sent to Gemini AI for each processing step.

---

## 1. Newsletter Parsing (Step 2)

**Purpose**: Parse newsletter email into individual articles

**Model**: `gemini-2.5-flash` (configured in .env)

**Prompt Structure**:
```
[INSTRUCTIONS FROM config/newsletter_parser_instructions.txt]

Newsletter Email to Parse:
From: [email sender]
Subject: [email subject]
Date: [email date]

Newsletter Content:
[full email body - text or HTML]
```

**Full Prompt Example**:
```
You are analyzing a daily hotel industry newsletter email. Your task is to parse this newsletter and extract individual articles/news items from it.

INSTRUCTIONS:
1. Read the entire newsletter content carefully
2. Identify each distinct article, news item, or story in the newsletter
3. For each article, extract:
   - A sequential article number (starting from 1)
   - The complete article text (preserve the full content)
   - A headline/title for the article (use the actual headline if present, or create a concise summary headline)

GUIDELINES:
- Newsletters typically contain 5-15 separate articles/news items
- Each article should be a complete, self-contained news item
- Preserve all relevant details including names, numbers, locations, and dates
- Do not combine multiple articles into one
- Do not split a single article into multiple parts
- Skip newsletter headers, footers, subscription info, and advertisements
- Focus on substantive news content about hotels, hospitality, real estate, and related industries

OUTPUT FORMAT:
Return a JSON array of article objects. Each object should have:
- article_number: integer (1, 2, 3, etc.)
- headline: string (concise title for the article)
- article_text: string (complete article content)

Example output format:
[
  {
    "article_number": 1,
    "headline": "Marriott Acquires New Property in Miami",
    "article_text": "Full text of the article here..."
  },
  {
    "article_number": 2,
    "headline": "Hilton Reports Q3 Earnings",
    "article_text": "Full text of the second article..."
  }
]

Newsletter Email to Parse:
From: Eli Evans <eevans@awhpartners.com>
Subject: FW: Marriott, Hilton, and Hyatt Finish 2025 With Strong Growth
Date: Tue, 28 Jan 2026 20:11:39 +0000

Newsletter Content:
[Full newsletter text - could be 5,000-20,000 characters of newsletter content]
Daily Lodging Report for January 26, 2026. Alan R. Woinski, Editor.

The DJIA rose 314 points... [continues with full newsletter text]
```

**Expected Response**:
```json
[
  {
    "article_number": 1,
    "headline": "Marriott International Reports Strong Global Growth",
    "article_text": "Marriott grew net rooms by over 4.3% in 2025..."
  },
  {
    "article_number": 2,
    "headline": "Hilton Achieves Significant Growth in 2025",
    "article_text": "Hilton added nearly 800 hotels..."
  }
]
```

**Processing Time**: 3-15 seconds per newsletter (depends on length)

---

## 2. Entity Extraction (Step 3)

**Purpose**: Extract hotels, companies, and contacts from each article

**Model**: `gemini-2.5-flash` (configured in .env)

**Prompt Structure**:
```
[INSTRUCTIONS FROM config/entity_extractor_instructions.txt]

Article Headline: [article headline]

Article Text:
[article text content]
```

**Full Prompt Example**:
```
You are analyzing a hotel industry news article. Your task is to extract entities (hotels, companies, and contacts) mentioned in the article.

INSTRUCTIONS:
1. Read the article carefully
2. Extract all hotels mentioned with their details
3. Extract all companies mentioned with their roles
4. Extract all contacts/people mentioned with their titles and affiliations

ENTITY TYPES TO EXTRACT:

HOTELS:
- name: The hotel's name (required)
- city: City where the hotel is located (if mentioned)
- state: State/province/region (if mentioned)
- brand: Hotel brand or flag (e.g., Marriott, Hilton, Holiday Inn)

COMPANIES:
- name: Company name (required)
- role: The company's role in the context (e.g., "buyer", "seller", "broker", "developer", "owner", "operator", "lender", "investor")

CONTACTS:
- name: Person's full name (required)
- title: Job title (if mentioned)
- company: Company affiliation (if mentioned)

GUIDELINES:
- Only extract entities that are explicitly mentioned in the article
- For hotels, include the brand if mentioned separately (e.g., "The Marriott-flagged hotel" = brand: "Marriott")
- For companies, infer the role from context when possible
- For contacts, include their most relevant title and company mentioned in the article
- Do not make up or infer information that isn't in the text
- It's acceptable to return empty arrays if no entities of a type are found

OUTPUT FORMAT:
Return a JSON object with three arrays:
{
  "hotels": [
    {"name": "Hotel Name", "city": "City", "state": "State", "brand": "Brand"}
  ],
  "companies": [
    {"name": "Company Name", "role": "buyer"}
  ],
  "contacts": [
    {"name": "John Smith", "title": "CEO", "company": "ABC Corp"}
  ]
}

Article Headline: Marriott International Reports Strong Global Growth

Article Text:
Marriott International announced another year of outstanding global growth in 2025, marked by new brand offerings, strategic global scaling, and thoughtful collaboration with hotel owners. Marriott grew net rooms by over 4.3% in 2025, adding over 700 properties and nearly 100,000 rooms to the system. This included over 630 properties added through organic deals, representing more than 89,000 rooms...
```

**Expected Response**:
```json
{
  "hotels": [],
  "companies": [
    {
      "name": "Marriott International",
      "role": "operator"
    },
    {
      "name": "citizenM",
      "role": "brand partner"
    }
  ],
  "contacts": []
}
```

**Processing Time**: 2-10 seconds per article (depends on article length)

**Total Processing Time for 28 Articles**: ~2-5 minutes

---

## API Configuration

**Response Format**: JSON (enforced via `response_mime_type="application/json"`)

**Response Schema**: Typed schema validation using Pydantic TypedDict
- Newsletter Parser: `list[ArticleInfo]`
- Entity Extractor: `ArticleEntities`

**Model**: `gemini-2.5-flash` (default, configurable via `GEMINI_MODEL` in .env)

**Alternative Models**:
- `gemini-1.5-flash` - Faster but slightly less accurate
- `gemini-2.0-flash-exp` - Experimental, may be faster
- `gemini-1.5-pro` - More accurate but slower and more expensive

---

## Prompt Customization

Both prompts can be customized by editing:
1. `config/newsletter_parser_instructions.txt` - Newsletter parsing instructions
2. `config/entity_extractor_instructions.txt` - Entity extraction instructions

Changes to these files take effect immediately without code changes.

---

## Performance Optimization Options

**Current Performance**: ~8.5 minutes for 3 newsletters → 28 articles
- Newsletter parsing: ~5 minutes (2-3 newsletters)
- Entity extraction: ~3.5 minutes (28 articles)
- Validation: ~8 seconds

**Optimization Ideas**:
1. **Use faster model**: Switch to `gemini-1.5-flash` (saves ~30-40% time)
2. **Parallel processing**: Process multiple articles simultaneously (saves ~50% time)
3. **Batch API calls**: Combine multiple articles in one prompt (complex, may reduce accuracy)
4. **Cache parsed newsletters**: Skip re-parsing seen emails (saves 100% on duplicates)

---

## Cost Estimation

**Gemini Flash Pricing** (as of 2026):
- Input: $0.075 per 1M tokens
- Output: $0.30 per 1M tokens

**Typical Usage per Newsletter**:
- Newsletter parsing: ~10K tokens input + 2K tokens output = ~$0.001
- Entity extraction (28 articles): ~50K tokens input + 5K tokens output = ~$0.005
- **Total per newsletter scan: ~$0.006** (less than 1 cent)
