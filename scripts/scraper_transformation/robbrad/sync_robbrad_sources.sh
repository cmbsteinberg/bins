#!/usr/bin/env bash
set -euo pipefail

# Config
REPO="robbrad/UKBinCollectionData"
BRANCH="master"
SOURCE_DIR="uk_bin_collection/uk_bin_collection/councils"
INPUT_JSON="uk_bin_collection/tests/input.json"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# scripts/scraper_transformation/robbrad -> scripts/scraper_transformation -> scripts -> root
PARENT_DIR="$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")")")"
API_DIR="${PARENT_DIR}/api"
LOCAL_DIR="${SCRIPT_DIR}/robbrad_sources"
SCRAPERS_DIR="${API_DIR}/scrapers"
PATCH_SCRIPT="${SCRIPT_DIR}/patch_robbrad_scrapers.py"

CLONE_DIR=$(mktemp -d)
trap 'rm -rf "$CLONE_DIR"' EXIT

# Shallow clone
echo "Cloning ${REPO} (shallow)..."
git clone --depth 1 --branch "$BRANCH" "https://github.com/${REPO}.git" "$CLONE_DIR"

# Create local dir
mkdir -p "$LOCAL_DIR"

# Copy input.json to local dir for reference
cp "$CLONE_DIR/$INPUT_JSON" "$LOCAL_DIR/input.json"

# Run the patch script
# It will read input.json, find corresponding files in CLONE_DIR/SOURCE_DIR,
# filter them, and copy/patch them to SCRAPERS_DIR
echo "Running patch_robbrad_scrapers.py..."
uv run python "$PATCH_SCRIPT" "$CLONE_DIR" "$SCRAPERS_DIR"

echo "Done."
