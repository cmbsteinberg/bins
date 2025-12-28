# Extraction Pipeline

This directory contains an automated pipeline for extracting and analyzing UK council bin collection workflows from the [UKBinCollectionData](https://github.com/robbrad/UKBinCollectionData) repository.

## Overview

The pipeline analyzes council bin collection scripts to:
1. Extract API endpoints, request types, and required user inputs
2. Identify councils that can be simplified from Selenium/Playwright to direct HTTP requests
3. Generate structured YAML configuration files for each council
4. Validate CORS compatibility for browser-based implementations

## Pipeline Steps

### 1. Extract Information (`01_extract_info.py`)

**Purpose**: Analyze council Python scripts using LLM to extract bin collection workflow metadata.

**What it does**:
- Fetches council scripts from GitHub API
- Uses Gemini LLM with structured output to extract:
  - Request type (single_api, token_then_api, id_lookup_then_api, selenium, calendar)
  - Required user inputs (postcode, uprn, etc.)
  - API URLs and HTTP methods
  - Response formats and selectors
  - Playwright code for selenium-based councils
- Validates extracted inputs against expected inputs from `input.json`
- Processes up to 50 councils concurrently

**Output**: `data/council_extraction_results.json`

**Usage**:
```bash
uv run python extraction/01_extract_info.py
```

### 2. Playwright Network Capture (`02_playwright_run.py`)

**Purpose**: Execute Playwright automation for selenium-based councils and capture network requests.

**What it does**:
- Filters for councils marked as `selenium` with playwright_code
- Executes Playwright code with test parameters from `input.json`
- Captures network requests (XHR, fetch, document) while filtering noise
- Handles parameter aliasing (e.g., house_number → paon)
- Extracts UPRN from URL query parameters
- Returns captured requests even on execution failure

**Output**: `data/playwright_network_logs.json`

**Usage**:
```bash
uv run python extraction/02_playwright_run.py
```

### 3. Analyze Network Logs (`03_analyze_network_logs.py`)

**Purpose**: Analyze captured network requests to determine if Playwright can be replaced with simple HTTP requests.

**What it does**:
- Loads network logs from Phase 2
- Uses LLM to analyze each council's network traffic
- Proposes alternative request types (single_api, token_then_api, id_lookup_then_api)
- Identifies essential API requests vs analytics/tracking
- Extracts required headers, payloads, and authentication
- Provides confidence ratings (high, medium, low)
- Processes up to 10 councils concurrently to avoid rate limits

**Output**: `data/network_analysis_results.json`

**Usage**:
```bash
uv run python extraction/03_analyze_network_logs.py
```

### 4. YAML Conversion (`04_yaml_conversion.py`)

**Purpose**: Convert JSON extraction results to individual YAML configuration files per council.

**What it does**:
- Merges data from extraction and network analysis
- Auto-corrects misclassified request types (e.g., id_lookup_then_api with only 1 URL → single_api)
- Extracts test inputs from `input.json` (uprn, postcode from URLs)
- Creates API-ready configs or holding patterns for selenium councils
- Generates one YAML file per council in `data/councils/`

**Output**: `data/councils/*.yaml` (one file per council)

**Usage**:
```bash
uv run python extraction/04_yaml_conversion.py
```

### 5. CORS Check (`05_check_cors.py`)

**Purpose**: Validate CORS compatibility for all council API endpoints.

**What it does**:
- Loads council YAML configs
- Fills URL templates with test data
- Makes HEAD requests to check CORS headers
- Processes up to 50 councils concurrently
- Reports success rate, CORS status, and selenium counts

**Output**: Console report with statistics

**Usage**:
```bash
uv run python extraction/05_check_cors.py
```

## Utility Modules

### `utils/gemini.py`

LLM integration using Google's Gemini API for structured output extraction.

**Key Function**:
- `llm_call_with_struct_output(prompt, response_schema)` - Async LLM call with Pydantic schema validation

**Configuration**:
- Requires `PROJECT` environment variable for Vertex AI
- Uses `gemini-3-flash-preview` model by default
- Enables low-level thinking for better extraction quality

### `utils/structured_output.py`

Pydantic schemas for data validation and structured outputs.

**Main Schemas**:
- `CouncilExtraction` - Full extraction spec with implementation details
- `NetworkAnalysisResult` - Network log analysis with simplification proposals
- `RequestType` - Enum for request types (single_api, token_then_api, etc.)
- `HttpMethod` - Enum for HTTP methods (GET, POST, PUT)

### `utils/error_handling.py`

Common error handling and file I/O utilities to reduce code duplication.

**Key Functions**:
- `read_json()` / `write_json()` - JSON file operations with error handling
- `read_yaml()` / `write_yaml()` - YAML file operations with error handling
- `safe_execute()` - Execute functions with exception handling
- `process_batch()` - Async batch processing with semaphore control
- `print_summary()` - Print formatted operation summaries

### `utils/paths.py`

Centralized path management using absolute paths that work from anywhere.

**Key Paths**:
- `paths.data_dir` - Main data directory
- `paths.councils_dir` - Council YAML configs
- `paths.council_extraction_json` - Extraction results
- `paths.playwright_network_logs_json` - Network capture logs
- `paths.network_analysis_json` - Network analysis results
- `paths.input_json` - Test parameters
- `paths.github_api_url` - GitHub API endpoint
- `paths.input_json_url` - Remote input.json URL

**Key Methods**:
- `get_council_yaml_path(council_name)` - Get YAML path for council
- `list_council_names()` - List all council names
- `validate()` - Validate paths and return status

## Data Flow

```
GitHub Council Scripts
         ↓
[01_extract_info.py] → council_extraction_results.json
         ↓
[02_playwright_run.py] → playwright_network_logs.json
         ↓
[03_analyze_network_logs.py] → network_analysis_results.json
         ↓
[04_yaml_conversion.py] → councils/*.yaml
         ↓
[05_check_cors.py] → CORS validation report
```

## Requirements

Environment variables (in `.env`):
```
PROJECT=your-gcp-project-id  # For Vertex AI
```

Python dependencies:
- `google-genai` - Gemini LLM integration
- `aiohttp` - Async HTTP requests
- `playwright` - Browser automation
- `pydantic` - Data validation
- `python-dotenv` - Environment management
- `pyyaml` - YAML file handling
- `httpx` - HTTP client for CORS checks

## Directory Structure

```
extraction/
├── README.md                          # This file
├── 01_extract_info.py                 # LLM extraction from GitHub
├── 02_playwright_run.py               # Network capture via Playwright
├── 03_analyze_network_logs.py         # Network log analysis
├── 04_yaml_conversion.py              # JSON to YAML conversion
├── 05_check_cors.py                   # CORS validation
├── utils/
│   ├── gemini.py                      # LLM integration
│   ├── structured_output.py           # Pydantic schemas
│   ├── error_handling.py              # Error handling utilities
│   └── paths.py                       # Path management
└── data/
    ├── input.json                     # Test parameters
    ├── council_extraction_results.json
    ├── playwright_network_logs.json
    ├── network_analysis_results.json
    └── councils/                      # Individual YAML configs
        ├── council1.yaml
        ├── council2.yaml
        └── ...
```

## Request Type Classification

The pipeline classifies councils into these request types:

- **single_api**: One API call returns all bin data
- **token_then_api**: Get authentication token/session, then query
- **id_lookup_then_api**: Look up address ID from postcode, then query with ID
- **selenium**: Requires browser automation (Playwright/Selenium)
- **calendar**: Date calculation only, no HTTP requests needed

## Notes

- The pipeline uses aggressive concurrency (50 simultaneous requests) for speed
- LLM calls are rate-limited to 10 concurrent requests to avoid API throttling
- Network analysis prioritizes accuracy from captured traffic over initial extraction
- Auto-correction identifies and fixes common LLM misclassifications
- Test inputs are extracted from URLs using regex patterns when not directly provided
- CORS checks use `Origin: https://example.com` to simulate cross-origin requests
