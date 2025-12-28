#!/bin/bash
# Check if councils-data.json needs to be updated when YAML files change

# Check if any council YAML files are being committed
if git diff --cached --name-only | grep -q "^src/councils/.*\.yaml$"; then
    # Check if councils-data.json is also staged
    if ! git diff --cached --name-only | grep -q "bins-website/councils-data.json"; then
        echo "⚠️  Council YAML files changed but councils-data.json not staged!"
        echo "   Run: python3 bins-website/convert-yaml.py"
        echo "   Then: git add bins-website/councils-data.json"
        exit 1
    fi
fi

exit 0
