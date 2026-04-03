# Frontend Results Redesign

## Summary

Redesigned the bin collection results display on the landing page to show grouped, scannable results with an accordion for future dates and a wheelie bin icon.

## Changes

### `api/templates/index.html`

Replaced the flat collection list styles with a card-based layout:

- **`.bin-group`** — Bordered card per bin type with rounded corners
- **`.bin-next`** — Flex row: icon + type name + date + relative label
- **`.bin-relative`** — Green "Tomorrow" / "In 3 days" badge; red if the date is in the past
- **`.bin-more`** — Pure CSS accordion using `<details>`/`<summary>` for future dates. Custom triangle markers via `::before` pseudo-element, webkit marker hidden

### `api/static/app.js`

Rewrote `renderResults()` and added helpers:

- **`BIN_SVG`** — Inline SVG wheelie bin icon (grey, neutral colour). Simple rects: body, ridges, lid, handle, wheels. Avoids colour confusion since bin colours vary across councils.
- **`formatDate(dateStr)`** — Extracted date formatting (was inline). Appends `T00:00:00` to avoid timezone-shift issues with `new Date()`.
- **`relativeDay(dateStr)`** — Returns `{ text, past }` for labels like "Today", "Tomorrow", "In N days", or "N days ago".
- **`renderResults()`** — Groups collections into a `Map` keyed by `c.type`. For each group:
  - Shows the first (next) date prominently with the bin icon and relative label
  - Wraps remaining dates in a `<details>` accordion ("N more dates")
  - No JavaScript needed for the expand/collapse — it's native HTML disclosure

## Design Decisions

- **No JS for accordion**: `<details>`/`<summary>` is supported in all modern browsers and keeps the page dependency-free.
- **Neutral grey bin icon**: Councils use wildly different bin colours (green for general waste in one council, green for recycling in another). A neutral grey avoids misleading users. The icon is purely decorative to add visual weight to each card.
- **Grouped by type**: Previously all collections were listed flat in date order, making it hard to scan which bins are due when. Grouping by type with "next date" prominent matches how people actually think about bins — "when is my recycling next?"
- **Relative date labels**: "Tomorrow" or "In 3 days" is immediately useful without mental date arithmetic.
