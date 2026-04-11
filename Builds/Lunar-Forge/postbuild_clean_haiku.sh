#!/usr/bin/env bash
# Post-build scrub for the "Luna Clean (Haiku)" profile.
# Usage: ./postbuild_clean_haiku.sh <output-folder>
#   e.g. ./postbuild_clean_haiku.sh output/draft_xxxxxxxxxx-macos-arm64-0.1.0

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <output-folder>" >&2
  exit 1
fi

OUT="$1"
if [[ ! -d "$OUT" ]]; then
  echo "Not a directory: $OUT" >&2
  exit 1
fi

CONFIG_DIR="$OUT/config"
USER_DATA="$OUT/data/user"

# 1) Pin LLM providers to Claude Haiku only
mkdir -p "$CONFIG_DIR"
cat > "$CONFIG_DIR/llm_providers.json" <<'JSON'
{
  "current_provider": "claude",
  "default_provider": "claude",
  "providers": {
    "claude": {
      "enabled": true,
      "api_key_env": "ANTHROPIC_API_KEY",
      "default_model": "claude-haiku-4-5-20251001",
      "models": ["claude-haiku-4-5-20251001"]
    }
  }
}
JSON
echo "[ok] pinned llm_providers.json -> claude-haiku-4-5-20251001"

# 2) Scrub personal/cached state from data/user (substrate is reseeded on launch)
if [[ -d "$USER_DATA" ]]; then
  rm -f  "$USER_DATA"/alias_cache.json \
         "$USER_DATA"/entity_review_queue.json \
         "$USER_DATA"/hygiene_sweep_state.json
  rm -rf "$USER_DATA"/cache \
         "$USER_DATA"/kozmo_projects
  # Drop the substrate so first launch creates a fresh one from schema.sql
  rm -f  "$USER_DATA"/luna_engine.db \
         "$USER_DATA"/luna_engine.db-shm \
         "$USER_DATA"/luna_engine.db-wal
  echo "[ok] scrubbed data/user (substrate will be recreated on first launch)"
else
  echo "[warn] $USER_DATA not found — skipping scrub"
fi

# 3) Strip macOS quarantine so Gatekeeper doesn't block the launcher
if command -v xattr >/dev/null 2>&1; then
  xattr -dr com.apple.quarantine "$OUT" 2>/dev/null || true
  echo "[ok] removed com.apple.quarantine"
fi

echo
echo "Done. Before launching:"
echo "  export ANTHROPIC_API_KEY=sk-ant-..."
echo "  open \"$OUT/Launch Luna.command\""
