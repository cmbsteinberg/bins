# Pipeline Patch Scripts Refactor

Refactored `pipeline/hacs/patch_scrapers.py` and `pipeline/ukbcd/patch_scrapers.py` to reduce complexity, eliminate duplication, and improve modularity. Guided by `pyscn check` diagnostics.

## Changes

### New: `pipeline/shared.py`

Shared utilities extracted from both pipeline scripts:

- **Path constants**: `PROJECT_ROOT`, `API_DIR`, `SCRAPERS_DIR`, `ADMIN_LOOKUP_PATH`, `OVERRIDES_PATH`
- **`BLOCKED_DOMAINS`** — domains too broad to use as lookup keys
- **`normalise_domain(url)`** — extracts bare domain from a URL
- **`load_admin_lookup()` / `save_admin_lookup(lookup)`** — read/write `admin_scraper_lookup.json`
- **`load_overrides()`** — read `pipeline/overrides.json`

### `pipeline/hacs/patch_scrapers.py`

| Before | After |
|---|---|
| `_analyse_imports` complexity 11 | Split into `_analyse_import_node` + `_analyse_import_from_node` |
| `_patch_directory` complexity 13 | Extracted `_patch_single_file`, `_log_override_info`, `_print_results` |
| 4 separate `_load_*` functions for overrides | Single `_load_override_sets()` returning a 3-tuple, using `shared.load_overrides()` |

### `pipeline/ukbcd/patch_scrapers.py`

| Before | After |
|---|---|
| `main()` complexity 20 | Split into `_load_input_data`, `_should_skip_council`, `_patch_councils`, `_process_council` |
| Monolithic `convert_requests_to_httpx_sync` | Composed from 8 focused sub-functions (`_replace_requests_imports`, `_replace_requests_api_calls`, `_replace_requests_exceptions`, `_strip_urllib3_references`, `_strip_requests_adapters`, `_fix_httpx_compat`, `_hoist_verify_false`, `_ensure_httpx_import`) |
| Duplicated `normalise_domain`, `load_admin_lookup`, `BLOCKED_DOMAINS` | Imported from `pipeline.shared` |
| Inline stats counters | `_PatchStats` dataclass with `log_summary()` |

## Validation

- All functions pass `pyscn check` with zero quality issues (complexity under threshold, no flagged problems)
- Remaining clone warnings are informational (structural similarity between small `str -> str` transform functions)
- `uv run pytest tests/test_frontend.py` passes (7/7)
- Import smoke tests pass for all three modules
- `transform_source()` produces identical output to before
