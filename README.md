# Bins - UK Council Bin Collection API

A Python library and API for looking up bin collection schedules across UK councils. This project provides a unified interface to query bin collection information from 200+ UK local authorities.

## Features

- Support for 200+ UK councils with pre-configured YAML definitions
- Multiple request types: single API calls, token-based authentication, ID lookups, and browser automation
- UPRN (Unique Property Reference Number) lookup from postcodes
- Local authority information lookup
- Async and sync interfaces
- Built-in retry logic and error handling
- Rate limiting for external APIs

## Installation

Requires Python 3.13 or higher.

```bash
# Clone the repository
git clone <repository-url>
cd bins

# Install dependencies using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

## Quick Start

### Looking Up Bin Collection Times

```python
from src.bin_lookup import BinLookup

# Initialize the lookup service
lookup = BinLookup()

# Query a council (example: Brighton & Hove)
response = lookup.lookup(
    council_name="BrightonandHoveCouncil",
    inputs={"uprn": "12345678"}
)

print(f"Status: {response.status_code}")
print(response.text)
```

### Finding UPRN and Local Authority

```python
from src.uprn_lookup import PostcodeFinder

with PostcodeFinder() as finder:
    # Get addresses for a postcode
    addresses = finder.uprn_lookup("BR8 7RE")

    for addr in addresses:
        print(f"Address: {addr['full_address']}")
        print(f"UPRN: {addr['uprn']}")

    # Get local authority information
    if addresses:
        target_address = addresses[0]['full_address']
        authority = finder.admin_lookup("BR8 7RE", user_address=target_address)
        print(f"Council: {authority['child_name']}")
```

### CLI Usage

```bash
# Run bin lookup via CLI
python -m src.main BrightonandHoveCouncil uprn=12345678

# List available councils
python -m src.main
```

### Async Usage

```python
import asyncio
from src.bin_lookup import BinLookup

async def lookup_bins():
    lookup = BinLookup()
    response = await lookup.lookup_async(
        council_name="BrightonandHoveCouncil",
        inputs={"uprn": "12345678"}
    )
    return response

# Run async lookup
result = asyncio.run(lookup_bins())
```

## Project Structure

```
bins/
├── src/
│   ├── bin_lookup.py       # Main BinLookup class for council queries
│   ├── uprn_lookup.py      # PostcodeFinder for UPRN/authority lookups
│   ├── main.py             # CLI interface
│   ├── councils/           # YAML configs for 200+ UK councils
│   └── utils/
│       ├── utils.py        # Helper functions (URL templating, etc.)
│       └── exceptions.py   # Custom exceptions
├── tests/                  # Test suite
├── extraction/             # Data extraction tools (see extraction/README.md)
└── pyproject.toml          # Project dependencies and metadata
```

**Note:** The `extraction/` directory contains separate tooling for discovering and extracting council bin collection APIs. See `extraction/README.md` for details on that process.

## Council Configuration

Each council is defined by a YAML file in `src/councils/`. Example structure:

```yaml
council: BrightonandHoveCouncil
request_type: single_api
required_user_input:
  - uprn
api_urls:
  - "https://example.com/api/bins?uprn={uprn}"
api_methods:
  - GET
response_format: json
```

### Supported Request Types

1. **single_api** - Simple GET/POST request to a single endpoint
2. **token_then_api** - Fetch a session token, then make authenticated request
3. **id_lookup_then_api** - Look up an ID from postcode, then query with that ID
4. **selenium** - Requires browser automation (Playwright/Selenium)
5. **calendar** - iCal/calendar file parsing (not yet implemented)

## API Reference

### BinLookup

Main class for querying council bin collection schedules.

**Methods:**
- `lookup(council_name: str, inputs: dict) -> httpx.Response` - Synchronous lookup
- `lookup_async(council_name: str, inputs: dict) -> httpx.Response` - Async lookup
- `load_council_config(council_name: str) -> dict` - Load council YAML config

**Parameters:**
- `councils_dir` - Path to council YAML configs (default: `extraction/data/councils`)
- `timeout` - Request timeout in seconds (default: 30)
- `verify_ssl` - Verify SSL certificates (default: True)
- `use_requests_fallback` - Fallback to requests library for SSL issues (default: True)
- `max_retries` - Number of retry attempts (default: 0)

### PostcodeFinder

Class for UPRN and local authority lookups.

**Methods:**
- `uprn_lookup(postcode: str) -> List[Dict]` - Get addresses and UPRNs for postcode
- `admin_lookup(postcode: str, user_address: str = None) -> Dict` - Get local authority info

**Returns (uprn_lookup):**
```python
[
    {"full_address": "1 High Street, Town, AB1 2CD", "uprn": "12345678"},
    ...
]
```

**Returns (admin_lookup):**
```python
{
    "child_name": "Brighton and Hove City Council",
    "child_url": "https://www.brighton-hove.gov.uk",
    "child_tier": "unitary",
    "parent_name": None,
    "parent_url": None,
    "parent_tier": None
}
```

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src
```

### Code Quality

```bash
# Format code
ruff format .

# Lint code
ruff check .
```

### Adding a New Council

1. Create a YAML file in `src/councils/` named `{CouncilName}.yaml`
2. Define the required fields:
   - `council`: Council name
   - `request_type`: One of the supported types
   - `required_user_input`: List of required inputs (e.g., `postcode`, `uprn`)
   - `api_urls`: List of API endpoint URL templates
   - `api_methods`: List of HTTP methods (GET/POST)
   - `response_format`: Expected response format (json/html/xml)
3. Add test inputs for validation
4. Test the configuration

## Error Handling

The library includes comprehensive error handling:

- **ConfigError** - Invalid council configuration
- **FileNotFoundError** - Council config not found
- **ValueError** - Missing required inputs
- **NotImplementedError** - Council requires unimplemented features (e.g., Selenium)
- **httpx.HTTPError** - Network/HTTP errors
- **httpx.TimeoutException** - Request timeouts

## Rate Limiting

The `PostcodeFinder` class automatically rate-limits requests to external APIs:
- 1 request per second to GOV.UK and council APIs
- Automatic exponential backoff on retries (3 attempts max)

## Dependencies

Key dependencies:
- **httpx** - HTTP client with async support
- **pyyaml** - YAML config parsing
- **playwright** - Browser automation for complex sites
- **pydantic** - Data validation
- **tenacity** - Retry logic with exponential backoff
- **requests** - Fallback HTTP client for SSL issues

See `pyproject.toml` for the full dependency list.

## License

See LICENSE file for details.

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Support

For issues, questions, or contributions, please open an issue on the repository.
