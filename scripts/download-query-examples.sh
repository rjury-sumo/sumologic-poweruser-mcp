#!/bin/bash
# Download the query examples database
# This file is too large for git, so we host it externally

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET_FILE="$REPO_ROOT/logs_searches.json"

if [ -f "$TARGET_FILE" ]; then
    echo "✅ logs_searches.json already exists"
    exit 0
fi

echo "Downloading query examples database..."
# Option A: From GitHub release
# curl -L -o "$TARGET_FILE" "https://github.com/yourusername/sumologic-python-mcp/releases/download/v1.0.0/logs_searches.json"

# Option B: From cloud storage (S3, GCS, etc.)
# curl -L -o "$TARGET_FILE" "https://your-storage-url/logs_searches.json"

# Option C: Copy from local source
if [ -f "/Users/rjury/Documents/sumo2025/sumologic-query-examples/logs_searches.json" ]; then
    cp "/Users/rjury/Documents/sumo2025/sumologic-query-examples/logs_searches.json" "$TARGET_FILE"
    echo "✅ Copied logs_searches.json from local source"
else
    echo "❌ Error: logs_searches.json not found"
    echo "Please obtain this file from:"
    echo "  - Project maintainer"
    echo "  - Extract from Sumo Logic published apps"
    echo "  - GitHub release (if available)"
    exit 1
fi
