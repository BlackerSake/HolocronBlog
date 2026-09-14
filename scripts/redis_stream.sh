#!/usr/bin/env bash
STREAM="$1"
GROUP="${2:-}"
TAG="${3:-sample}"

echo "=== $TAG $(date +%H:%M:%S) ==="
echo "XLEN: $(redis-cli XLEN "$STREAM")"
echo "--- XINFO STREAM ---"
redis-cli XINFO STREAM "$STREAM" | head -20
echo "--- XINFO GROUPS ---"
redis-cli XINFO GROUPS "$STREAM"
if [[ -n "$GROUP" ]]; then
  echo "--- XINFO CONSUMERS ($GROUP) ---"
  redis-cli XINFO CONSUMERS "$STREAM" "$GROUP"
  echo "--- XPENDING ($GROUP) ---"
  redis-cli XPENDING "$STREAM" "$GROUP"
fi
echo