"""Sample device responses used by the MusicPal tests."""

from __future__ import annotations

STATE_XML = b"""<?xml version="1.0"?>
<state>
  <display>Radio Eins - Now playing</display>
  <volume>12</volume>
</state>"""

STATE_CLOCK_XML = b"""<?xml version="1.0"?>
<state>
  <display>Clock</display>
</state>"""

# Favorite rows alternate their CSS class, and slot 3 is unused.  The row
# position is deliberately not the favorite index.
FAVORITES_HTML = b"""<html><body><table>
<tr class="table_alt1"><td><input type="text" name="name_0" value="Radio Eins"></td></tr>
<tr class="table_alt2"><td><input type="text" name="name_1" value="Deutschlandfunk"></td></tr>
<tr class="table_alt1"><td><input type="text" name="name_2" value="FM4"></td></tr>
<tr class="table_alt2"><td><input type="text" name="name_3" value=""></td></tr>
<tr class="table_alt1"><td><input type="text" name="name_4" value="Jazz Radio"></td></tr>
<tr><td><input type="submit" name="save" value="Save"></td></tr>
</table></body></html>"""

VOLUME_HTML = b"""<html><body>
<img src="/images/volume_on.gif"><img src="/images/volume_on.gif">
<img src="/images/volume_on.gif"><img src="/images/volume_off.gif">
</body></html>"""

NOW_PLAYING_HTML = b"""<html><body>
<div class="content_content">Radio Eins <span>Die Neue</span></div>
</body></html>"""

UPTIME_HTML = b"uptime 86400.0"

INFO_HTML = b"""<html><body><div class="content_content">
<b>Firmware version:</b>1.62<br>
<b>MAC address:</b><span>00:1A:2B:3C:4D:5E</span>
</div></body></html>"""

AVT_NOTIFY = (
    b'<?xml version="1.0"?>'
    b'<e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0">'
    b"<e:property><LastChange>"
    b'&lt;Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/"&gt;'
    b'&lt;InstanceID val="0"&gt;'
    b'&lt;TransportState val="PLAYING"/&gt;'
    b'&lt;AVTransportURI val="http://stream.example/radio.mp3"/&gt;'
    b"&lt;/InstanceID&gt;&lt;/Event&gt;"
    b"</LastChange></e:property></e:propertyset>"
)

RCS_NOTIFY = (
    b'<?xml version="1.0"?>'
    b'<e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0">'
    b"<e:property><LastChange>"
    b'&lt;Event xmlns="urn:schemas-upnp-org:metadata-1-0/RCS/"&gt;'
    b'&lt;InstanceID val="0"&gt;'
    b'&lt;Volume channel="Master" val="9"/&gt;'
    b'&lt;Volume channel="LF" val="99"/&gt;'
    b'&lt;Mute channel="Master" val="1"/&gt;'
    b"&lt;/InstanceID&gt;&lt;/Event&gt;"
    b"</LastChange></e:property></e:propertyset>"
)

DESCRIPTION_XML = b"""<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0"><device><serviceList>
<service>
  <serviceType>urn:schemas-upnp-org:service:AVTransport:1</serviceType>
  <eventSubURL>/AVTransport/evt</eventSubURL>
</service>
<service>
  <serviceType>urn:schemas-upnp-org:service:RenderingControl:1</serviceType>
  <eventSubURL>RenderingControl/evt</eventSubURL>
</service>
</serviceList></device></root>"""
