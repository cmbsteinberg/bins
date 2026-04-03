## Monkey-Patching the Scrapers

### The problem

All 239 scrapers use synchronous `requests`. Running them in an async FastAPI server means each scrape blocks a thread for 2-10 seconds. Under load (launch spike, cold caches), this exhausts the thread pool.

### The approach

On each deploy (triggered by commit/CI), we:

1. Clone the latest `*_gov_uk.py` files from the upstream HACS repo 
2. Run an AST-transform script that patches each file for async httpx
3. Output patched files to `scrapers/` directory in our repo

### What the transform does

The scrapers follow a consistent pattern. Here's what needs to change:

#### Import replacement

```python
# Before
import requests
from requests.adapters import HTTPAdapter

# After
import httpx
```

#### Session → AsyncClient

```python
# Before
s = requests.Session()
s.headers.update(HEADERS)

# After
s = httpx.AsyncClient(headers=HEADERS, follow_redirects=True)
```

#### Sync → Async calls

```python
# Before
r = s.get(url, headers=headers)
r = s.post(url, headers=headers, data=form_data)

# After
r = await s.get(url, headers=headers)
r = await s.post(url, headers=headers, data=form_data)
```

#### fetch() → async def fetch()

```python
# Before
def fetch(self):

# After
async def fetch(self):
```

#### time.sleep → asyncio.sleep

```python
# Before
import time
time.sleep(2)

# After
import asyncio
await asyncio.sleep(2)
```

#### Custom SSL adapters (e.g. Ashford)

```python
# Before (requests)
class LegacyTLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.set_ciphers("AES256-SHA256")
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.maximum_version = ssl.TLSVersion.TLSv1_2
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)

s = requests.Session()
s.mount("https://", LegacyTLSAdapter())

# After (httpx)
ctx = ssl.create_default_context()
ctx.set_ciphers("AES256-SHA256")
ctx.minimum_version = ssl.TLSVersion.TLSv1_2
ctx.maximum_version = ssl.TLSVersion.TLSv1_2

s = httpx.AsyncClient(verify=ctx, follow_redirects=True)
```

#### requests.post / requests.get (without session)

```python
# Before
r = requests.get(url)
r = requests.post(url, json=payload)

# After
async with httpx.AsyncClient() as client:
    r = await client.get(url)
    r = await client.post(url, json=payload)
```

### Edge cases requiring manual review

Not all files will patch cleanly. The transform script should flag these for manual review:

| Pattern | Issue | Prevalence |
|---------|-------|------------|
| `requests.adapters.HTTPAdapter` subclass | Custom SSL/retry — needs httpx equivalent | ~5 files |
| `requests.exceptions.RequestException` | Replace with `httpx.HTTPError` | ~10 files |

### Compatibility shim

The scrapers import from `waste_collection_schedule`:

```python
from waste_collection_schedule import Collection
```

We provide our own minimal `Collection` class:

```python
# scrapers/waste_collection_schedule.py
from dataclasses import dataclass
from datetime import date

@dataclass
class Collection:
    date: date
    t: str
    icon: str | None = None
```

Similarly, some scrapers use helper services:

```python
from waste_collection_schedule.service.ICS import ICS
```

We either vendor these from the upstream repo or provide compatible stubs.

### Transform script outline

```python
"""
patch_scrapers.py — AST transform to convert requests-based scrapers to async httpx.

Run on deploy: clones upstream, transforms, outputs to scrapers/.
"""
import ast
import astor  # or ast.unparse on 3.9+

REPLACEMENTS = {
    # import-level
    "import requests": "import httpx",
    "from requests.adapters import HTTPAdapter": "",
    # etc.
}

def transform_file(source_path, output_path):
    tree = ast.parse(open(source_path).read())
    # 1. Replace imports
    # 2. Find class Source, method fetch — make async
    # 3. Walk all Call nodes: s.get/s.post → await
    # 4. Replace time.sleep → asyncio.sleep
    # 5. Handle Session() → AsyncClient()
    # 6. Flag files with HTTPAdapter subclasses for manual review
    ...
```

The transform is mechanical for ~90% of files. The remaining ~10% (custom adapters, unusual patterns) get flagged and patched manually once, then maintained.

---