"""Async API client for the Freecom MusicPal.

The device exposes a handful of CGI endpoints that return HTML (or a small
XML document for ``state.cgi``).  This module wraps those endpoints, turns
HTTP/parse failures into the exception hierarchy below and keeps all
BeautifulSoup work off the event loop.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import timedelta
from typing import Any
from urllib.parse import quote

import bs4
import httpx

from .const import (
    DEFAULT_PASSWORD,
    DEFAULT_USERNAME,
    REQUEST_TIMEOUT,
    VOLUME_MAX,
)

_LOGGER = logging.getLogger(__name__)

# Favorite slots are rendered as ``<input name="name_<index>" value="...">``.
_FAVORITE_NAME_RE = re.compile(r"^name_(\d+)$")
_MAC_RE = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")

# Characters left untouched when building ``ipc_send`` query strings.  The
# device splits the raw query string on "&", so "&", "#", "%" and spaces must
# be percent-encoded while URL punctuation has to survive verbatim.
_IPC_SAFE_CHARS = "!$'()*+,-./:;=?@_~"


# =============================================================================
# Exceptions
# =============================================================================


class MusicPalError(Exception):
    """Base class for all MusicPal API errors."""


class MusicPalConnectionError(MusicPalError):
    """The device could not be reached."""


class MusicPalAuthError(MusicPalError):
    """The device rejected the supplied credentials."""


# =============================================================================
# Blocking parse helpers (executed in an executor)
# =============================================================================


def _build_soup(content: bytes) -> bs4.BeautifulSoup:
    """Build a BeautifulSoup instance from HTML response bytes."""
    return bs4.BeautifulSoup(content, "lxml")


def _build_soup_xml(content: bytes) -> bs4.BeautifulSoup:
    """Build a BeautifulSoup instance from XML response bytes.

    ``state.cgi`` is the one endpoint that answers with XML; feeding it to
    the HTML parser works but emits an XMLParsedAsHTMLWarning on every poll.
    """
    return bs4.BeautifulSoup(content, "lxml-xml")


def _parse_state(soup: bs4.BeautifulSoup) -> dict[str, str]:
    """Extract the ``<state>`` document into a flat mapping."""
    state: dict[str, str] = {}
    if not soup.state:
        return state
    for state_tag in soup.state.children:
        if isinstance(state_tag, bs4.Tag) and state_tag.name:
            state[state_tag.name] = (state_tag.string or "").strip()
    return state


def _parse_volume(soup: bs4.BeautifulSoup) -> int | None:
    """Count the lit volume bars on the "now playing" frame.

    Returns ``None`` when the page did not contain a volume widget at all,
    so callers can distinguish "muted" from "unknown".
    """
    count = len(soup.find_all("img", src="/images/volume_on.gif"))
    if count == 0:
        return None
    return max(0, min(VOLUME_MAX, count - 1))


def _parse_favorites(soup: bs4.BeautifulSoup) -> list[dict[str, Any]]:
    """Extract configured favorites, keyed by their real slot index.

    The favorites page alternates row CSS classes, so the row position is
    *not* the favorite index.  The index is read from the input name instead.
    Empty slots are skipped.
    """
    favorites: list[dict[str, Any]] = []
    for tag in soup.find_all("input"):
        if not isinstance(tag, bs4.Tag):
            continue
        name = tag.get("name")
        if not isinstance(name, str):
            continue
        match = _FAVORITE_NAME_RE.match(name)
        if match is None:
            continue
        value = tag.get("value")
        label = value.strip() if isinstance(value, str) else ""
        if not label:
            continue
        favorites.append({"index": int(match.group(1)), "name": label})

    favorites.sort(key=lambda fav: int(fav["index"]))
    return favorites


def _parse_now_playing(soup: bs4.BeautifulSoup) -> str:
    """Extract the "now playing" text block."""
    content = soup.find(class_="content_content")
    if isinstance(content, bs4.Tag):
        return " ".join(content.stripped_strings)
    return ""


def _parse_uptime(soup: bs4.BeautifulSoup) -> timedelta | None:
    """Parse the uptime endpoint, which returns ``"<label> <seconds>"``."""
    text = soup.get_text(" ", strip=True)
    for part in reversed(text.split()):
        try:
            return timedelta(seconds=float(part))
        except ValueError:
            continue
    return None


def _parse_info(soup: bs4.BeautifulSoup) -> dict[str, str]:
    """Parse the device info page into a ``label -> value`` mapping.

    The page renders labels as ``<b>`` elements followed by loose text and
    ``<span>`` values.  Anything that does not fit that shape is ignored.
    """
    info: dict[str, str] = {}
    content = soup.find(class_="content_content")
    if not isinstance(content, bs4.Tag):
        return info

    label: str | None = None
    values: list[str] = []

    def _flush() -> None:
        if label and values:
            info.setdefault(label, " ".join(values))

    for element in content.children:
        if isinstance(element, bs4.element.Comment):
            continue
        if isinstance(element, bs4.Tag) and element.name == "b":
            _flush()
            label = element.get_text(strip=True).rstrip(":")
            values = []
            continue
        text = (
            element.get_text(" ", strip=True)
            if isinstance(element, bs4.Tag)
            else str(element).strip()
        )
        if text:
            values.append(text)
    _flush()

    if "mac" not in {key.lower() for key in info}:
        mac_match = _MAC_RE.search(soup.get_text(" ", strip=True))
        if mac_match:
            info["MAC"] = mac_match.group(0).replace("-", ":").lower()

    return info


# =============================================================================
# Client
# =============================================================================


class MusicPalClient:
    """Client to interact with a MusicPal device."""

    def __init__(
        self,
        hostname: str,
        username: str = DEFAULT_USERNAME,
        password: str = DEFAULT_PASSWORD,
        timeout: float = REQUEST_TIMEOUT,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialize the MusicPal client.

        Args:
            hostname: IP address or hostname of the MusicPal device.
            username: Username for HTTP authentication.
            password: Password for HTTP authentication.
            timeout: Per-request timeout in seconds.
            client: Externally managed ``httpx.AsyncClient`` to reuse (e.g.
                Home Assistant's shared client).  When omitted the client
                creates and owns its own session via ``async with``.
        """
        self.hostname = hostname
        self.username = username
        self.password = password
        self.timeout = timeout
        self._client = client
        self._owns_client = client is None

    # --- lifecycle --------------------------------------------------------

    async def __aenter__(self) -> MusicPalClient:
        """Async context manager entry."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
            self._owns_client = True
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """Async context manager exit."""
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    # --- low level --------------------------------------------------------

    @property
    def _auth(self) -> tuple[str, str]:
        return (self.username, self.password)

    async def _fetch(
        self,
        url: str,
        *,
        method: str = "GET",
        params: dict[str, Any] | None = None,
    ) -> bytes:
        """Perform a request and return the response body.

        Raises:
            MusicPalAuthError: The device rejected the credentials.
            MusicPalConnectionError: The device was unreachable or timed out.
            MusicPalError: The device answered with an unexpected status.
        """
        if self._client is None:
            raise RuntimeError(
                "Client not initialized. Use 'async with MusicPalClient(...)' "
                "or pass an existing httpx.AsyncClient."
            )

        _LOGGER.debug("MusicPal request: %s %s params=%s", method, url, params)
        try:
            response = await self._client.request(
                method=method,
                url=url,
                params=params,
                auth=self._auth,
                timeout=self.timeout,
            )
        except httpx.TimeoutException as err:
            raise MusicPalConnectionError(
                f"Timeout communicating with {self.hostname}"
            ) from err
        except httpx.HTTPError as err:
            raise MusicPalConnectionError(
                f"Error communicating with {self.hostname}: {err}"
            ) from err

        if response.status_code in (401, 403):
            raise MusicPalAuthError(
                f"Authentication rejected by {self.hostname}"
            )
        if response.status_code >= 400:
            raise MusicPalError(
                f"{self.hostname} returned HTTP {response.status_code} "
                f"for {response.url}"
            )
        return response.content

    async def _soup(self, content: bytes) -> bs4.BeautifulSoup:
        """Parse HTML in a thread to avoid blocking the event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _build_soup, content)

    async def _soup_xml(self, content: bytes) -> bs4.BeautifulSoup:
        """Parse XML in a thread to avoid blocking the event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _build_soup_xml, content)

    # --- endpoints --------------------------------------------------------

    async def admin_cgi(
        self,
        function: str,
        extra_params: dict[str, Any] | None = None,
        method: str = "GET",
    ) -> bytes:
        """Call the ``admin.cgi`` endpoint and return the response body."""
        params: dict[str, Any] = {"f": function}
        if extra_params:
            params.update(extra_params)
        url = f"http://{self.hostname}/admin/cgi-bin/admin.cgi"
        return await self._fetch(url, method=method, params=params)

    async def debug_cgi(
        self,
        function: str,
        extra_params: dict[str, Any] | None = None,
    ) -> bytes:
        """Call the ``debug.cgi`` endpoint and return the response body."""
        params: dict[str, Any] = {"f": function}
        if extra_params:
            params.update(extra_params)
        url = f"http://{self.hostname}/admin/cgi-bin/debug.cgi"
        return await self._fetch(url, params=params)

    async def ipc_send(self, command: str, *args: str) -> bytes:
        """Call the ``ipc_send`` endpoint.

        ``ipc_send`` expects bare, ampersand separated arguments rather than
        key/value pairs, so the query string is assembled by hand.  Each
        argument is percent-encoded just enough that embedded "&", "#" or
        whitespace cannot break the argument split.
        """
        encoded = [
            quote(str(arg), safe=_IPC_SAFE_CHARS) for arg in (command, *args)
        ]
        url = f"http://{self.hostname}/admin/cgi-bin/ipc_send?" + "&".join(
            encoded
        )
        return await self._fetch(url)

    async def state_cgi(self) -> bytes:
        """Call the ``state.cgi`` endpoint and return the response body."""
        url = f"http://{self.hostname}/admin/cgi-bin/state.cgi"
        return await self._fetch(url, params={"fav": 0})

    # --- high level -------------------------------------------------------

    async def get_state(self) -> dict[str, str]:
        """Return the device state document as a flat mapping."""
        soup = await self._soup_xml(await self.state_cgi())
        return _parse_state(soup)

    async def get_volume(self) -> int | None:
        """Return the current volume step (0..VOLUME_MAX), or None."""
        content = await self.admin_cgi(
            "volume_set",
            extra_params={"n": "../now_playing_frame.html", "v": -1},
        )
        return _parse_volume(await self._soup(content))

    async def set_volume(self, volume: int) -> None:
        """Set the volume step (clamped to 0..VOLUME_MAX)."""
        volume = max(0, min(VOLUME_MAX, volume))
        await self.admin_cgi(
            "volume_set",
            extra_params={"n": "../now_playing_frame.html", "v": volume},
        )

    async def volume_up(self) -> None:
        """Increase the volume by one step."""
        await self.admin_cgi("volume_inc")

    async def volume_down(self) -> None:
        """Decrease the volume by one step."""
        await self.admin_cgi("volume_dec")

    async def play_pause(self) -> None:
        """Toggle play/pause."""
        await self.admin_cgi("play_pause")

    async def next_track(self) -> None:
        """Skip to the next track."""
        await self.admin_cgi("next_song")

    async def play_url(self, url: str) -> None:
        """Play a media URL."""
        await self.ipc_send("play", url)

    async def power_on(self) -> None:
        """Wake the device from standby."""
        await self.ipc_send("power_up")

    async def power_off(self) -> None:
        """Send the device to standby."""
        await self.ipc_send("power_down")

    async def show_clock(self) -> None:
        """Display the clock screen."""
        await self.admin_cgi("show_clock", method="POST")

    async def show_message(self, message: str) -> None:
        """Show a message box on the display."""
        await self.ipc_send("show_msg_box", message)

    async def show_list(self, *items: str) -> None:
        """Show a list on the display."""
        await self.ipc_send("show_list", *items)

    async def get_favorites(self) -> list[dict[str, Any]]:
        """Return the configured favorites as ``{"index", "name"}`` dicts."""
        content = await self.admin_cgi(
            "favorites",
            extra_params={"n": "../favorites.html"},
        )
        return _parse_favorites(await self._soup(content))

    async def play_favorite(self, index: int) -> None:
        """Play the favorite stored in *index*."""
        await self.admin_cgi(
            "favorites",
            extra_params={
                "n": "../favorites.html",
                "a": "p",
                "i": str(index),
            },
        )

    async def get_now_playing(self) -> str:
        """Return the "now playing" text shown by the device."""
        content = await self.admin_cgi(
            "now_playing_frame",
            extra_params={"n": "../now_playing_frame.html"},
        )
        return _parse_now_playing(await self._soup(content))

    async def get_uptime(self) -> timedelta | None:
        """Return the device uptime, or None when it cannot be parsed."""
        content = await self.admin_cgi(
            "uptime",
            extra_params={"n": "../empty.html"},
            method="POST",
        )
        return _parse_uptime(await self._soup(content))

    async def get_info(self) -> dict[str, str]:
        """Return the device info page as a ``label -> value`` mapping."""
        content = await self.admin_cgi(
            "info",
            extra_params={"n": "../info.html"},
        )
        return _parse_info(await self._soup(content))

    async def reboot(self) -> None:
        """Reboot the device."""
        await self.debug_cgi("reboot")

    async def restart_nashville(self) -> None:
        """Restart the Nashville firmware service."""
        await self.debug_cgi("restart")
