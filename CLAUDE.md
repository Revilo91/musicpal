# CLAUDE.md – Project Context for Claude AI

This file provides context about the **musicpal** repository to help Claude give accurate, idiomatic assistance.

## Project Overview

**musicpal** is a Python project that serves as a control interface for the _Freecom MusicPal_ hardware media player / internet radio (released ~2007). It has two deployment modes:

1. **CLI tool** (`musicpal` script) – command-line remote control of the device.
2. **Home Assistant custom integration** (`custom_components/musicpal/`) – HACS-compatible integration that exposes the device as a media player and set of sensor entities inside Home Assistant.

## Repository Structure

```
musicpal/
├── musicpal                          # CLI entry point (argparse, routes to API)
├── setup.py                          # Package installation & dependencies
├── pyproject.toml                    # Build system (setuptools), Black config
├── .pre-commit-config.yaml           # black, pylint, mypy hooks
├── hacs.json                         # HACS metadata
├── README.md                         # Main documentation
├── HACS_README.md                    # Home Assistant integration guide
├── INSTALLATION_DE.md                # German installation guide
├── info.md                           # Short integration description
└── custom_components/musicpal/
    ├── __init__.py                   # HA entry point, coordinator, services
    ├── config_flow.py                # UI configuration flow
    ├── const.py                      # Constants (domain, keys, intervals)
    ├── media_player.py               # MediaPlayer entity
    ├── sensor.py                     # Sensor entities (display, uptime, favorites)
    ├── musicpal_api.py               # Async httpx API client
    ├── manifest.json                 # HA integration metadata
    ├── services.yaml                 # Custom service definitions
    ├── strings.json                  # UI strings / translations
    └── translations/
        ├── de.json                   # German
        └── en.json                   # English
```

## Tech Stack

| Area | Technology |
|------|-----------|
| Language | Python 3.8+ |
| HTTP client | `httpx` (async for HA, sync for CLI) |
| HTML parsing | `beautifulsoup4` + `lxml` |
| HA framework | Home Assistant 2024.7.0+ |
| Packaging | `setuptools` + `setuptools_scm` |
| Formatting | `black` (line length 80, target py38) |
| Type checking | `mypy --strict` |
| Linting | `pylint` (unused-import checks only) |

## Device API

The MusicPal device exposes three HTTP endpoints:

| Endpoint | Purpose |
|----------|---------|
| `admin.cgi` | Main command endpoint (play, volume, favorites, …) |
| `state.cgi` | Device status / state polling |
| `ipc_send` | IPC command endpoint |

Default credentials: `admin` / `admin`.

## Key Conventions

- **Async HTTP**: The HA integration uses `httpx.AsyncClient` with the async context manager pattern (see `musicpal_api.py`).
- **Coordinator pattern**: `DataUpdateCoordinator` from HA is used for polling (`__init__.py`).
- **Code sections** are separated by equal-sign comment dividers (`# ===…`).
- **Type annotations**: All code uses strict mypy typing; annotate every function and variable.
- **No test suite** currently exists. Quality is enforced via pre-commit hooks.
- The CLI script is named `musicpal` (no `.py` extension) and is treated as a module by mypy (`--scripts-are-modules`).

## Custom HA Services

| Service | Description |
|---------|-------------|
| `musicpal.show_message` | Display a custom message on the device screen |
| `musicpal.show_list` | Display a list on the device screen |
| `musicpal.play_url` | Play a media URL directly |
| `musicpal.select_favorite` | Select a favorite by index |

## Development Commands

```bash
# Install dependencies
pip install -e ".[dev]"

# Run pre-commit hooks manually
pre-commit run --all-files

# Format with black
black musicpal custom_components/

# Type-check
mypy --strict --scripts-are-modules --disable-error-code=import-untyped musicpal custom_components/

# Lint
pylint --disable=all --enable=unused-import musicpal custom_components/
```

## Important Notes for Claude

- When adding new features to the HA integration, follow the existing `DataUpdateCoordinator` and entity patterns in `__init__.py`, `media_player.py`, and `sensor.py`.
- Always use `httpx.AsyncClient` (not `requests`) for HTTP calls in the HA integration.
- Keep code compliant with `black` (80-char lines) and fully typed for `mypy --strict`.
- New HA services must be declared in both `services.yaml` and registered in `__init__.py`.
- Translations belong in `translations/de.json` and `translations/en.json`; update both when adding new UI strings.
- The project targets Python 3.8+; avoid syntax or library features unavailable in that version.
