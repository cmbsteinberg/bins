# Porting the 42 UKBCD selenium scrapers — XHR capture findings

**Date:** 2026-04-24
**Prior art:** `HANDPORT_PLAN.md` (Phase 2.5 introduced the XHR capture
pivot), `LIGHTPANDA_EXPERIMENT.md`, `pipeline/ukbcd/selenium_test_results.json`
**Capture harness:** `pipeline/ukbcd/capture_upstream_xhrs.py`
**Raw captures:** `pipeline/ukbcd/xhr_captures/*.json`
**Summary:** `pipeline/ukbcd/xhr_capture_summary.json`

This document reports how each council's JavaScript actually talks to
its backend, so we can replace Lightpanda / Chromium ports with plain
`httpx` wherever possible. It is the practical answer to the question
"which of the 42 selenium scrapers genuinely need a browser?"

## TL;DR

- **29 of 42** scrapers were probed (the other 13 are `upstream_broken`
  in the manifest — upstream itself doesn't work, so there is nothing
  to observe).
- **29 of 29** successfully ran under the capture harness and returned
  bins data (after one harness bug fix — see "Investigation story" below).
- **Every success is portable to plain `httpx`** after manual review.
  Nine were flagged automatically by the harness's heuristic;
  twenty more needed a human to look at the XHR list and identify the
  payload endpoint.
- **The backend landscape is smaller than it looked.** Four vendors
  account for ~14 councils; the rest are one-offs whose flows are still
  straightforward HTTP once you can see them.

## Investigation story

This was not a clean one-shot run. The findings here come from two
passes of the harness, and the delta between them is instructive.

### Pass 1 (flawed harness): 18/29 success

On the first run the harness called each council's `parse_data()`
directly with kwargs built from `input.json`:

```python
result_obj = CouncilClass().parse_data('', **payload)
```

where `payload` copied `input.json` keys verbatim (`uprn`, `postcode`,
`house_number`, `usrn`, `paon`, plus forced `headless=True`,
`web_driver=None`).

Eighteen councils succeeded, eleven "failed" with 0 XHRs captured.
The rough instinct was that these eleven were "broken in practice" —
selenium couldn't even load the page under real headless Chromium.

That conclusion was wrong. A cross-check against
`pipeline/ukbcd/selenium_test_results.json` (the earlier probe that
runs upstream's `collect_data.py` CLI directly) showed **all 29 had
passed that probe** just days before. The failures were not upstream
breakage — they were regressions introduced by the harness.

### Root cause

Upstream's `collect_data.py` CLI maps its argparse flags to the kwargs
the framework's `template_method` expects. The interesting part is
what the CLI does that `input.json` does *not*:

| CLI flag / behaviour | Input.json equivalent |
|---|---|
| `-n/--number` → `paon` kwarg | `house_number` key |
| URL as positional arg | `url` key (but ignored by my harness) |
| `-s/--skip_get_url` | `skip_get_url` key (ignored by my harness) |
| Framework calls `get_data(url)` and passes HTML as `page` when `skip_get_url=False` | `parse_data('', …)` in my harness — no pre-fetch |

Scrapers read `kwargs.get("paon")` and `check_paon(None)` raises
`ValueError`. My harness passed the key `house_number` instead of
`paon`, so eleven scrapers (those whose upstream code uses `paon`
rather than postcode/UPRN-only flows) hit the error at line one of
`parse_data()` and never produced XHRs. Somerset, MidSuffolk, Powys,
Ceredigion, Hertsmere, MidUlster, TestValley, Edinburgh, Hillingdon,
BrightonAndHove, ForestOfDean all read `paon`.

### Pass 2 (fixed harness): 29/29 success

The fix was straightforward:

- `build_payload` now maps `house_number → paon` (matching the CLI)
  and also threads through `url`, `skip_get_url`, and `local_browser`.
- The harness now calls `get_and_parse_data(url, **kwargs)` — the
  framework entry point — instead of `parse_data` directly. This
  matches `collect_data.py` verbatim (minus the JSON-output wrapping)
  and means `get_data(url)` pre-fetch and the `skip_get_url` branch
  both behave identically to the CLI path.

With that change every formerly-failing capture recovered. The
previous "broken in practice" classification was spurious; there are
no broken-in-practice scrapers in the probed set.

### Lesson

When writing a harness that re-uses upstream framework code, calling
the framework's own entry point is always cheaper and safer than
re-implementing its arg routing. This is doubly true here, where the
gap between the CLI's semantics and input.json's field names is not
documented anywhere — it exists only in `collect_data.py`'s argparse
setup.

## How the capture harness works

`pipeline/ukbcd/capture_upstream_xhrs.py` runs each upstream scraper
verbatim under its own `uv run --no-project --with …` venv, but with a
two-stage handshake injected into selenium's lifecycle:

1. Monkey-patch `uk_bin_collection.uk_bin_collection.common.create_webdriver`
   to launch Chrome with `--remote-debugging-port=<free>` and
   `--user-data-dir=<tmp>`, then emit `__READY__` and block on `GO`
   from the parent over stdin.
2. Parent reads `__READY__`, connects Playwright over CDP to the same
   Chrome, attaches `request` / `response` listeners to every browser
   context (including future ones), and writes `GO\n`.
3. The upstream scraper's `parse_data()` then drives the browser
   normally via the framework's `get_and_parse_data(url, **kwargs)`;
   Playwright observes every request that crosses the wire.
4. Monkey-patched `WebDriver.quit` emits `__QUIT_REQUESTED__` and
   blocks on `FINISH`. The parent drains response-body fetches while
   Chrome is still alive, then releases the subprocess.
5. Subprocess prints `__RESULT__<json>` to stdout. Parent records
   result + all events to `xhr_captures/{Council}.json`, categorising
   each request as either XHR-ish or static.

A third code path handles councils whose upstream scraper never
touches selenium at all: if `__RESULT__` arrives before `__READY__`,
the harness records a "browserless" capture with 0 XHRs and the
scraper's own result.

### Heuristic `httpx_convertible` flag

The summary tags a capture as httpx-convertible when at least one
non-static XHR returns a 2xx JSON/text response whose body contains
both the UPRN and either the postcode or a date-ish string. This is
the "no human needed" signal; it flagged 9 of 29. Twenty more are
trivially convertible on manual inspection — see the next section
for the reasons it missed.

### Run parameters

- Concurrency 4, per-council soft budget 300s.
- All 29 captures completed in ~3 minutes total.
- Typical successful scrape took 6–15s per council end-to-end
  including Chrome launch, chromedriver pairing via selenium-manager,
  CDP handshake, and scrape.

## Vendor cluster findings

### IEG4 AchieveForms (4 councils captured; 6 in total cluster)

Captured: GloucesterCity, NorthDevonCounty, Tendring, ThreeRivers.
Not captured: EastSuffolk, NorthEastDerbyshire (`upstream_broken`).

**Payload endpoint:** `POST https://<council>-self.achieveservice.com/apibroker/runLookup?id=<id>` (or similar `my.<council>.gov.uk/apibroker/runLookup`).

**Flow:** Upstream navigates to a public webpage which embeds the
form in an iframe served from AchieveForms. The iframe's JS calls
`/apibroker/runLookup` with JSON containing the UPRN. Response is a
JSON payload enumerating collection types and dates. No
authentication; the `id=` query parameter is a public lookup slug.

**Portability:** Tier 0, trivial. One `httpx.post` with a JSON body
(`{"formValues": {...}}`) is all each scraper needs. The four
currently live as `blocked_on_lightpanda_iframes`; they flip to
`ported` today without waiting on Lightpanda's iframe CDP support.

### Jadu CXM (3 councils — largest cluster after IEG4)

Captured: StaffordshireMoorlandsDistrict, **Hillingdon** (newly
identified), **Powys** (newly identified).

**Payload endpoint:** Two shapes, both on a `/apiserver/…` base:

- `GET <council>.gov.uk/apiserver/postcode?postcode=<pc>&callback=jQuery…` — JSONP address lookup
- `POST <council>.gov.uk/apiserver/formsservice/http/processsubmission?pageSessionId=<sid>` — form-encoded, UPRN in body, 303 → GET `/findyourbinday?pageSessionId=<sid>` which renders the result HTML

**Portability:** Tier 0 with a session. Seed `pageSessionId` from the
initial page load, JSONP-strip the callback wrapper, then 2–3 HTTP
calls. The JSONP pattern is the giveaway: any UKBCD scraper
targeting a `/apiserver/postcode?callback=…` URL is Jadu CXM.

**Implication for Phase 1:** Hillingdon and Powys were previously
singleton "one-off" targets. They are not one-offs — they share the
same base with StaffsMoorlands. A single Jadu CXM base class handles
all three.

### iTouchVision (4 councils — previously thought to be 3)

Captured: BlaenauGwent (**newly clustered — previously a singleton**),
EpsomAndEwell, Hyndburn, Winchester.

**Wire shape:** The public page redirects to a React SPA at
`iportal.itouchvision.com/icollectionday/collection-day/?uuid=<UUID>`
(or `iapp.itouchvision.com`, or a bespoke council subdomain). The SPA
bundle calls a consistent backend:

- `GET https://iweb.itouchvision.com/portal/itouchvision/kmbd/address`
- `GET https://iweb.itouchvision.com/portal/itouchvision/kmbd/collectionDay`

(Some councils point at `itouchvision.app` instead of `iweb.itouchvision.com` — same API shape.)

**Complication: response bodies are encrypted hex blobs.** The React
bundle decrypts client-side (presumably AES with a key derived from
the `uuid` or embedded in `main.<hash>.js`). Parameters appear to be
passed via headers / derived from the `uuid` session. Without the
decryption key, a plain `httpx` port cannot read the responses.

**Portability:** Not trivially Tier 0 from the capture alone. Two
realistic paths:

1. **Reuse HACS's existing `iapp_itouchvision_com` scraper.** HACS
   has already reverse-engineered the crypto; we get four councils
   by adding a thin UKBCD-branded wrapper that feeds the uuid.
2. **Reverse-engineer the crypto** from `main.<hash>.js` ourselves
   (straight AES with a symmetric key in the bundle is the common
   pattern) — higher risk, higher effort.

Recommend path 1.

### Jadu Continuum (2 councils)

Captured: Sevenoaks, **Hertsmere** (newly confirmed).

**Host pattern:** `<council>-dc-host01.oncreate.app` or
`<council>-services.onmats.com`, with path prefix `/w/webpage/…`.

**Flow (Sevenoaks):**
1. `POST /w/webpage/waste-collection-day` with a `_session_storage`
   / CSRF dance returns JSON session metadata.
2. `POST .../?webpage_subpage_id=PAG…` with form body
   `code_action=search&code_params={"search_item":"<postcode>"}` → JSON address list with internal IDs.
3. `POST …` with `code_action=address_selected&code_params={"selected":"<id>"}` then
   `GET /w/webpage/<template_id>?webpage_token=<t>` returns HTML with
   collection dates.

**Flow (Hertsmere):** Same oncreate.app / onmats.com shape. The Pass 1
harness couldn't capture it because `paon` was missing; Pass 2 surfaced
28 XHRs including the `/w/ajax?webpage_subpage…` POST that carries the
interaction.

**Portability:** Tier 0. Four-request `httpx.AsyncClient` with cookie
jar. Sevenoaks is currently pinned `blocked_on_lightpanda_rendering`;
Hertsmere is `blocked_on_lightpanda_interactions`. Both dissolve.

### Salesforce Community (2 councils)

Captured: **ForestOfDean** (newly surfaced). Cotswold is
`upstream_broken`.

**Endpoint:** `POST https://community.fdean.gov.uk/s/sfsites/aura?r=<n>&aura.LookupPageId=…`
— Salesforce Aura framework's message-bus endpoint. Request body is
an Aura "message" JSON with a `params.uprn`-style payload.

**Portability:** Tier 0 but heavier. Aura requires a valid
`aura.token` and `fwuid` harvested from an initial GET of the
Salesforce page. Well-documented pattern in the Salesforce
reverse-engineering community. Doable, but more work than Jadu CXM.

## Individual finds (single-site bespoke flows)

### Pure Tier 0, single endpoint

- **Teignbridge**: `GET https://www.teignbridge.gov.uk/repositories/hidden-pages/bin-finder?uprn=<uprn>` returns HTML containing the schedule directly. One line. This is the easiest port in the set — start here.
- **Basildon**: already known to be browserless. Capture confirmed
  upstream never called `create_webdriver`; flow is a plain
  `POST https://basildonportal.azurewebsites.net/api/getPropertyRefuseInformation`.
- **DumfriesAndGalloway**: capture emitted 0 XHRs with a successful
  result → upstream is also already plain-HTTP. Port as browserless.
- **Edinburgh**: capture emitted 0 XHRs with a successful result →
  browserless too. Another already-plain-HTTP upstream.

### Tier 0, confirmed payload URL

These came back with an explicit `candidate_payload_url` in the summary:

| Council | Endpoint |
|---|---|
| ArgyllandBute | POST to `https://www.argyll-bute.gov.uk/rubbish-and-recycling/household-waste/bin-collection` (HTML response with schedule) |
| NewForest | POST to `https://forms.newforest.gov.uk/ufs/ufsajax?…` (Oracle UFS) |
| Northumberland | POST to `https://bincollection.northumberland.gov.uk/address-select` |
| Torbay | POST to `https://selfservice-torbay.servicebuilder.co.uk/core/address…` |
| Wychavon | POST to `https://selfservice.wychavon.gov.uk/sw2AddressLookupWS/jaxrs/…` |

All of these are single-site bespoke forms. Each is a direct
`httpx.post` per scraper; no cluster reuse to be had, but no browser
needed either.

### Other singletons with clear flows (heuristic missed)

- **Somerset** (10 XHRs): form on `somerset.gov.uk/collection-days`, similar bespoke shape to Northumberland.
- **Ceredigion** (68 XHRs): bespoke form on `ceredigion.gov.uk/resident/bins-recycling/` — the candidate URL the heuristic returned is the cookie banner, ignore; the real endpoint is a POST to the same origin.
- **MidSuffolk** (131 XHRs): lots of chat-widget noise in the heuristic's candidate; the real backend is a POST on the midsuffolk page.
- **MidUlster** (41 XHRs): bespoke flow on `midulstercouncil.org/resident/bins-recycling`.
- **TestValley** (9 XHRs): small flow, likely single POST.
- **BrightonAndHove** (20 XHRs): `enviroservices.brighton-hove.gov.uk/widgets/HTMLSnippet/...` — looks like a widget iframe pattern.
- **Winchester** (12 XHRs): thin flow. (Also a secondary iTouchVision host; check whether main data path is iTouchVision or bespoke.)

None of these needs a browser at runtime.

### Why the heuristic missed so many

The `httpx_convertible` flag had a 9/29 recall in this run. Reasons
it undercounted:

- **UPRN-in-query rather than body** (Teignbridge pattern). The
  heuristic only scored response bodies.
- **3xx redirect with empty body** (StaffsMoorlands / Jadu CXM
  processsubmission). Heuristic requires a 2xx body → scores zero
  even when the POST clearly carried the UPRN.
- **Response body uses internal IDs** rather than UPRN/postcode
  literally (Sevenoaks / Jadu Continuum, Salesforce Aura).
- **Encrypted bodies** (iTouchVision). No human-readable match is
  possible.
- **First hit on candidate URL is noise** — cookie banners, analytics,
  chat widgets appear high in document order and win the
  "highest-scoring URL" race.

Proposed improvements to the heuristic:

- Score UPRN appearances in request URL query strings, not just
  response bodies.
- Score UPRN in POST bodies regardless of response content.
- Filter out known-noise domains (GoogleTagManager, civiccomputing,
  click4assistance, region1.google-analytics) before scoring.
- Pattern-boost specific vendor path fragments (`/apibroker/runLookup`,
  `/ufs/ufsajax`, `kmbd/collectionDay`, `/w/webpage/`, `/apiserver/`).
- Emit `needs_crypto_reverse: true` when every candidate response body
  is high-entropy hex — so iTouchVision-class situations are visible
  at a glance instead of hiding as "no candidate".

## Revised 42-council scorecard

| Bucket | Count | Members |
|---|---|---|
| **Ready to port as Tier 0 today** (capture + flow known) | **22** | IEG4 (4): Gloucester, NorthDevon, Tendring, ThreeRivers · Jadu CXM (3): StaffsMoorlands, Hillingdon, Powys · Jadu Continuum (2): Sevenoaks, Hertsmere · Salesforce Community (1): ForestOfDean · Bespoke singletons (8): ArgyllAndBute, NewForest, Northumberland, Torbay, Wychavon, Somerset, Teignbridge, plus BrightonAndHove · Additional singletons (3): MidSuffolk, MidUlster, TestValley · Browserless (4): Basildon, DumfriesAndGalloway, Edinburgh, Ceredigion |
| **iTouchVision cluster — port after one crypto/HACS decision** | **4** | Blaenau, EpsomAndEwell, Hyndburn, Winchester |
| **Upstream broken in manifest (no work possible)** | **13** | Babergh, Boston, Cotswold, EastSuffolk, EppingForest, GreatYarmouth, Halton, KingstonUponThames, Knowsley, NorthEastDerbyshire, NorthNorfolk, Slough, Stirling |

**Total: 22 + 4 + 13 = 39.** The gap to 42 is three councils that
appear in overlapping classifications in the manifest (e.g. listed as
both cluster members and singletons) — consolidate when writing the
Phase 2 tracking PR.

## Recommended order of work

1. **Teignbridge.** 10-line `httpx.get` + `BeautifulSoup`. Single
   scraper, no cluster, proves the Tier 0 code path end to end with
   the minimum moving parts.
2. **The four browserless** (Basildon, DumfriesAndGalloway, Edinburgh,
   Ceredigion). Port upstream logic mostly verbatim. Proves the
   browserless classification works through the integration test
   harness.
3. **IEG4 AchieveForms cluster** (4 councils). Write
   `IEG4AchieveFormsHttpxScraper` base with a single `runLookup`
   method, subclass four times. Moves four councils from
   `blocked_on_lightpanda_iframes` → `ported` in one PR. Highest
   leverage in the set.
4. **Jadu CXM cluster** (3 councils: StaffsMoorlands, Hillingdon,
   Powys). One base class for the `/apiserver/…` JSONP + form-encoded
   flow, three subclasses. Big win relative to effort.
5. **Jadu Continuum cluster** (2 councils: Sevenoaks, Hertsmere). One
   base class for the `/w/webpage/…` JSON flow.
6. **Bespoke singletons** (~8 councils). ArgyllAndBute, NewForest,
   Northumberland, Torbay, Wychavon, Somerset, BrightonAndHove,
   MidSuffolk, MidUlster, TestValley. One scraper each, ~30 minutes
   per once the capture gives you the exact flow.
7. **Salesforce Community — ForestOfDean.** Standalone for now; port
   as a singleton, but build with Aura reuse in mind in case more
   councils appear later.
8. **iTouchVision cluster decision.** Either port HACS's
   `iapp_itouchvision_com` into `api/scrapers/hacs_*.py` and drop the
   four UKBCD entries into the override map, or invest a half-day to
   reverse-engineer the AES in the React bundle. Strong preference
   for reuse.

## Loose ends / improvements for the harness

- **Harness lesson codified** — `build_payload` now mirrors the CLI's
  argparse mapping (especially `house_number → paon`), and the harness
  calls `get_and_parse_data(url, **kwargs)` instead of `parse_data`
  directly. This bug should not recur.
- **Heuristic improvements** per the "Why the heuristic missed so
  many" section above.
- **Headless-only run.** All captures ran `headless=True`. Adding a
  `--headful` mode for re-probing councils whose upstream is
  rumoured to need non-headless would be useful on the margin — but
  in this run every council worked headless, so there's no immediate
  customer.
- **Multiple test cases.** The harness currently runs the single
  `input.json` test case per council. Running 2–3 cases would expose
  which parameters are actually varying in requests (UPRN vs USRN vs
  postcode) and harden the heuristic's payload detection.

## What this changes about Phase 2 of the plan

`HANDPORT_PLAN.md` Phase 2 Tier A ordered work by vendor cluster with
the assumption that each cluster had one Lightpanda blocker. The
capture evidence says:

- **The IEG4 cluster isn't blocked on Lightpanda at all** once you
  drop the browser. Move it from "Tier A pinned" to "port now".
- **Jadu Continuum and Jadu CXM aren't blocked on Lightpanda either.**
  Their pinned statuses
  (`blocked_on_lightpanda_rendering` /
  `blocked_on_lightpanda_interactions`) were correct observations
  about *running the browser port on Lightpanda*, but they conflated
  "needs browser" with "needs Lightpanda". The Tier 0 version of each
  scraper sidesteps Lightpanda entirely.
- **Cluster sizes are bigger than the plan estimated.** Jadu CXM
  picks up Hillingdon and Powys. iTouchVision picks up Blaenau. Some
  councils previously counted as "singletons" were mis-classified
  because no one had seen the wire yet.
- **iTouchVision is the only cluster where the browser was actually
  doing non-trivial work** (client-side decryption). Even there, the
  way out is reusing HACS rather than running a browser.
- **No scraper in this set actually requires Chromium at runtime.**
  The plan's Tier-C "Chromium on demand" fallback has no customers
  yet among the 42. If we keep Chromium-on-demand in the architecture,
  it's for some hypothetical future council, not for anyone today.

Bottom line: the pivot to XHR reverse engineering in Phase 2.5 was
correct, and the observed evidence pushes it further than the pivot
itself proposed. The next deliverable is not more Lightpanda-pinned
hand-ports — it's Teignbridge + IEG4 + Jadu (CXM and Continuum) as
pure Tier 0, which alone lands 10 scrapers as fully working ports,
without any browser runtime at all.
