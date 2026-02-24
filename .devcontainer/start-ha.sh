#!/usr/bin/env bash
set -e

# === Workspace discovery ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if [ -d "/workspaces/musicpal" ]; then
  WORKSPACE_ROOT="/workspaces/musicpal"
else
  WORKSPACE_ROOT="$PROJECT_ROOT"
fi

# === Home Assistant config ===
if [ -d "/config" ]; then
  CONFIG_DIR="/config"
else
  CONFIG_DIR="$WORKSPACE_ROOT/.devcontainer/ha-config"
fi

VENV_DIR="$WORKSPACE_ROOT/.venv"
if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "Error: virtual environment not found at $VENV_DIR" >&2
  echo "Run .devcontainer/setup.sh first." >&2
  exit 1
fi

export PATH="$HOME/.local/bin:$PATH"

echo "Starting Home Assistant..."
echo "Configuration: $CONFIG_DIR"
echo "Web UI: http://localhost:8123"
echo ""
echo "Press Ctrl+C to stop Home Assistant"
echo ""

cd "$WORKSPACE_ROOT"
"$VENV_DIR/bin/python" -m homeassistant -c "$CONFIG_DIR"
