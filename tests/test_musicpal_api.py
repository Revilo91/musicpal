"""Tests for the MusicPal HTTP API client."""

from __future__ import annotations

from datetime import timedelta

import httpx
import pytest

from custom_components.musicpal.musicpal_api import (
    _IPC_SAFE_CHARS,
    MusicPalAuthError,
    MusicPalClient,
    MusicPalConnectionError,
    MusicPalError,
    _build_soup,
    _build_soup_xml,
    _parse_favorites,
    _parse_info,
    _parse_now_playing,
    _parse_state,
    _parse_uptime,
    _parse_volume,
)

from .const import (
    FAVORITES_HTML,
    INFO_HTML,
    NOW_PLAYING_HTML,
    STATE_XML,
    UPTIME_HTML,
    VOLUME_HTML,
)


def test_parse_state() -> None:
    """The state document is flattened into a mapping."""
    assert _parse_state(_build_soup_xml(STATE_XML)) == {
        "display": "Radio Eins - Now playing",
        "volume": "12",
    }


def test_parse_favorites_uses_slot_index_not_row_position() -> None:
    """Favorites are keyed by their slot, and empty slots are skipped."""
    assert _parse_favorites(_build_soup(FAVORITES_HTML)) == [
        {"index": 0, "name": "Radio Eins"},
        {"index": 1, "name": "Deutschlandfunk"},
        {"index": 2, "name": "FM4"},
        {"index": 4, "name": "Jazz Radio"},
    ]


def test_parse_volume() -> None:
    """Lit volume bars are counted, minus the leading speaker icon."""
    assert _parse_volume(_build_soup(VOLUME_HTML)) == 2


def test_parse_volume_unknown_when_widget_missing() -> None:
    """A page without a volume widget yields None rather than 0."""
    assert _parse_volume(_build_soup(b"<html>error</html>")) is None


def test_parse_now_playing() -> None:
    """The now playing block is collapsed into one line."""
    assert (
        _parse_now_playing(_build_soup(NOW_PLAYING_HTML))
        == "Radio Eins Die Neue"
    )


def test_parse_uptime() -> None:
    """Uptime is read from the trailing seconds value."""
    assert _parse_uptime(_build_soup(UPTIME_HTML)) == timedelta(days=1)


def test_parse_uptime_garbage() -> None:
    """Unparsable uptime yields None instead of raising."""
    assert _parse_uptime(_build_soup(b"<html>oops</html>")) is None


def test_parse_info() -> None:
    """Labels on the info page become keys, and the MAC is recognised."""
    info = _parse_info(_build_soup(INFO_HTML))
    assert info["Firmware version"] == "1.62"
    assert info["MAC address"] == "00:1A:2B:3C:4D:5E"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Rock & Roll", "Rock%20%26%20Roll"),
        ("plain", "plain"),
        ("a#b", "a%23b"),
    ],
)
def test_ipc_argument_quoting(raw: str, expected: str) -> None:
    """Characters that would break the argument split are encoded."""
    from urllib.parse import quote

    assert quote(raw, safe=_IPC_SAFE_CHARS) == expected


async def test_client_requests_and_auth_errors() -> None:
    """Status codes map onto the client's exception hierarchy."""
    routes: dict[str, httpx.Response] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        return routes[request.url.path]

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = MusicPalClient("host", client=http_client)

        routes["/admin/cgi-bin/state.cgi"] = httpx.Response(
            200, content=STATE_XML
        )
        assert (await client.get_state())["volume"] == "12"

        routes["/admin/cgi-bin/state.cgi"] = httpx.Response(401)
        with pytest.raises(MusicPalAuthError):
            await client.get_state()

        routes["/admin/cgi-bin/state.cgi"] = httpx.Response(500)
        with pytest.raises(MusicPalError):
            await client.get_state()


async def test_client_connection_error() -> None:
    """Transport failures surface as MusicPalConnectionError."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = MusicPalClient("host", client=http_client)
        with pytest.raises(MusicPalConnectionError):
            await client.get_state()


async def test_ipc_send_builds_ampersand_separated_query() -> None:
    """ipc_send arguments are joined with & and encoded individually."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, content=b"")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = MusicPalClient("host", client=http_client)
        await client.show_message("Rock & Roll")

    assert seen == [
        "http://host/admin/cgi-bin/ipc_send?show_msg_box&Rock%20%26%20Roll"
    ]


async def test_client_requires_a_session() -> None:
    """Using the client without a session is a programming error."""
    with pytest.raises(RuntimeError):
        await MusicPalClient("host").get_state()
