# Bin Collection API Discovery

Automated discovery system for UK council bin collection APIs using Claude Agent SDK.

## Overview

This system uses browser automation with network traffic capture to discover how each council's bin lookup system works. The goal is to:

1. **Navigate** council websites automatically
2. **Capture** all network requests during bin lookup
3. **Identify** the actual API being used (not just the webpage)
4. **Generate** configuration files for runtime API access

## Architecture

```
chrome-ws (Node.js CLI)
    ↓ (bash commands)
Claude Agent SDK
    ↓ (processes JSON)
Network Analyzer (Python)
    ↓ (generates YAML)
Config Generator (Python)
```

### Components

- **`using-chrome-directly/chrome-ws`**: Enhanced Chrome DevTools Protocol tool with network tracking
- **`models.py`**: Pydantic models for bin data, network requests, and configs
- **`network_analyzer.py`**: Identifies bin API from captured network traffic
- **`config_generator.py`**: Transforms discovery data into YAML configs
- **`discovery_example.py`**: Example showing the complete workflow

## How It Works

### 1. chrome-ws Enhancement

The `chrome-ws` tool has been enhanced with three new commands for persistent network monitoring:

```bash
# Start session (begins capturing network traffic)
SESSION_ID=$(chrome-ws session-start 0)

# Execute commands within session
chrome-ws session-cmd $SESSION_ID navigate "https://council.gov.uk/bins"
chrome-ws session-cmd $SESSION_ID fill "input#postcode" "AB12 3CD"
chrome-ws session-cmd $SESSION_ID click "button#search"
chrome-ws session-cmd $SESSION_ID wait-for "div.results"

# Stop session and export network log
chrome-ws session-stop $SESSION_ID network.json
```

The network log includes:
- All HTTP requests made during the session
- Request/response headers
- Request/response bodies
- Timing information
- Resource types (XHR, Fetch, Document, etc.)

### 2. Network Analysis

The `NetworkAnalyzer` processes the captured traffic to identify the bin API:

**Stage 1: Keyword Scoring**
- Scores each request based on URL keywords ('bin', 'waste', 'collection', etc.)
- Prioritizes XHR/Fetch requests over page loads
- Checks response bodies for bin-related content and dates
- Filters to top 5 candidates

**Stage 2: AI Analysis** (optional)
- Claude analyzes top candidates with full context
- Identifies the actual bin data API
- Provides confidence score and reasoning

**Output:**
```python
APIAnalysis(
    api_url="https://council.gov.uk/api/bins?postcode=AB12CD",
    method="GET",
    parameters={"query": {"postcode": "AB12CD"}},
    response_format="json",
    confidence=0.95,
    reasoning="XHR request containing JSON with bin types and dates"
)
```

### 3. Config Generation

The `ConfigGenerator` creates YAML configs for runtime use:

```yaml
council: Stirling Council
slug: stirling_council
confidence: 0.95

api:
  method: GET
  endpoint: https://my.stirling.gov.uk/api/bins
  parameters:
    query:
      postcode: '{postcode}'  # Template variable
  response_format: json

parsing:
  date_format: '%Y-%m-%d'
  bin_types:
    general_waste: generalWaste
    recycling: recycling
    food_waste: foodWaste
    garden_waste: gardenWaste

metadata:
  postcode_tested: FK15 0AF
  notes: Direct API, simple GET request
```

## Usage

### Setup

1. Install dependencies:
```bash
uv sync
```

2. Ensure Chrome is accessible (chrome-ws will auto-detect platform)

### Running Discovery (Example Script)

```bash
cd src/agents
python discovery_example.py
```

This will:
- Start Chrome with remote debugging
- Navigate to Stirling Council website
- Attempt to fill postcode form
- Capture all network traffic
- Analyze and identify the bin API
- Generate YAML config

### Using with Claude Agent SDK

The agent is defined in `bin_discovery_agent.py` and can be invoked in three ways:

#### 1. Single Council Discovery

```bash
cd src/agents
python run_discovery.py "Stirling Council" "https://my.stirling.gov.uk/" "FK15 0AF"
```

This will:
- Launch the Claude Agent SDK agent
- Agent reads `using-chrome-directly/SKILL.md` to learn chrome-ws commands
- Agent executes bash commands to navigate and interact with the site
- Agent captures network traffic and analyzes it
- Saves network.json and config.yaml

#### 2. Batch Discovery (5 councils for testing)

```bash
cd src/agents
python run_batch_discovery.py
```

#### 3. Batch Discovery (all 197 councils)

```bash
cd src/agents
python run_batch_discovery.py --all
```

### How the Agent Works

The `bin_discovery_agent.py` creates an `AgentDefinition` that:

1. **Embeds the SKILL.md documentation** - Agent learns chrome-ws commands
2. **Provides detailed instructions** - Agent knows the discovery workflow
3. **Uses bash commands** - Agent executes `chrome-ws` directly via subprocess
4. **Calls Python analyzers** - Agent runs `network_analyzer.py` and `config_generator.py`

**Agent Architecture:**
```python
from claude_agent_sdk import AgentDefinition, query

# Define the agent (in bin_discovery_agent.py)
bin_discovery_agent = AgentDefinition(
    description="Discovers bin collection APIs...",
    prompt=AGENT_PROMPT,  # Includes SKILL.md + instructions
    tools=None,  # Uses bash - no tool restrictions
    model="sonnet"
)

# Invoke the agent (in run_discovery.py)
result = query(
    prompt="Discover API for Stirling Council at https://...",
    agent=bin_discovery_agent
)
```

The agent is **fully autonomous** - it:
- Inspects page DOM to find selectors
- Tries different form field patterns
- Adapts to each council's unique website
- Analyzes network traffic to identify APIs
- Generates structured configs

## File Structure

```
src/agents/
├── using-chrome-directly/
│   ├── chrome-ws                    # Enhanced with session commands
│   ├── SKILL.md                     # Documentation (updated)
│   ├── test-session.sh              # Test script
│   └── test-*.sh                    # Other test scripts
├── models.py                        # Pydantic models
├── network_analyzer.py              # API identification logic
├── config_generator.py              # YAML config generation
├── discovery_example.py             # Complete workflow example
├── prompts.py                       # Agent prompts (existing)
└── README.md                        # This file

data/
├── postcodes_by_council.csv         # Input: 197 councils
└── discoveries/                     # Output: Discovery JSON files
    └── stirling_council_discovery.json

configs/                             # Output: YAML configs
└── stirling_council.yaml
```

## Data Models

### NetworkRequest
Captured request/response from Chrome DevTools Protocol:
- `request_id`, `url`, `method`
- `request_headers`, `request_body`
- `response_status`, `response_headers`, `response_body`
- `resource_type`, `timing`, `initiator`

### APIAnalysis
Identified bin API:
- `api_url`, `method`, `parameters`
- `response_format`, `response_sample`
- `confidence`, `reasoning`

### CouncilDiscovery
Complete discovery output:
- Council details
- Network requests (all captured traffic)
- API analysis (identified API)
- Optional visual data (extracted from page)

### CouncilConfig
Runtime YAML config:
- API endpoint and parameters (with templates like `{postcode}`)
- Parsing rules (date formats, bin type mappings)
- Metadata (confidence, notes)

## Network Log Format

The `session-stop` command exports JSON with this structure:

```json
[
  {
    "requestId": "1234.56",
    "url": "https://council.gov.uk/api/bins?postcode=AB12CD",
    "method": "GET",
    "requestHeaders": {...},
    "requestBody": null,
    "responseStatus": 200,
    "responseHeaders": {...},
    "responseBody": "{\"collections\": [...]}",
    "resourceType": "xhr",
    "timing": {...},
    "initiator": {...}
  }
]
```

## Next Steps

1. **Test on more councils**: Run discovery on the 197 councils in `postcodes_by_council.csv`
2. **Improve analyzer**: Add more sophisticated API detection heuristics
3. **Build runtime wrapper**: Create library that uses generated configs to fetch bin data
4. **Batch processing**: Process all councils in parallel
5. **Error handling**: Better handling of edge cases (captchas, multi-step forms, etc.)

## Troubleshooting

**Chrome won't start:**
```bash
# Check if Chrome is running
curl http://localhost:9222/json/version

# Kill existing Chrome if needed
pkill -f "remote-debugging-port=9222"

# Start fresh
./using-chrome-directly/chrome-ws start
```

**Session commands fail:**
- Ensure session-start process is still running
- Session IDs are UUIDs - check you're using the correct one
- Use `chrome-ws tabs` to verify Chrome state

**No bin API found:**
- Check network.json manually - look for XHR/Fetch requests
- Some councils use embedded data (no API) - will need different approach
- Try different postcodes if form validation fails

**Config generator produces empty parsing rules:**
- API response might not be JSON
- Response sample might be too short
- Manual config creation may be needed

## References

- [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/)
- [Claude Agent SDK](https://github.com/anthropics/anthropic-agent-sdk)
- [Project Plan](../../PROJECT_PLAN.md)
