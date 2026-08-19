# MusicPal Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Custom Home Assistant integration for the Freecom MusicPal internet radio device.

## About

The Freecom MusicPal is an early hardware media player / internet radio that was released around 2007. This integration allows you to control your MusicPal device from Home Assistant.

## Features

- **Media Player Entity**: Full media player controls including play/pause, volume control, and favorite selection
- **Sensor Entities**:
  - Display content sensor
  - Uptime sensor
  - Favorites count sensor
- **Services**:
  - Show custom messages on the display
  - Show clock
  - Reboot device

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/Revilo91/musicpal`
6. Select category: "Integration"
7. Click "Add"
8. Find "MusicPal" in the integration list and click "Download"
9. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/musicpal` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to Settings → Devices & Services
2. Click "+ Add Integration"
3. Search for "MusicPal"
4. Enter your device details:
   - **Hostname or IP address**: The IP address or hostname of your MusicPal device
   - **Username**: Default is "admin"
   - **Password**: Default is "admin"
5. Click "Submit"

### Options

Press **Configure** on the integration card to change how often the device is
polled (5-300 seconds, default 30). The MusicPal is 2007 hardware, so lower
values make Home Assistant react faster at the cost of more load on the
device.

## Usage

### Media Player

The integration creates a media player entity for your MusicPal device with the following features:

- **Power Control**: Turn the device on/off
- **Playback Control**: Play, pause, next track
- **Volume Control**: Set volume level (0-100%) or use volume up/down
- **Source Selection**: Select from your configured favorites
- **Play Media**: Play a media URL directly

### Sensors

Three sensor entities are created:

1. **Display**: The text currently shown on the device screen
2. **Last boot**: When the device last started (a stable timestamp rather than
   an ever-increasing counter, so it does not fill up your recorder database)
3. **Favorites**: How many favorites are configured; the names are available as
   the `favorites` attribute

All three are marked as diagnostic entities.

### Services

#### `musicpal.show_message`

Display a custom message on the MusicPal screen.

```yaml
action: musicpal.show_message
target:
  entity_id: media_player.musicpal
data:
  message: "Hello from Home Assistant!"
```

#### `musicpal.show_clock`

Display the clock on the MusicPal screen.

```yaml
action: musicpal.show_clock
target:
  entity_id: media_player.musicpal
```

#### `musicpal.reboot`

Reboot the MusicPal device.

```yaml
action: musicpal.reboot
target:
  entity_id: media_player.musicpal
```

## Example Automations

### Play favorite at a specific time

```yaml
automation:
  - alias: "Morning Radio"
    trigger:
      - platform: time
        at: "07:00:00"
    action:
      - action: media_player.select_source
        target:
          entity_id: media_player.musicpal
        data:
          source: "Morning Radio"
```

### Show message on MusicPal display

```yaml
automation:
  - alias: "Doorbell notification"
    trigger:
      - platform: state
        entity_id: binary_sensor.doorbell
        to: "on"
    action:
      - action: musicpal.show_message
        target:
          entity_id: media_player.musicpal
        data:
          message: "Someone at the door!"
```

## Supported Commands

The integration supports all major MusicPal API commands:

- Power control (on/off)
- Playback control (play/pause, next)
- Volume control (set, up, down)
- Display control (show message, show clock)
- Favorites selection
- Device management (reboot)

## Requirements

- Home Assistant 2024.12.0 or newer
- A Freecom MusicPal device on your network

## Troubleshooting

### Cannot connect to device

- Ensure the MusicPal device is powered on and connected to your network
- Verify the IP address or hostname is correct
- Check that you can ping the device from your Home Assistant host
- Ensure the username and password are correct (default: admin/admin)

### Integration not appearing in HACS

- Make sure you've added this repository as a custom repository in HACS
- Try refreshing HACS
- Check that HACS is properly installed and configured

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the GNU General Public License v3 (GPLv3) - see the LICENSE file for details.

## Links

- [GitHub Repository](https://github.com/Revilo91/musicpal)
- [Home Assistant](https://www.home-assistant.io/)
- [HACS](https://hacs.xyz/)
- [MusicPal Information](https://musicpal.mcproductions.nl/)

## Credits

Based on the original `musicpal` CLI tool by Joerg Mechnich.
