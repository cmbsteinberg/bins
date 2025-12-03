# UK Bin Collection API Wrapper - Project Plan

## Project Overview

### Goal
Create a unified API wrapper for UK council bin collection times. Currently, each council has its own implementation (if any), creating a fragmented landscape. This project will provide a single, standardized interface to query bin collection information from any UK council.

### Data Source
- CSV file (`data/bins_info_with_uprn.csv`) containing:
  - 200+ UK councils
  - Council bin lookup URLs
  - Known API endpoints (where available in `uprn_url` column)
  - Sample postcodes for testing

### Core Approach
Use Claude Agent SDK with bespoke tool to:
1. Discover how each council's bin lookup works
2. Capture the underlying API calls or data sources
3. Generate configuration files for each council
4. Build a runtime wrapper that uses these configs to fetch bin data

---

## Architecture

### Three-Stage Pipeline

#### Stage 1: Discovery (Agent-Powered)
- **Tool**: Claude Agent SDK + Playwright MCP
- **Input**: Council name, URL, sample postcode
- **Process**: Agent navigates site, captures network requests
- **Output**: Detailed JSON discovery file per council

#### Stage 2: Config Generation (Python Script)
- **Tool**: Python script (`generate_config.py`)
- **Input**: Discovery JSON files
- **Process**: Extract API patterns, generate structured configs
- **Output**: YAML config file per council

#### Stage 3: Runtime API (Python Library)
- **Tool**: Python library (`bin_api.py`)
- **Input**: YAML configs + user requests
- **Process**: Execute API calls, parse responses
- **Output**: Standardized bin collection data

### Key Design Principle
**Runtime simplicity**: No browser/Playwright needed at runtime. All complexity is in discovery phase. Runtime is just HTTP requests + parsing.

---

## Council API Types

Based on expected patterns, we'll encounter 4 main types:

### Type 1: Simple JSON API
```yaml
council: "Example Council"
type: api
method: GET
endpoint: "https://api.council.gov.uk/bins/{uprn}"
response_format: json
parsing:
  bin_type: "collections[].type"
  date: "collections[].date"
```

### Type 2: Multi-Step API Chain
```yaml
council: "Example Council"
type: api_chain
steps:
  - name: uprn_lookup
    method: POST
    endpoint: "https://council.gov.uk/lookup"
    body: {"postcode": "{postcode}"}
    response_format: json
    extract: "addresses[0].uprn"

  - name: bins
    method: GET
    endpoint: "https://council.gov.uk/bins/{step1.uprn}"
    response_format: json
    parsing:
      bin_type: "collections[].type"
      date: "collections[].date"
```

### Type 3: API Returning HTML
```yaml
council: "Example Council"
type: api
method: GET
endpoint: "https://council.gov.uk/bins?postcode={postcode}"
response_format: html
parsing:
  container: ".bin-item"
  fields:
    bin_type: ".type::text"
    date: ".date::text"
```

### Type 4: Multi-Step with HTML Response
```yaml
council: "Example Council"
type: api_chain
steps:
  - name: session
    method: POST
    endpoint: "https://council.gov.uk/start"
    response_format: json
    extract: "sessionId"

  - name: bins
    method: GET
    endpoint: "https://council.gov.uk/bins?session={step1.sessionId}&pc={postcode}"
    response_format: html
    parsing:
      container: ".collection"
      fields:
        bin_type: ".bin-name::text"
        date: ".collection-date::text"
```

---

## Implementation Phases

### Phase 1: Project Setup
**Duration**: 30 minutes

**Tasks**:
- Install Claude Agent SDK
- Configure Playwright MCP with network request capture
- Create directory structure:
  ```
  /agents          - Agent definitions
  /output          - Raw discovery JSON files
  /configs         - Generated YAML configs (phase 4+)
  /src             - Runtime API wrapper (phase 6+)
  /scripts         - Utility scripts
  ```

**Select Test Councils** (5-10 councils):
- 2-3 with known APIs (from CSV `uprn_url` column)
- 2-3 without known APIs (blank `uprn_url`)
- Mix to cover all 4 expected config types
- Prioritize variety over ease

---

### Phase 2: Build Discovery Agent
**Duration**: Core development effort

**Create**: `agents/discover_council.py`

**Agent Inputs**:
- Council name
- Council bin lookup URL
- Sample postcode (from CSV)

**Agent Workflow**:
1. Navigate to council URL using Playwright
2. Locate postcode input field
3. Enter sample postcode
4. Submit form / trigger search
5. Wait for bin collection results to appear
6. Extract visual data (everything user sees: bin types, dates, colors)
7. Call `browser_network_requests` MCP tool to get all network activity
8. Analyze network requests to identify bin data source
9. Document findings and output structured JSON

**Key Capabilities Required**:
- Page navigation and interaction
- Data extraction from DOM
- Network request monitoring via `browser_network_requests`
- Pattern recognition (which API call has bin data?)
- Structured output generation

**Agent Output Format** (flexible, will evolve):
```json
{
  "council": "Council Name",
  "url": "https://council.gov.uk/bins",
  "postcode_used": "AB1 2CD",
  "timestamp": "2025-01-06T10:00:00Z",

  "visual_data": {
    "raw_html_snippet": "<div class='bins'>...</div>",
    "bin_types_displayed": ["Black bin - General waste", "Blue bin - Recycling"],
    "dates_displayed": ["Monday 13th January", "Monday 13th January"],
    "additional_info": "Any other relevant visual data"
  },

  "network_requests": [
    {
      "url": "https://api.council.gov.uk/lookup?postcode=AB12CD",
      "method": "GET",
      "headers": {"Content-Type": "application/json"},
      "response_type": "json",
      "response": {"uprn": "12345678", "address": "..."}
    },
    {
      "url": "https://api.council.gov.uk/bins/12345678",
      "method": "GET",
      "headers": {},
      "response_type": "json",
      "response": {
        "collections": [
          {"type": "REFUSE", "date": "2025-01-13"},
          {"type": "RECYCLING", "date": "2025-01-13"}
        ]
      }
    }
  ],

  "agent_analysis": {
    "suspected_bin_api_index": 1,
    "suspected_api_type": "api_chain",
    "parameters_detected": {
      "postcode": "AB12CD",
      "uprn": "12345678"
    },
    "notes": "Free-form agent observations about what happened",
    "confidence": "high|medium|low",
    "issues": ["Any problems encountered"]
  }
}
```

**Design Philosophy**:
- Output is verbose and flexible
- Capture everything, structure later
- No strict schema enforcement yet
- Agent includes its interpretation/analysis
- Preserve raw data for manual review

---

### Phase 3: Run Discovery & Manual Analysis
**Duration**: Depends on council complexity

**Process**:
1. Run agent on all 5-10 test councils
2. Save outputs to `/output/{council_slug}_discovery.json`
3. Monitor for failures and edge cases

**Manual Review**:
- Review all discovery JSON files
- Identify common patterns:
  - Parameter names (uprn vs UPRN vs addressId vs propertyId)
  - Response structures (arrays vs objects, nesting depth)
  - Field names (type vs binType vs wasteType)
  - Date formats
  - Multi-step patterns
- Document edge cases and outliers
- Note what doesn't fit expected types

**Design YAML Schema v1**:
Based on findings, design the structure for YAML config files. This happens AFTER seeing real data, not before.

**Key Questions to Answer**:
- How common are multi-step APIs?
- JSON vs HTML response ratio?
- What parameter variations exist?
- What custom logic is needed?
- What's the most flexible schema structure?

---

### Phase 4: Build Config Generator
**Duration**: Medium development effort

**Create**: `scripts/generate_config.py`

**Purpose**: Transform raw discovery JSON into structured YAML config

**Input**: Discovery JSON file from Phase 3
**Output**: Structured YAML config file

**Core Logic**:

```python
def generate_config(discovery_json_path):
    """
    Transform discovery data into structured config
    """
    discovery = load_json(discovery_json_path)

    # 1. Determine config type
    config_type = determine_type(discovery['network_requests'])

    # 2. Filter relevant API calls
    api_calls = filter_bin_related_requests(
        discovery['network_requests'],
        discovery['visual_data']
    )

    # 3. Build request templates
    steps = []
    for call in api_calls:
        step = {
            'method': call['method'],
            'endpoint': templatize_url(call['url']),
            'response_format': call['response_type'],
            'parameters': detect_parameters(call)
        }
        steps.append(step)

    # 4. Build parsing rules
    parsing = map_response_to_output(
        api_calls[-1]['response'],  # Final API call has bin data
        discovery['visual_data']
    )

    # 5. Generate config
    config = {
        'council': discovery['council'],
        'type': config_type,
        'discovered_at': discovery['timestamp'],
        'raw_discovery_path': discovery_json_path,
        'confidence': calculate_confidence(discovery),
        'needs_review': should_flag_for_review(discovery),
        'unmapped_fields': find_unmapped_fields(discovery),

        # API details (schema depends on Phase 3 findings)
        'api': build_api_config(steps),
        'parsing': parsing,
    }

    return config

def templatize_url(url):
    """
    Convert: https://api.council.gov.uk/bins/12345678
    To:      https://api.council.gov.uk/bins/{uprn}
    """
    # Pattern matching to identify dynamic segments
    pass

def detect_parameters(api_call):
    """
    Identify what parameters are needed and where they come from
    Returns: {'uprn': 'from_step1', 'postcode': 'user_input'}
    """
    pass

def map_response_to_output(api_response, visual_data):
    """
    Correlate API response fields with visual data
    to identify which fields contain bin type, date, etc.
    """
    pass
```

**Features**:
- Handles all 4 config types
- Flags ambiguous cases for human review
- Embeds confidence scores
- Tracks unmapped/unusual fields
- Preserves link to raw discovery data

**Output Example** (schema TBD based on Phase 3):
```yaml
council: "Cambridge City Council"
slug: "cambridge"
type: "api"
discovered_at: "2025-01-06T10:00:00Z"
confidence: 85
needs_review: false

api:
  method: GET
  endpoint: "https://servicelayer3c.azure-api.net/wastecalendar/collection/search/{uprn}"
  parameters:
    uprn: "{user_uprn}"
    authority: "CCC"
    numberOfCollections: "255"
  response_format: json

parsing:
  bin_type: "collections[].type"
  date: "collections[].date"
  mapping:
    "REFUSE": "general_waste"
    "RECYCLING": "recycling"

metadata:
  raw_discovery: "/output/cambridge_discovery.json"
  unmapped_fields: []
  warnings: []
```

---

### Phase 5: YAML Config Schema Design
**Duration**: Design task, completed during Phase 3/4

**Note**: Schema will be designed AFTER reviewing real discovery data, not before.

**Required Elements** (minimum):
- Council identification
- Config type (api, api_chain, etc.)
- API endpoint(s) and methods
- Parameter definitions
- Response parsing rules
- Metadata (confidence, review flags)

**Flexible Elements** (evolve as needed):
- Parameter mapping (standardize variations)
- Field translations (council terms → standard terms)
- Custom handlers for edge cases
- Authentication/headers
- Rate limiting
- Error handling

**Extension Mechanism**:
For councils that don't fit the standard pattern:
```yaml
custom_logic:
  handler: "custom_handlers.special_council"
  notes: "Explain why custom logic needed"
```

---

### Phase 6: Build Runtime API Wrapper
**Duration**: Medium development effort

**Create**: `src/bin_api.py`

**Purpose**: Unified Python library to fetch bin times from any council

**Core Interface**:
```python
class BinAPIWrapper:
    def __init__(self, config_dir: str = "./configs"):
        """Load all council configs"""
        self.configs = self._load_all_configs(config_dir)

    def get_bin_times(self, council: str, postcode: str, uprn: str = None):
        """
        Fetch bin collection times for a council

        Args:
            council: Council name or slug
            postcode: UK postcode
            uprn: Unique Property Reference Number (if known)

        Returns:
            Standardized bin collection data
        """
        config = self.configs[council]

        # Execute request(s) based on config type
        if config['type'] == 'api':
            response = self._execute_single_api(config, postcode, uprn)
        elif config['type'] == 'api_chain':
            response = self._execute_chain(config, postcode, uprn)

        # Parse response based on format
        if config['response_format'] == 'json':
            data = self._parse_json(response, config['parsing'])
        elif config['response_format'] == 'html':
            data = self._parse_html(response, config['parsing'])

        return self._normalize_output(data, council, postcode)
```

**Implementation Details**:

```python
def _execute_single_api(self, config, postcode, uprn):
    """Execute a single API call"""
    params = self._substitute_parameters(
        config['parameters'],
        {'postcode': postcode, 'uprn': uprn}
    )

    if config['method'] == 'GET':
        return requests.get(config['endpoint'].format(**params))
    elif config['method'] == 'POST':
        return requests.post(config['endpoint'], json=config['body'])

def _execute_chain(self, config, postcode, uprn):
    """Execute multi-step API chain"""
    context = {'postcode': postcode, 'uprn': uprn}

    for step in config['steps']:
        response = self._execute_step(step, context)

        # Extract value for next step
        if 'extract' in step:
            extracted_value = self._extract_from_response(
                response,
                step['extract']
            )
            context[step['name']] = extracted_value

    return response  # Final response contains bin data

def _parse_json(self, response, parsing_rules):
    """Parse JSON response using JSONPath"""
    from jsonpath_ng import parse

    data = response.json()
    results = []

    for rule_name, rule_path in parsing_rules.items():
        jsonpath_expr = parse(rule_path)
        matches = jsonpath_expr.find(data)
        results.append({rule_name: [m.value for m in matches]})

    return results

def _parse_html(self, response, parsing_rules):
    """Parse HTML response using BeautifulSoup"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(response.text, 'html.parser')
    container = soup.select(parsing_rules['container'])

    results = []
    for item in container:
        result = {}
        for field, selector in parsing_rules['fields'].items():
            element = item.select_one(selector.replace('::text', ''))
            result[field] = element.get_text(strip=True)
        results.append(result)

    return results

def _normalize_output(self, data, council, postcode):
    """Convert to standardized output format"""
    return {
        'council': council,
        'postcode': postcode,
        'collections': [
            {
                'bin_type': item['bin_type'],
                'next_collection': item['date'],
                # ... standardized fields
            }
            for item in data
        ]
    }
```

**Dependencies**:
- `requests` - HTTP requests
- `beautifulsoup4` - HTML parsing
- `jsonpath-ng` - JSON parsing
- `pyyaml` - Config loading
- `python-dateutil` - Date parsing

**No Playwright at Runtime**: All complexity is handled in discovery phase. Runtime is just HTTP + parsing.

---

### Phase 7: Testing & Validation
**Duration**: Per-council testing

**For Each Test Council**:

1. **Verify Discovery**:
   - Review discovery JSON for accuracy
   - Confirm visual data matches what agent saw
   - Validate network requests are complete

2. **Validate Config**:
   - Review generated YAML config
   - Check endpoint templates are correct
   - Verify parameter mappings
   - Test parsing rules manually

3. **Test Runtime Wrapper**:
   ```python
   wrapper = BinAPIWrapper()
   result = wrapper.get_bin_times('cambridge', 'CB3 9AF')
   print(result)
   ```
   - Confirm API calls execute successfully
   - Validate response parsing
   - Compare output to original visual data

4. **Document Issues**:
   - Record failures and reasons
   - Note edge cases
   - Track councils needing custom logic

**Success Criteria**:
- Discovery agent completes for all test councils
- Configs generated for all types
- Runtime wrapper successfully retrieves bin times
- Output matches expected data

---

### Phase 8: Documentation & Scale-Up Planning
**Duration**: Documentation effort

**Deliverables**:

1. **Technical Documentation**:
   - Agent architecture and usage
   - Config generator logic
   - Runtime wrapper API reference
   - YAML schema specification

2. **Findings Report**:
   - Patterns discovered across councils
   - Distribution of config types
   - Common parameters and variations
   - Edge cases and handling strategies

3. **Scale-Up Plan**:
   - Prioritize remaining councils
   - Batch processing strategy
   - Error handling and retries
   - Quality assurance process
   - Timeline for full coverage

4. **Known Issues & Limitations**:
   - Councils that don't work
   - Required manual interventions
   - Rate limiting considerations
   - Maintenance requirements

**Next Steps** (Beyond PoC):
- Scale agent runs to all 200+ councils
- Build monitoring/alerting for API changes
- Create public API endpoints
- Add caching layer
- Handle authentication where needed
- Build admin interface for config management

---

## Key Design Decisions

### 1. Agent-Based Discovery vs Manual Mapping
**Decision**: Use agent-based discovery
**Rationale**: 200+ councils make manual mapping infeasible. Agent can systematically discover and document at scale.

### 2. Schema Design Timing
**Decision**: Design schema AFTER seeing real data
**Rationale**: Can't anticipate all variations. Flexible initial output allows schema to evolve based on actual patterns.

### 3. Runtime Complexity
**Decision**: No browser/Playwright at runtime
**Rationale**: Discovered APIs can be called directly. Browser overhead not needed once endpoints are known. Faster, cheaper, more reliable.

### 4. Config Format
**Decision**: YAML (not JSON)
**Rationale**: More readable for human review, supports comments, standard for config files.

### 5. Multi-Phase Approach
**Decision**: Discovery → Config → Runtime (3 separate stages)
**Rationale**: Clear separation of concerns. Discovery is one-time cost. Runtime must be fast/efficient.

### 6. Validation Strategy
**Decision**: Start with 5-10 councils, manual review, then scale
**Rationale**: Prove concept on diverse subset before investing in full-scale automation.

---

## Success Metrics

### Phase 1-2 Success:
- Agent successfully discovers bin data for 5-10 councils
- Discovery outputs contain sufficient detail for config generation
- All 4 config types represented in test set

### Phase 3-4 Success:
- Configs generated for all test councils
- 80%+ confidence on auto-generated configs
- Clear flagging of ambiguous cases

### Phase 5-6 Success:
- Runtime wrapper successfully calls APIs
- Standardized output matches visual data
- No Playwright needed at runtime

### Overall PoC Success:
- End-to-end pipeline working
- Validated on diverse council types
- Clear path to scaling
- Documentation complete

---

## Risks & Mitigations

### Risk: Councils change their websites/APIs
**Mitigation**: Store discovery date, implement monitoring, plan for re-discovery

### Risk: Some councils have no APIs (JavaScript-rendered only)
**Mitigation**: Flag as "unsupported", consider alternative approaches for subset

### Risk: Agent can't navigate complex forms
**Mitigation**: Start with simple cases, document failures, may need manual config for some

### Risk: Rate limiting / blocking
**Mitigation**: Add delays, rotate IPs if needed, respect robots.txt

### Risk: Authentication required
**Mitigation**: Document requirement, add auth support to schema v2+

---

## Future Enhancements

- Public API endpoint (REST/GraphQL)
- Webhook notifications for bin day reminders
- Mobile app integration
- UPRN lookup service (postcode → UPRN)
- Change detection and alerting
- Historical data storage
- Coverage statistics and reporting
- Council API health monitoring

---

## Appendix: Test Council Selection Criteria

When selecting 5-10 councils for PoC:

### Must Include:
- At least 1 with known API (from CSV `uprn_url`)
- At least 1 without known API (blank `uprn_url`)
- At least 1 Scottish council
- At least 1 Welsh council
- Mix of urban/rural
- Mix of large/small councils

### Diversity Goals:
- Different website vendors/platforms
- Variety of complexity levels
- Different response formats
- Geographic distribution

### Suggested Test Set:
1. Cambridge City Council (known API, JSON)
2. Aberdeen City Council (no known API)
3. Brighton and Hove (known API, likely complex)
4. Bridgend County Borough Council (Wales)
5. East Ayrshire Council (Scotland)
6. Canterbury City Council
7. Bath and North East Somerset Council (known API)
8. Conwy County Borough Council (Wales, known API)
9. Darlington Borough Council (known API)
10. Peterborough City Council (known API)

Adjust based on initial discovery results.
