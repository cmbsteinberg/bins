#!/bin/bash
# Test session commands with network tracking

echo "=== Session Network Tracking Test ==="
echo

# Step 1: Start session on tab 0
echo "Step 1: Starting session on tab 0..."
SESSION_ID=$(./chrome-ws session-start 0 &)
sleep 2
echo "Session ID: $SESSION_ID"
echo

# Step 2: Navigate within session
echo "Step 2: Navigating to example.com..."
./chrome-ws session-cmd "$SESSION_ID" navigate "https://example.com"
sleep 2
echo

# Step 3: Wait for page load
echo "Step 3: Waiting for page to load..."
./chrome-ws session-cmd "$SESSION_ID" wait-for "h1"
echo

# Step 4: Extract heading
echo "Step 4: Extracting heading..."
HEADING=$(./chrome-ws session-cmd "$SESSION_ID" extract "h1")
echo "Heading: $HEADING"
echo

# Step 5: Stop session and export network log
echo "Step 5: Stopping session and exporting network log..."
OUTPUT_FILE="/tmp/network-test-$(date +%s).json"
./chrome-ws session-stop "$SESSION_ID" "$OUTPUT_FILE"
echo

# Step 6: Analyze captured network traffic
echo "Step 6: Analyzing captured network traffic..."
if [ -f "$OUTPUT_FILE" ]; then
    echo "✓ Network log created: $OUTPUT_FILE"
    REQUEST_COUNT=$(cat "$OUTPUT_FILE" | grep -c '"requestId"' || echo "0")
    echo "  Requests captured: $REQUEST_COUNT"
    echo
    echo "  Sample URLs captured:"
    cat "$OUTPUT_FILE" | grep -o '"url": *"[^"]*"' | head -5
    echo
    echo "  Resource types:"
    cat "$OUTPUT_FILE" | grep -o '"resourceType": *"[^"]*"' | sort | uniq -c
else
    echo "✗ ERROR: Network log not created"
    exit 1
fi

echo
echo "=== Session Test Complete ==="
