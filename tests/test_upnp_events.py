"""Tests for the MusicPal UPnP event helpers."""

from __future__ import annotations

from custom_components.musicpal.upnp_events import (
    AVT_SERVICE_TYPE,
    RC_SERVICE_TYPE,
    parse_upnp_description,
    parse_upnp_notify_body,
)

from .const import AVT_NOTIFY, DESCRIPTION_XML, RCS_NOTIFY


def test_avtransport_notify_unwraps_last_change() -> None:
    """AVTransport variables live inside the nested LastChange document."""
    state = parse_upnp_notify_body(AVT_NOTIFY)
    assert state["TransportState"] == "PLAYING"
    assert state["AVTransportURI"] == "http://stream.example/radio.mp3"
    # The wrapper itself must not leak through as a state variable.
    assert "LastChange" not in state


def test_renderingcontrol_notify_keeps_master_channel_only() -> None:
    """Per-channel variables are reduced to the Master channel."""
    assert parse_upnp_notify_body(RCS_NOTIFY) == {"Volume": "9", "Mute": "1"}


def test_notify_body_garbage_is_ignored() -> None:
    """Malformed XML yields an empty mapping instead of raising."""
    assert parse_upnp_notify_body(b"<not xml") == {}


def test_parse_description_resolves_event_urls() -> None:
    """Relative and absolute eventSubURLs both resolve against the base."""
    services = parse_upnp_description(DESCRIPTION_XML, "http://10.0.0.5:1400")
    assert services[AVT_SERVICE_TYPE] == (
        "http://10.0.0.5:1400/AVTransport/evt"
    )
    assert services[RC_SERVICE_TYPE] == (
        "http://10.0.0.5:1400/RenderingControl/evt"
    )


def test_parse_description_garbage_is_ignored() -> None:
    """A non-XML description yields no services."""
    assert parse_upnp_description(b"nope", "http://host") == {}


def test_pause_on_device_is_reported_via_upnp() -> None:
    """Pausing on the device itself arrives as PAUSED_PLAYBACK."""
    body = (
        b'<?xml version="1.0"?>'
        b'<e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0">'
        b"<e:property><LastChange>"
        b'&lt;Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/"&gt;'
        b'&lt;InstanceID val="0"&gt;'
        b'&lt;TransportState val="PAUSED_PLAYBACK"/&gt;'
        b"&lt;/InstanceID&gt;&lt;/Event&gt;"
        b"</LastChange></e:property></e:propertyset>"
    )
    assert parse_upnp_notify_body(body)["TransportState"] == "PAUSED_PLAYBACK"


def test_last_change_ignores_other_instances() -> None:
    """Only InstanceID 0 is considered."""
    body = (
        b'<?xml version="1.0"?>'
        b'<e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0">'
        b"<e:property><LastChange>"
        b'&lt;Event xmlns="urn:schemas-upnp-org:metadata-1-0/AVT/"&gt;'
        b'&lt;InstanceID val="1"&gt;'
        b'&lt;TransportState val="STOPPED"/&gt;'
        b"&lt;/InstanceID&gt;&lt;/Event&gt;"
        b"</LastChange></e:property></e:propertyset>"
    )
    assert parse_upnp_notify_body(body) == {}
