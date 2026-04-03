
## API Endpoints

I am setting up an API for UK Bin Collections. Each council has its own scraper file in src/scrapers/. Each has test cases, and it's own class called Source. I have monkey patched them to work asynchrnonously.

I now need to write a fastapi wrapper to allow me to deploy this as an api. Below I have laid out what I want the endpoints to look like roughly. I want both an api to be a backend for my website which allows people to search for their bin times, but also a public api for use by people like the home automation community.

src/address_lookup/address_lookup.py gives a sense of how I will get user info on postcodes, address, etc

The scrapers are from the hacs_waste_collection_schedule repo. You may need to look at the following links at some point for ideas on how to daisy chain these files together:
- https://github.com/mampfes/hacs_waste_collection_schedule/tree/master/custom_components/waste_collection_schedule
- https://github.com/mampfes/hacs_waste_collection_schedule/tree/master/custom_components/waste_collection_schedule/waste_collection_schedule

Please write your scripts into src/api/ You may need multiple .py files for this. Do not owrry about caching for now.

### `GET /api/lookup/{uprn}`

Primary lookup. Returns cached schedule or triggers scrape.

**Query params:**
- `council` (required): scraper module name, e.g. `croydon_gov_uk`
- `postcode` (optional): required by some scrapers
- `address` (optional): required by some scrapers (e.g. Croydon's `houseID`)

**Response:**
```json
{
  "uprn": "100020194783",
  "council": "birmingham_gov_uk",
  "cached": true,
  "cached_at": "2026-03-20T02:00:00Z",
  "collections": [
    {
      "date": "2026-03-24",
      "type": "Household Collection",
      "icon": "mdi:trash-can"
    },
    {
      "date": "2026-03-27",
      "type": "Recycling Collection",
      "icon": "mdi:recycle"
    }
  ]
}
```

**Error responses:**
- `404`: Council scraper not found
- `422`: Missing required params for this council's scraper
- `503`: Council site unreachable / scraper failing
- `429`: Too many requests (per-IP rate limit)

### `GET /api/councils`

Returns list of supported councils with their required parameters.

```json
[
  {
    "id": "birmingham_gov_uk",
    "name": "Birmingham City Council",
    "url": "https://birmingham.gov.uk",
    "params": ["uprn", "postcode"]
  },
  {
    "id": "croydon_gov_uk",
    "name": "Croydon Council",
    "url": "https://croydon.gov.uk",
    "params": ["postcode", "houseID"]
  }
]
```

### `GET /api/health`

Returns per-council scraper health status (last success/failure, error rate).


## Public API

### Design principle

The public API and the web app share the same server, same endpoints, same cache. There is no separate API service. The only difference is rate limiting tiers.

No API keys. The API is open — anyone can call it. Rate limiting is the only gate.

### Versioned route prefix

```
# Web app (internal frontend calls)
GET /api/lookup/{uprn}?council=birmingham_gov_uk&postcode=B27+6TF

# Public API (third parties, versioned)
GET /api/v1/lookup/{uprn}?council=birmingham_gov_uk&postcode=B27+6TF
GET /api/v1/councils
```

`/api/v1/` is the stable, documented, versioned surface for external consumers. Internal frontend routes can break freely; `/api/v1/` cannot without a version bump.

Both hit the same handler — the v1 prefix is just a FastAPI router alias:

```python
router = APIRouter()

@router.get("/lookup/{uprn}")
async def lookup(uprn: str, council: str, postcode: str | None = None, address: str | None = None):
    ...

# Mount at both paths
app.include_router(router, prefix="/api")
app.include_router(router, prefix="/api/v1")
```

### Public endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/councils` | List supported councils + required params |
| `GET` | `/api/v1/lookup/{uprn}` | Get collection schedule for a UPRN |

That's it. Two endpoints. Address/UPRN resolution (postcodes.io, Placecube) stays client-side — not our data, no reason to proxy it.

### Rate limiting (no keys)

Rate limiting is per-IP using a sliding window in Redis:

```python
async def rate_limit(request: Request):
    ip = request.client.host  # or X-Forwarded-For behind Cloudflare
    key = f"ratelimit:{ip}:{datetime.now().strftime('%Y-%m-%d')}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 86400)
    if count > DAILY_LIMIT:
        raise HTTPException(429, detail="Rate limit exceeded. Try again tomorrow.")
```


### Documentation

FastAPI auto-generates OpenAPI docs at `/api/v1/docs` (Swagger UI) and `/api/v1/redoc` (ReDoc). No custom docs site needed for v1.

Add a brief landing page at the root with:
- What the API does (one sentence)
- Example `curl` command
- Link to `/api/v1/docs`
- Rate limit policy
- Link to GitHub repo
