# UK Council Bin Collection Scraper

A sophisticated browser automation system for discovering and capturing bin collection APIs from UK council websites.

## Overview

This scraper uses Playwright to automatically explore UK council bin collection lookup flows. It navigates council websites, fills forms, clicks buttons, and records network traffic to help reverse-engineer the underlying APIs.

## Architecture

The system follows a modular, stateless design with clear separation of concerns:

```
Runner
  ├─ Preflight Validation (Quick checks before full exploration)
  └─ Session (For each council)
      ├─ Observer (Page state snapshots)
      ├─ Strategist (Action planning via rules)
      ├─ Executor (Action execution)
      └─ Recorder (Network + activity capture)
```

## Components

### Runner (`runner.py`)
- Orchestrates the overall process across all councils
- Loads council list from CSV or JSON
- Runs pre-flight validation to detect issues early
- Manages browser lifecycle and parallel execution
- Generates summary reports

### Session (`session.py`)
- Manages exploration of a single council website
- Main loop: Observe → Strategize → Execute → Repeat
- Detects termination conditions (success, dead-end, loops)
- Records all activity via Recorder

### Observer (`observer.py`)
- Creates structured snapshots of page state
- Finds and scores inputs, buttons, selects, custom dropdowns
- Detects success/error indicators
- Relevance scoring for element identification

### Strategist (`strategist.py`)
- Plans actions using a rule-based system
- Rules operate at different priorities (1-100)
- Proposes multiple candidate actions
- Filters already-tried actions to avoid loops

**Built-in Rules:**
1. **DismissCookieConsentRule** - Handle GDPR cookie banners
2. **FillPostcodeRule** - Fill postcode fields
3. **ClickSubmitAfterFillRule** - Submit forms after filling
4. **SelectAddressRule** - Select from address dropdowns
5. **SelectFromCustomDropdownRule** - Select from custom dropdowns
6. **OpenCustomDropdownRule** - Open closed dropdowns
7. **ClickContinueButtonRule** - Navigate to next steps
8. **ExploratoryClickRule** - Try untested buttons

### Executor (`executor.py`)
- Reliably performs actions on the page
- Handles timeouts, visibility checks, scroll-into-view
- Returns structured results with error diagnostics
- Supports: fill, click, select, wait

### Recorder (`recorder.py`)
- Streams all activity to disk incrementally
- Captures network requests/responses
- Records action sequences and observations
- Takes screenshots at key moments
- Uses JSONL format for easy streaming reads

### Models (`models.py`)
- Data classes for all major concepts
- Observation: Page state snapshot
- Action: Single interaction (fill, click, select, wait)
- ExecutionResult: Action outcome
- SessionResult: Overall session result
- NetworkEntry: Captured HTTP request/response

## Usage

### CLI

```bash
# Run preflight validation only
uv run python -m council_scraper.main preflight \
  --councils data/postcodes_by_council.csv

# Run full scraping
uv run python -m council_scraper.main run \
  --councils data/postcodes_by_council.csv \
  --output output/ \
  --headless

# Run in headed mode (see browser)
uv run python -m council_scraper.main run \
  --councils data/councils.json \
  --output output/ \
  --headed
```

### Programmatic

```python
from council_scraper import Runner, Config

config = Config(headless=False)  # Show browser
runner = Runner("councils.json", "output/", config)

result = await runner.run()
print(f"Success: {result.success_count}, Failed: {result.failure_count}")
```

## Output Structure

```
output/
├── preflight_report.json          # Pre-flight validation results
├── summary_report.json            # Final summary
└── {council_id}/
    ├── observations.jsonl         # Page state snapshots (JSONL)
    ├── actions.jsonl              # Action sequence (JSONL)
    ├── network.jsonl              # Network traffic (JSONL)
    └── screenshots/
        ├── 001_initial.png
        ├── 002_after_fill.png
        └── ...
```

### JSONL Format

Each file is one JSON object per line, allowing:
- Streaming reads without loading entire file
- Appending new entries easily
- Incremental processing

Example reading with `jq`:
```bash
# Filter XHR requests
jq -c 'select(.resource_type == "xhr")' output/council/network.jsonl

# Extract API calls
jq 'select(.request_url | contains("/api"))' output/council/network.jsonl > api_calls.jsonl

# Show action sequence
jq '.action.description' output/council/actions.jsonl
```

## Configuration

### Global Config (Config class)

```python
config = Config(
    # Timeouts (ms)
    page_load_timeout_ms=30000,
    element_timeout_ms=5000,
    settle_timeout_ms=10000,

    # Delays
    typing_delay_ms=50,
    action_delay_ms=500,

    # Limits
    max_iterations=50,
    max_same_url_visits=3,

    # Recording
    screenshot_on_action=True,

    # Browser
    headless=True,
    viewport_width=1280,
    viewport_height=720,
)
```

## Termination Conditions

### Success Indicators
- Page contains: "next collection", "bin day", "collection date", "recycling", etc.
- Contains dates in common formats (e.g., "Monday", "Jan 15")

### Dead-End Indicators
- Error messages: "postcode not found", "invalid address", "no results"
- Login/CAPTCHA walls
- 404 or site error pages

### Loop Detection
- Same URL visited >3 times
- Same page state hash seen multiple times
- Same action attempted multiple times with no change

## Test Files

The repository includes example test scripts:

- `test_preflight.py` - Test preflight validation only
- `test_single.py` - Test single council exploration
- `test_multi.py` - Test with multiple councils

Run with:
```bash
uv run python test_preflight.py
uv run python test_single.py
uv run python test_multi.py
```

## Example Results

```
Testing with 3 councils:
  - Huntingdonshire District Council
  - Ashford Borough Council
  - Watford Borough Council

Processing 2 councils (skipped 1 due to preflight)
  huntingdonshire_district_counc: success (0 iterations)
  watford_borough_council: success (2 iterations)

✓ Summary:
  Successful: 2
  Failed: 0
  Skipped: 1
```

## Design Principles

1. **Exploration Over Precision** - Try multiple approaches, tolerate failures gracefully
2. **Observability** - Record everything; filter during analysis
3. **Stateless Components** - Easy to reason about and debug
4. **Graceful Degradation** - Handle 80-90% automatically; fail cleanly on edge cases

## Known Challenges & Mitigations

### Cookie Consent Banners
- DismissCookieConsentRule runs with highest priority
- Detects via class names, button text, nearby "cookie" text

### CAPTCHAs
- Detected early in preflight
- Flagged for manual handling or CAPTCHA service integration

### Rate Limiting
- Configurable delays between requests
- Respects site timeouts and waits for settle

### Multi-Step Flows
- High iteration limit (default 50)
- Clear progress tracking to avoid loops

## Development Notes

### Adding New Rules

1. Extend `Rule` base class from `strategist.py`
2. Implement `propose()` and `priority` property
3. Register in `Strategist._default_rules()`

Example:
```python
class MyCustomRule(Rule):
    @property
    def priority(self) -> int:
        return 25  # Between FillPostcodeRule (10) and ClickSubmit (20)

    def propose(self, observation, history, test_postcode):
        # Propose actions based on observation
        return [
            Action(
                action_type="click",
                selector="button.my-button",
                description="Click my custom button",
                confidence=0.9,
            )
        ]
```

### Debugging

Enable headed mode and slow motion:
```python
config = Config(headless=False)  # See the browser
config.action_delay_ms = 1000    # 1 second between actions
```

Check recordings:
```bash
# See what the observer found
head output/council/observations.jsonl | jq .

# See action sequence
cat output/council/actions.jsonl | jq '.action.description'

# See all XHR requests
jq -c 'select(.resource_type == "xhr")' output/council/network.jsonl
```

## Future Enhancements

- Parallel execution across multiple councils
- ML-based heuristics for better action selection
- Visual diffing to detect site changes
- Web UI for configuration and results viewing
- Integration with API reverse-engineering tools
