#!/bin/bash
# Prepare Claude Code cloud sessions: OpenSpec CLI, Python dependencies and
# local development settings, so the OpenSpec skills and the tests work.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# Same version that generated the skills in .claude/ and .opencode/.
OPENSPEC_VERSION=1.14.2
if [ "$(openspec --version 2>/dev/null)" != "$OPENSPEC_VERSION" ]; then
  npm install -g "@fission-ai/openspec@$OPENSPEC_VERSION"
fi
echo 'export OPENSPEC_TELEMETRY=0' >> "$CLAUDE_ENV_FILE"

cd "$CLAUDE_PROJECT_DIR/src"
uv sync
if [ ! -f .env ]; then
  cp .env.example .env
fi
