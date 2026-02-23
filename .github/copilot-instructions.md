# GitHub Copilot Instructions

This file provides project-specific context so GitHub Copilot can give accurate, idiomatic suggestions for the **musicpal** repository.

## Project Overview

**musicpal** is a Python project that provides a control interface for the _Freecom MusicPal_ hardware media player / internet radio (released ~2007). It is shipped in two forms:

1. **CLI tool** (`musicpal` script) – argparse-based command-line client.
2. **Home Assistant custom integration** (`custom_components/musicpal/`) – HACS-compatible integration for Home Assistant.

## Repository Layout

```
musicpal/
├── musicpal                          # CLI script (no .py extension)
├── setup.py                          # Package metadata & dependencies
├── pyproject.toml                    # Build system (setuptools), Black config
├── .pre-commit-config.yaml           # black / pylint / mypy hooks
├── hacs.json                         # HACS metadata
└── custom_components/musicpal/
    ├── __init__.py                   # HA setup, DataUpdateCoordinator, services
    ├── config_flow.py                # UI config flow
    ├── const.py                      # Constants
    ├── media_player.py               # MediaPlayer entity
    ├── sensor.py                     # Sensor entities
    ├── musicpal_api.py               # Async httpx API client
    ├── manifest.json                 # HA integration manifest
    ├── services.yaml                 # Service definitions
    ├── strings.json                  # UI strings
    └── translations/                 # de.json, en.json
```

## Tech Stack & Dependencies

- **Language**: Python 3.8+
- **HTTP**: `httpx` — use `httpx.AsyncClient` in the HA integration; `httpx.Client` in the CLI.
- **HTML parsing**: `beautifulsoup4` + `lxml`
- **HA framework**: Home Assistant 2024.7.0+, `DataUpdateCoordinator` pattern
- **Formatting**: `black` — line length **80**, target Python 3.8
- **Type checking**: `mypy --strict` — all code must be fully typed
- **Linting**: `pylint` (only unused-import checks are enabled)

## Coding Conventions

### General
- All functions and variables must have type annotations (`mypy --strict`).
- Format with `black` at 80 characters per line targeting Python 3.8.
- Use equal-sign comment dividers (`# ===…`) to separate major code sections.
- The CLI script `musicpal` has no `.py` extension; mypy treats it as a module via `--scripts-are-modules`.

### Home Assistant Integration
- Follow the `DataUpdateCoordinator` pattern already established in `__init__.py`.
- Use `httpx.AsyncClient` (async context manager) for all HTTP calls inside the integration.
- Register new services in **both** `services.yaml` and `__init__.py`.
- Add UI strings to **both** `translations/de.json` and `translations/en.json` when updating `strings.json`.
- Platforms: `media_player`, `sensor`, `button` — follow the existing entity base classes.

### Custom Services

| Service | Description |
|---------|-------------|
| `musicpal.show_message` | Show a message on the device display |
| `musicpal.show_list` | Show a list on the device display |
| `musicpal.play_url` | Play a media URL |
| `musicpal.select_favorite` | Select a favorite by index |

## Device API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `admin.cgi` | Main command endpoint |
| `state.cgi` | Device state / status polling |
| `ipc_send` | IPC command endpoint |

Default credentials: `admin` / `admin`.

## What to Avoid

- **Do not use `requests`** — the project uses `httpx` throughout.
- **Do not drop type annotations** — all code must pass `mypy --strict`.
- **Do not exceed 80 characters per line** — enforced by `black`.
- **Do not target Python versions above 3.8** in syntax or library usage without updating `pyproject.toml`.
- **Do not add new HA services** without updating both `services.yaml` and `__init__.py`.
