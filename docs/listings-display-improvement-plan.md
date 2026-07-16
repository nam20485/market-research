# Improve Generated Listings Display

## Goal
Refactor the generated marketplace postings output to match the richness of `templates/listings-template.md`, improve visual appeal and copy-paste ergonomics, and separate Facebook Marketplace and OfferUp into distinct full-width sections.

## Context

**Current state:**
- Backend returns minimal `{title, description}` per marketplace (`MarketplaceListing` schema)
- Frontend renders two side-by-side cards in a grid with a single "Copy to clipboard" button (title + description)
- Listing prompt (`app/prompts/listing.py`) asks LLM for only title/description

**Template requirements (from `templates/listings-template.md`):**
- Suggested Title, Price, Category, Condition
- Full Description (copy-paste block)
- Key Features (bullet list)
- Search Tags (copy-paste block)
- Payment/Delivery terms

## Plan

### 1. Backend: Expand Listing Schema

**File:** `app/schemas/listing.py`

Add optional fields to `MarketplaceListing`:
```python
class MarketplaceListing(BaseModel):
    title: str = ""
    price: str = ""          # suggested price (string, e.g. "$195")
    category: str = ""       # marketplace category (e.g. "Electronics > Computer Parts")
    condition: str = ""      # condition (e.g. "New", "Like New")
    description: str = ""
    features: list[str] = [] # key features as bullet points
    tags: list[str] = []     # search tags
    terms: str = ""          # payment/delivery terms block
```

### 2. Backend: Update Listing Prompt

**File:** `app/prompts/listing.py`

Revise `LISTING_INSTRUCTIONS` to request richer structured output. Shape:
```json
{
  "facebook_marketplace": {
    "title": "...",
    "price": "$195",
    "category": "Electronics > Computer Parts",
    "condition": "New",
    "description": "Brand new & sealed...",
    "features": ["1TB capacity", "PCIe Gen 4.0", "7,450 MB/s read"],
    "tags": ["Samsung 990 Pro", "NVMe SSD", "PS5 upgrade"],
    "terms": "CASH ONLY. Local pickup in [Your City]."
  },
  "offerup": { ... }
}
```

Add guidance: FB copy is conversational with emoji/enthusiasm; OfferUp is concise and keyword-forward.

### 3. Backend: Pass Through New Fields

**File:** `app/services/listing.py`

Update `ListingService.generate()` to include new fields when constructing `MarketplaceListing` instances:
```python
return ListingResponse(
    facebook_marketplace=MarketplaceListing(
        **parsed.get("facebook_marketplace", {})
    ),
    offerup=MarketplaceListing(**parsed.get("offerup", {})),
)
```

### 4. Frontend: Redesign ListingCard Component

**File:** `frontend/src/components/ListingStep.jsx`

Replace `ListingCard` with an expanded `MarketplaceCard` that:
- Shows title, price, category, condition as header elements
- Renders description in a copy-paste-friendly pre-formatted block
- Displays features as a bullet list
- Shows tags as a chip/badge row with a separate "Copy tags" button
- Includes payment terms in a distinct section
- Adds marketplace-specific visual styling (FB = blue accent border, OfferUp = orange accent border)
- Provides per-field copy buttons: "Copy title", "Copy description", "Copy tags", "Copy all"

### 5. Frontend: Separate FB and OfferUp Sections

**File:** `frontend/src/components/ListingStep.jsx`

Change from side-by-side grid to stacked full-width cards:
```jsx
<div className="flex flex-col gap-6">
  {listing.facebook_marketplace && <MarketplaceCard marketplace="Facebook Marketplace" ... />}
  {listing.offerup && <MarketplaceCard marketplace="OfferUp" ... />}
</div>
```

### 6. Frontend: Update API Types

**File:** `frontend/src/api.js`

Update `generateListing` JSDoc `@returns` to reflect expanded schema:
```javascript
/**
 * @returns {Promise<{
 *   facebook_marketplace: { title: string, description: string, price: string, category: string, condition: string, features: string[], tags: string[], terms: string },
 *   offerup: { title: string, description: string, price: string, category: string, condition: string, features: string[], tags: string[], terms: string },
 * }>}
 */
```

### 7. Update Frontend Tests

**File:** `frontend/src/components/ListingStep.test.jsx`

- Update mock `generateListing` return values to include new fields
- Update assertions to match new rendered elements (price, category, features, tags)
- Test per-field copy buttons (title, description, tags, all)

### 8. Update Backend Tests

**File:** `tests/test_listing.py` (or equivalent)

- Update any existing listing-generation tests expecting only `{title, description}`
- Add test coverage for new fields

### 9. Verify Research Stage (Optional)

**File:** `app/services/research.py` and `app/prompts/research.py`

Review whether the research prompt returns structured data (price range, condition, features) that feeds into listing generation. If the research summary is unstructured text, consider:
- Ensuring condition and key features are captured in the research report
- Passing these explicitly into the listing prompt rather than relying on the LLM to infer

### 10. Run Validation

```bash
pwsh -NoProfile -File ./scripts/validate.ps1 -All
```

This runs lint, typecheck, tests, and frontend build to confirm all changes are consistent.

## Risks & Edge Cases

- **LLM output variability:** The LLM may occasionally omit fields. The expanded schema uses defaults (`""`, `[]`) so missing fields don't break rendering.
- **Backward compatibility:** Existing listing generations in flight may return old-schema responses. Frontend should gracefully handle missing fields (show nothing, not error).
- **Copy buffer overflow:** Copying all fields at once produces a large text block. Consider a "smart copy" that formats for actual marketplace input fields.

## Validation Plan

1. Generate a listing for a test item; verify response includes title, price, category, condition, description, features, tags, terms for both marketplaces.
2. Render the listing in the UI; verify FB and OfferUp are stacked, visually distinct, and all fields are present.
3. Test copy buttons: title, description, tags, and "copy all" should populate clipboard with correctly formatted content.
4. Run `validate.ps1 -All` and confirm green.
