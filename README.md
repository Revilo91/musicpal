[![PyPI versio](https://img.shields.io/pypi/v/musicpal)](https://pypi.org/project/musicpal/)
[![PyPi format](https://img.shields.io/pypi/format/musicpal)](https://pypi.org/project/musicpal/)
[![PyPI license](https://img.shields.io/pypi/l/musicpal)](https://pypi.org/project/musicpal/)
[![PyPi weekly downloads](https://img.shields.io/pypi/dw/musicpal)](https://pypi.org/project/musicpal/)

## musicpal

Command line interface and Home Assistant integration for remote controlling a _Freecom MusicPal_ media player.

The Freecom MusicPal is one of the early hardware media players /
internet radios that was released around 2007.

At a price of 100-150 Euros, it was quite cheap and also hackable as
it is running a Linux-based OS with easy debugging access and a
published development toolchain.

The last stable firmware version 1.67 sports a 2.6.16 Linux
kernel. All services are offered by a single application called
_Nashville_ which, unfortunately, is closed source.

### Usage

```
usage: musicpal [--help] [-h HOSTNAME] [-u USERNAME] [-p PASSWORD] [-d] [-l]
                [command] [args ...]

Command line client for the Freecom MusicPal.

positional arguments:
  command               command for sending to the MusicPal device (default: state)
  args                  (optional) arguments for given command

optional arguments:
  --help                show this help message and exit
  -h HOSTNAME, --hostname HOSTNAME
                        IP or hostname of the MusicPal device (default: musicpal)
  -u USERNAME, --username USERNAME
                        username for HTTP authorization (default: admin)
  -p PASSWORD, --password PASSWORD
                        password for HTTP authorization (default: admin)
  -d, --debug           print additional output for debugging
  -l, --list            print list available API commands and exit
```

Available commands are:

| Command        | Description | Arguments |
| ---------------|-------------| ----------|
|`menu_collapse` | close menu on display | None |
|`play`          | play media file | HTTP URL |
|`power_down`    | suspend device | None |
|`power_up`      | wake-up device | None |
|`show_list`     | display a list | list items to be shown|
|`show_msg_box`  | display a message box | text to be shown |
|`favorites`     | list or select favorites | None or favorite index (starting from 0) |
|`info`          | retrieve network information | None |
|`next_song`     | skip to next favorite / playlist item | None |
|`now_playing`   | print currently playing track | None |
|`play_pause`    | toggle playback | None |
|`show_clock`    | display clock | None |
|`volume_dec`    | turn volume down | None |
|`volume_inc`    | turn volume up | None |
|`volume_set`    | print or set current volume | None or value between 0 and 20 |
|`reboot`        | reboot device | None |
|`restart`       | restart Nashville | None |
|`state`         | display various information about device state | None |

### Home Assistant Integration

This repository includes a HACS-compatible Home Assistant custom integration for the Freecom MusicPal.

#### Installation via HACS

1. Make sure you have [HACS](https://hacs.xyz/) installed in your Home Assistant instance
2. Add this repository as a custom repository in HACS:
   - Go to HACS → Integrations
   - Click the three dots in the top right corner
   - Select "Custom repositories"
   - Add `https://github.com/Revilo91/musicpal` as an Integration
3. Click "Download" to install the integration
4. Restart Home Assistant
5. Go to Settings → Devices & Services → Add Integration
6. Search for "MusicPal" and follow the configuration steps

#### Manual Installation

1. Copy the `custom_components/musicpal` directory to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration
4. Search for "MusicPal" and follow the configuration steps

#### Configuration

During setup, you will need to provide:
- **IP Address or Hostname**: The network address of your MusicPal device
- **Username**: Admin username (default: `admin`)
- **Password**: Admin password (default: `admin`)

#### Features

The integration provides a media player entity with support for:
- Power on/off
- Play/Pause control
- Next track
- Volume control (0-20 levels)
- State monitoring (playing, paused, idle)
- Media information (title, artist)

Additional entities provided:

**Sensors:**
- Volume sensor
- Source sensor
- Title sensor
- Artist sensor
- Album sensor
- State sensor
- Uptime sensor

**Buttons:**
- Reboot device
- Restart Nashville service
- Show clock on display
- Close menu on display

### Links

  * https://musicpal.mcproductions.nl/ - various information about the device
