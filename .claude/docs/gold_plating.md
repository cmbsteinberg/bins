Gold plating for this bin website:

1. Thanks
We need to add thank you's to 
- https://github.com/mampfes/hacs_waste_collection_schedule
- https://github.com/robbrad/UKBinCollectionData

Underath where the bin returns are on the front page, add thanks to both of the above -0 with a ncely formattteed github button linkingt o the pages
Also add thanks in the footer of the page

**Implemented:** Credits with GitHub SVG icon links appear below results in `app.js` (`renderResults`). Site-wide footer in `index.html` and `about.html` links to both repos.

2. Add an about apage, but do not add to the central navbar. Add it at the bottom of the page in a footer

**Implemented:** `/about` route in `main.py`, template at `api/templates/about.html`. Linked from footer only, not navbar.

3. Default Bin colours

Add default colouring to the presentation of the bin return. Standard colours are black for general waste, blue / green for cycling, and brown for food waste. I think implement this subttely, with a background shade for each box

**Implemented:** `binColour()` function in `app.js` matches bin type keywords to colours. CSS in `index.html` applies subtle background shading via `data-bin-colour` attribute: grey for general/black bins, light blue for recycling, light green for garden, light brown for food/organic.

4. Create a sitemap automatically. Again, add this to the footer

**Implemented:** `/sitemap.xml` endpoint in `main.py` generates XML sitemap with all pages. Uses `BASE_URL` env var (defaults to `https://bins.lovesguinness.com`). Linked in footer.

5. Add some form of loggin that can be extracted from Hetzner. I don't know what this would look like. Maybe just in the redis db somehwre? 

**Implemented:** HTTP middleware in `main.py` logs every request (method, path, status, duration in ms) to the `api.requests` logger — visible in stdout/journalctl on Hetzner. Also increments per-path counters in Redis hash `api:request_counts` when Redis is available, queryable via `redis-cli HGETALL api:request_counts`.

6. Add button to say that the answer is wrong - which auto sends an email to EMAIL in .env that contains the entered postcode and address, with output, saying it's wrong.

**Implemented:** "Report wrong answer" button in results footer (`app.js`). Calls `POST /api/v1/report` with postcode, address, UPRN, council, and collections. Backend in `routes.py` sends email via SMTP to `EMAIL` env var. SMTP configured via `SMTP_HOST` (default `localhost`) and `SMTP_PORT` (default `25`) in `.env`.

7. Accessibility

Make the index page as accessible as possible — WCAG AA compliant, keyboard navigable, screen-reader friendly.

**Implemented:** Changes across `index.html` and `app.js`:

- **Colour contrast (WCAG AA):** Bumped all low-contrast text colours — footer `#999` to `#555` (7:1), links `#666` to `#444` (9.7:1), error/past red `#e53935` to `#c62828`, green accent `#4caf50` to `#2e7d32`.
- **Skip-to-content link:** Hidden link at top of page, visible on keyboard focus, jumps to `<main id="main-content">`.
- **Focus indicators:** `:focus-visible` outline (3px blue, 2px offset) on all interactive elements.
- **Focus management:** Focus moves to address `<select>` after postcode search, to results `<section>` after lookup, and back to postcode `<input>` on "Back".
- **Live regions:** `role="alert" aria-live="assertive"` on error `<p>` (immediate announcement), `aria-live="polite"` on results `<section>` (announced after interaction), `role="status" aria-live="polite"` on report feedback `<span>`.
- **Decorative SVGs hidden:** `aria-hidden="true" focusable="false"` on bin icon and GitHub icon SVGs.
- **Screen-reader text for external links:** `.sr-only` spans with "(opens GitHub in new tab)" on all `target="_blank"` links. `.sr-only` class uses standard clip-rect technique.
- **Landmark labelling:** `aria-label` on `<nav>` ("Main navigation"), `<footer>` ("Site footer"), and all `<section>` elements ("Postcode search", "Address selection", "Collection results").
- **Semantic grouping:** `role="group" aria-label="X collection"` on each bin card div.
- **Semantic dates:** `<time datetime="YYYY-MM-DD">` wrapping all rendered dates.
- **Autocomplete:** `autocomplete="postal-code"` on the postcode input.
- **External link safety:** `rel="noopener"` on all `target="_blank"` links.

8. Client-side address lookup (no server proxy)

Address lookups hit Mid Suffolk's Placecube API (`/api/jsonws/invoke`) directly from the user's browser, not proxied through our server. This distributes requests across user IPs and avoids our server getting rate-limited/banned.

**Investigated:** The `x-csrf-token` header previously hardcoded in `address_lookup.js` is unnecessary — Mid Suffolk's Liferay JSONWS API does not validate CSRF tokens for unauthenticated (no session cookie) requests. The API endpoint returns permissive CORS headers (mirrors requesting origin), so cross-origin browser requests work fine.

**Implemented:** Removed the stale hardcoded `x-csrf-token: Ba9vI91W` from `address_lookup.js`. Requests still go directly from user browsers with no token needed.
