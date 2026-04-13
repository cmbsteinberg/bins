# Frontend Results Redesign

## Summary

Redesigned the bin collection results display and overall frontend layout across multiple iterations. Key changes: new footer, coverage page (iframe removed, map embedded directly), bin card redesign with colour coding, single combined accordion, past-date filtering, environment-aware static file caching, address formatting, security header fix, GOV.UK typography standards, and CSS refactored out of HTML into external files.

## Changes

### CSS refactor — inline styles extracted to external files

All inline `<style>` blocks have been moved to external CSS files in `api/static/`:

- **`shared.css`** — nav and footer styles (previously in `partials/shared-styles.html` as a `<style>` tag, now a `<link>` to the CSS file)
- **`style.css`** — all index.html page styles (variables, layout, bin cards, accordion, buttons, accessibility)
- **`coverage.css`** — Leaflet map and legend styles for the coverage page

The `partials/shared-styles.html` partial now just contains a `<link>` tag instead of inline styles.

### Footer (`api/templates/partials/footer.html`)

- Changed "Built on data from ... &" to "Powered by" with the two GitHub repo links on a separate line
- GitHub links use `.gh-link` class for pill/badge styling (border, rounded corners, padding)
- About and Sitemap links remain plain text

### Coverage page (`api/templates/coverage.html`)

- Removed title ("Coverage Map") and description text
- **Removed iframe** — Leaflet map is now embedded directly in the template. The iframe approach was blocked by `X-Frame-Options` even with `SAMEORIGIN`
- Leaflet CSS/JS loaded in the template, map JS inline, legend in bottom-right corner
- Map height is `70vh` with `border-radius: 8px`

### Security headers (`api/main.py`)

- Changed `X-Frame-Options` from `DENY` to `SAMEORIGIN` — `DENY` was blocking same-origin content

### Static file caching (`api/main.py`)

- Added `Cache-Control: no-cache` header for `/static/` paths, **only when `ENV` is not `production`**
- In dev (default): forces browser revalidation via ETag on every request, preventing stale JS/CSS
- In production (`ENV=production`): no header is set, so normal browser caching applies

### Environment config (`.env`, `.env.example`)

- Added `ENV` variable to both files
- `.env` (deployed config): `ENV=production` — static files are cached normally
- `.env.example` (new setup default): `ENV=development` — static files revalidate on every request

### Address formatting (`api/static/address_lookup.js`)

- Added `titleCase(str)` — lowercases then capitalises first letter of each word
- Added `formatAddress(item)` — takes structured API fields (`addressLine1` through `addressLine4` + `city`), title-cases each, appends postcode as-is, joins with commas
- Result: "Albemarle House, The Green, Old Buckenham, Attleborough, NR17 1SW" instead of all-caps

### Typography — GOV.UK standards (`api/static/style.css`)

Font sizes follow GOV.UK Design System guidelines (19px body minimum, 16px small text minimum):

- **Body**: `1.2rem` (19.2px) — matches GOV.UK's 19px standard
- **Bin type** (heading-like): `1.3rem` (~21px)
- **Bin date, form inputs, buttons, accordion summary/items**: `1.2rem` (19px)
- **Relative day, council name, report-sent**: `1rem` (16px) — GOV.UK's minimum for small text
- **Nothing in main content below `1rem`** (16px)
- Footer excluded (remains at `0.8rem` as it's supplementary)

### `api/static/style.css` (extracted from `index.html`)

- **Back button**: `.btn-secondary` gets `border: 1px solid var(--border)` for a visible bounded box
- **Bin colours**: Three CSS custom properties — `--colour-grey: #a0a0a0` (dark enough for "black bin"), `--colour-brown: #a67c52` (earthy brown), `--colour-green: #93c47d`. Cards use `opacity: 0.85`
- **No `<article>` wrapper**: `#results mark, #results article { all: unset }` prevents water.css interference
- **Bin card layout**: `.bin-info` is `display: flex` with `align-items: baseline` — type, date, and relative day on one line
- **Consistent text colour**: `.bin-relative` and `.report-sent` both use `#444`
- **Action buttons**: Single `.action-btn` class with `all: unset` to strip browser defaults, ensuring `<a>` and `<button>` render identically. `.action-btn.outline` variant for the report button. Centered at bottom of results
- **Accordion**: `.all-dates` — single `<details>` at bottom with all future dates across all types, sorted by date

### `api/static/app.js`

- **`binColour(type)`** — Two-tier matching: explicit colour word first, then waste category inference. Maps to three categories: brown, green, grey
- **`isToday(dateStr)`** — Filters past dates from display
- **`renderResults()`** — Groups by type, one card per type, single combined accordion, no `<article>`, buttons at bottom
- **Removed `GH_SVG`** — credits moved to shared footer

## Design Decisions

- **Three colours only**: Grey (refuse/general/default), brown (food/garden), green (recycling). Colour-word matching takes priority over category inference
- **Single combined accordion**: Per-type accordions were cluttered. One "All upcoming dates" accordion sorted by date
- **Past date filtering**: No point showing past dates. ICS feed still contains them
- **`all: unset` on action buttons**: Only reliable way to align `<a>` and `<button>` identically
- **No iframe for coverage**: `X-Frame-Options` made iframes unreliable. Direct embedding is simpler
- **Environment-gated caching**: `no-cache` only in non-production — forces revalidation via ETag in dev
- **CSS in external files**: Inline styles made templates hard to read and prevented browser caching of CSS. External files are cacheable, easier to maintain, and keep templates focused on structure
- **Address formatting at lookup stage**: Applied in `address_lookup.js` so both dropdown and results benefit
