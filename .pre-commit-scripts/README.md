# Pre-commit Scripts

Helper scripts for pre-commit hooks.

## check-councils-json.sh

Ensures that when council YAML files are modified, the generated `bins-website/councils-data.json` is also staged for commit.

This prevents situations where YAML files are updated but the JSON file is forgotten, which would cause the website to be out of sync.

### How it works:

1. Check if any `src/councils/*.yaml` files are in the commit
2. If yes, verify that `bins-website/councils-data.json` is also staged
3. If not, fail with a helpful message

### Manual usage:

```bash
.pre-commit-scripts/check-councils-json.sh
```
