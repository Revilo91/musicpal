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
├── tests/                            # pytest suite (pytest-homeassistant-custom-component)
└── custom_components/musicpal/
    ├── __init__.py                   # HA entry point, UPnP eventing, unload
    ├── config_flow.py                # UI config, reauth, reconfigure, options
    ├── const.py                      # Constants (domain, keys, intervals)
    ├── coordinator.py                # DataUpdateCoordinator + polled data model
    ├── entity.py                      # Base entity providing device_info
    ├── media_player.py               # MediaPlayer entity + entity services
    ├── sensor.py                     # Diagnostic sensors (display, boot, favorites)
    ├── musicpal_api.py               # Async httpx API client + exceptions
    ├── upnp_events.py                # UPnP SUBSCRIBE / NOTIFY helpers
    ├── diagnostics.py                # Config entry diagnostics
    ├── manifest.json                 # HA integration metadata
    ├── services.yaml                 # Custom service definitions
    ├── strings.json                  # UI strings (source for translations/en.json)
    └── translations/
        ├── de.json                   # German
        └── en.json                   # English
```

## Tech Stack

| Area | Technology |
|------|-----------|
| Language | Python 3.12+ (HA), 3.9+ (CLI) |
| HTTP client | `httpx` (async for HA, sync for CLI) |
| HTML parsing | `beautifulsoup4` + `lxml` |
| HA framework | Home Assistant 2024.12.0+ |
| Packaging | `setuptools` + `setuptools_scm` |
| Formatting | `ruff format` (line length 80) |
| Type checking | `mypy --strict` |
| Linting | `ruff check` (E, W, F, I, B, UP, SIM, C4, D) |
| Tests | `pytest` + `pytest-homeassistant-custom-component` |

## Device API

The MusicPal device exposes three HTTP endpoints:

| Endpoint | Purpose |
|----------|---------|
| `admin.cgi` | Main command endpoint (play, volume, favorites, …) |
| `state.cgi` | Device status / state polling |
| `ipc_send` | IPC command endpoint |

Default credentials: `admin` / `admin`.

## Key Conventions

- **Async HTTP**: The HA integration reuses Home Assistant's shared
  `httpx.AsyncClient` via `get_async_client(hass)`; `MusicPalClient` also
  supports the standalone `async with` pattern (see `musicpal_api.py`).
- **Coordinator pattern**: `MusicPalDataUpdateCoordinator` in `coordinator.py`
  polls the device and is stored on `entry.runtime_data` (not `hass.data`).
  Rarely changing data (favorites, uptime, info) is only refreshed every
  `SLOW_UPDATE_CYCLES` polls.
- **Errors**: `musicpal_api.py` raises `MusicPalError` /
  `MusicPalConnectionError` / `MusicPalAuthError`. Entity methods translate
  these into `HomeAssistantError`; the coordinator turns auth failures into
  `ConfigEntryAuthFailed` to trigger the reauth flow.
- **Code sections** are separated by equal-sign comment dividers (`# ===…`).
- **Type annotations**: All code uses strict mypy typing; annotate every function and variable.
- **Tests** live in `tests/` and use `pytest-homeassistant-custom-component`
  with a fully mocked device (no hardware needed).
- The CLI script is named `musicpal` (no `.py` extension) and is treated as a module by mypy (`--scripts-are-modules`).

## Custom HA Services

All three are **entity services** registered on the `media_player` platform,
so they are targeted with `target:` (or a plain `entity_id:`).

| Service | Description |
|---------|-------------|
| `musicpal.show_message` | Display a custom message on the device screen |
| `musicpal.show_clock` | Show the clock screen |
| `musicpal.reboot` | Reboot the device |

Playing a URL and selecting a favorite are covered by the standard
`media_player.play_media` and `media_player.select_source` services.

## Development Commands

```bash
# Install dependencies
pip install -e ".[dev]" --config-settings editable_mode=compat

# Run pre-commit hooks manually
pre-commit run --all-files

# Format
ruff format musicpal custom_components/ tests/

# Lint
ruff check musicpal custom_components/ tests/

# Type-check (config lives in pyproject.toml)
mypy --scripts-are-modules musicpal custom_components/

# Tests
pytest tests/
```

## Important Notes for Claude

- When adding new entities, subclass `MusicPalEntity` (`entity.py`) so they
  land on the shared device and get `has_entity_name` handling for free.
- Always use `httpx` (not `requests`) for HTTP calls in the HA integration.
- Keep code compliant with `ruff format` (80-char lines) and fully typed for
  `mypy --strict`.
- New entity services must be declared in `services.yaml`, described in
  `strings.json` plus both translation files, and registered via
  `platform.async_register_entity_service` in `media_player.py`.
- `strings.json` is the English source of truth; `translations/en.json` must
  stay identical to it.
- Translations belong in `translations/de.json` and `translations/en.json`; update both when adding new UI strings.
- The project targets Python 3.8+; avoid syntax or library features unavailable in that version.
