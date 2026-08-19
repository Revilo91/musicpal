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

# === Prerequisites ===
export PATH="$HOME/.local/bin:$PATH"

if command -v apt-get >/dev/null 2>&1 && [ -w /etc ]; then
  echo "Installing system dependencies..."
  sudo apt-get update -qq
  sudo apt-get install -y build-essential python3 python3-dev curl
else
  echo "Skipping system dependencies (apt not available or no sudo)."
fi

# === uv setup ===
if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# === Virtual environment ===
VENV_DIR="$WORKSPACE_ROOT/.venv"
if [ ! -d "$VENV_DIR" ]; then
  uv venv "$VENV_DIR"
fi

uv pip install --upgrade pip --python "$VENV_DIR/bin/python"
uv pip install -e "$WORKSPACE_ROOT" \
  --config-settings editable_mode=compat \
  --python "$VENV_DIR/bin/python"
uv pip install "homeassistant>=2024.12.0" \
  --python "$VENV_DIR/bin/python"

# Test and lint tooling (pytest-homeassistant-custom-component pins the
# Home Assistant version it was built against).
uv pip install --prerelease=allow \
  pytest pytest-homeassistant-custom-component ruff mypy \
  types-beautifulsoup4 \
  --python "$VENV_DIR/bin/python"

# === Home Assistant config ===
if [ -d "/config" ]; then
  CONFIG_DIR="/config"
else
  CONFIG_DIR="$WORKSPACE_ROOT/.devcontainer/ha-config"
  mkdir -p "$CONFIG_DIR"
fi

mkdir -p "$CONFIG_DIR/custom_components"
rm -f "$CONFIG_DIR/custom_components/musicpal"
ln -s "$WORKSPACE_ROOT/custom_components/musicpal" \
  "$CONFIG_DIR/custom_components/musicpal"

cp "$WORKSPACE_ROOT/.devcontainer/configuration.yaml" \
  "$CONFIG_DIR/configuration.yaml"
cp "$WORKSPACE_ROOT/.devcontainer/automations.yaml" \
  "$CONFIG_DIR/automations.yaml"
cp "$WORKSPACE_ROOT/.devcontainer/scripts.yaml" \
  "$CONFIG_DIR/scripts.yaml"
cp "$WORKSPACE_ROOT/.devcontainer/scenes.yaml" \
  "$CONFIG_DIR/scenes.yaml"

# === Summary ===
echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo "Configuration directory: $CONFIG_DIR"
echo "Virtual environment: $VENV_DIR"
echo ""
echo "To start Home Assistant:"
echo "  $WORKSPACE_ROOT/.devcontainer/start-ha.sh"
echo ""
echo "Home Assistant will be available at http://localhost:8123"
