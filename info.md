# MusicPal Integration

Control your Freecom MusicPal internet radio from Home Assistant!

## Features

### Media Player
- Power on/off control (the MusicPal shows its clock screen while in standby)
- Play/pause and next track
- Volume control (0-100%)
- Select favorites as sources
- Play media URLs

### Sensors (diagnostic)
- **Display**: Shows what's currently on the MusicPal screen
- **Last boot**: Timestamp of the device's last start
- **Favorites**: Number of configured favorites, with their names as an attribute

### Services
- `musicpal.show_message`: Display custom messages
- `musicpal.show_clock`: Show the clock
- `musicpal.reboot`: Reboot the device

## Quick Setup

1. Make sure your MusicPal device is on your network
2. Add the integration from Settings → Devices & Services
3. Enter your device's IP address
4. Use default credentials (admin/admin) or your custom ones
5. Optionally adjust the polling interval under the integration's **Configure** button

## Example Usage

### Automation: Morning Radio
```yaml
automation:
  - alias: "Wake up with music"
    trigger:
      platform: time
      at: "07:00:00"
    action:
      - action: media_player.select_source
        target:
          entity_id: media_player.musicpal
        data:
          source: "BBC Radio"
```

### Show Notifications
```yaml
automation:
  - alias: "Doorbell Alert"
    trigger:
      platform: state
      entity_id: binary_sensor.doorbell
      to: "on"
    action:
      - action: musicpal.show_message
        target:
          entity_id: media_player.musicpal
        data:
          message: "Someone is at the door!"
```

## Requirements

- Home Assistant 2024.12.0 or newer
- Freecom MusicPal device
- Network connectivity to the device

## Support

For issues and feature requests, please visit the [GitHub repository](https://github.com/Revilo91/musicpal/issues).

---

*Based on the original musicpal CLI tool by Joerg Mechnich*
