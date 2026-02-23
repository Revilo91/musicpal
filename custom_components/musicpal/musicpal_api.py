"""MusicPal API client for Home Assistant integration."""

from typing import Any, Optional
from datetime import timedelta

import httpx
import bs4


class MusicPalClient:
    """Client to interact with MusicPal device."""

    def __init__(
        self,
        hostname: str,
        username: str = "admin",
        password: str = "admin",
        timeout: float = 10.0,
    ):
        """Initialize the MusicPal client.

        Args:
            hostname: IP address or hostname of the MusicPal device
            username: Username for HTTP authentication
            password: Password for HTTP authentication
            timeout: Request timeout in seconds
        """
        self.hostname = hostname
        self.username = username
        self.password = password
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            auth=(self.username, self.password),
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    async def admin_cgi(
        self,
        function: str,
        extra_params: Optional[dict[str, Any]] = None,
        method: str = "GET",
    ) -> httpx.Response:
        """Call the admin.cgi API endpoint.

        Args:
            function: The function name to call
            extra_params: Additional parameters for the API call
            method: HTTP method (GET or POST)

        Returns:
            HTTP response object
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async with context.")

        params = {"f": function}
        if extra_params:
            params.update(extra_params)

        return await self._client.request(
            method=method,
            url=f"http://{self.hostname}/admin/cgi-bin/admin.cgi",
            params=params,
        )

    async def debug_cgi(
        self,
        function: str,
        extra_params: Optional[dict[str, Any]] = None,
    ) -> httpx.Response:
        """Call the debug.cgi API endpoint.

        Args:
            function: The function name to call
            extra_params: Additional parameters for the API call

        Returns:
            HTTP response object
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async with context.")

        params = {"f": function}
        if extra_params:
            params.update(extra_params)

        return await self._client.get(
            url=f"http://{self.hostname}/admin/cgi-bin/debug.cgi",
            params=params,
        )

    async def ipc_send(self, command: str, *args: str) -> httpx.Response:
        """Call the ipc_send API endpoint.

        Args:
            command: The command to send
            *args: Additional command arguments

        Returns:
            HTTP response object
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async with context.")

        url = (
            f"http://{self.hostname}/admin/cgi-bin/ipc_send?"
            + "&".join([command] + list(args))
        )
        return await self._client.get(url)

    async def state_cgi(self) -> httpx.Response:
        """Call the state.cgi API endpoint to get device state.

        Returns:
            HTTP response object
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async with context.")

        return await self._client.get(
            url=f"http://{self.hostname}/admin/cgi-bin/state.cgi",
            params={"fav": 0},
        )

    async def get_state(self) -> dict[str, Any]:
        """Get the current state of the device.

        Returns:
            Dictionary with device state information
        """
        response = await self.state_cgi()
        response.raise_for_status()

        soup = bs4.BeautifulSoup(response.content, "lxml")
        state = {}

        if soup.state:
            for state_tag in soup.state.children:
                if isinstance(state_tag, bs4.Tag) and state_tag.name:
                    state[state_tag.name] = state_tag.string

        return state

    async def get_volume(self) -> int:
        """Get the current volume level.

        Returns:
            Volume level (0-20)
        """
        response = await self.admin_cgi(
            "volume_set",
            extra_params={"n": "../now_playing_frame.html", "v": -1},
        )
        response.raise_for_status()

        soup = bs4.BeautifulSoup(response.content, "lxml")
        volume = len(soup.find_all("img", src="/images/volume_on.gif")) - 1
        return max(0, volume)

    async def set_volume(self, volume: int) -> None:
        """Set the volume level.

        Args:
            volume: Volume level (0-20)
        """
        volume = max(0, min(20, volume))
        response = await self.admin_cgi(
            "volume_set",
            extra_params={"n": "../now_playing_frame.html", "v": volume},
        )
        response.raise_for_status()

    async def volume_up(self) -> None:
        """Increase volume."""
        response = await self.admin_cgi("volume_inc")
        response.raise_for_status()

    async def volume_down(self) -> None:
        """Decrease volume."""
        response = await self.admin_cgi("volume_dec")
        response.raise_for_status()

    async def play_pause(self) -> None:
        """Toggle play/pause."""
        response = await self.admin_cgi("play_pause")
        response.raise_for_status()

    async def next_track(self) -> None:
        """Skip to next track."""
        response = await self.admin_cgi("next_song")
        response.raise_for_status()

    async def play_url(self, url: str) -> None:
        """Play a media URL.

        Args:
            url: URL of the media to play
        """
        response = await self.ipc_send("play", url)
        response.raise_for_status()

    async def power_on(self) -> None:
        """Power on the device."""
        response = await self.ipc_send("power_up")
        response.raise_for_status()

    async def power_off(self) -> None:
        """Power off the device."""
        response = await self.ipc_send("power_down")
        response.raise_for_status()

    async def show_clock(self) -> None:
        """Display the clock."""
        response = await self.admin_cgi("show_clock", method="POST")
        response.raise_for_status()

    async def show_message(self, message: str) -> None:
        """Show a message on the display.

        Args:
            message: Message text to display
        """
        response = await self.ipc_send("show_msg_box", message)
        response.raise_for_status()

    async def get_favorites(self) -> list[dict[str, Any]]:
        """Get list of favorites.

        Returns:
            List of favorites with index and name
        """
        response = await self.admin_cgi(
            "favorites",
            extra_params={"n": "../favorites.html"},
        )
        response.raise_for_status()

        soup = bs4.BeautifulSoup(response.content, "lxml")
        favorites = []

        for i, fav_tag in enumerate(soup.find_all(class_="table_alt1")):
            if not isinstance(fav_tag, bs4.Tag):
                continue
            name = fav_tag.find(attrs={"name": f"name_{i}"})
            if name and isinstance(name, bs4.Tag):
                favorites.append({"index": i, "name": name.get("value", "")})

        return favorites

    async def play_favorite(self, index: int) -> None:
        """Play a favorite by index.

        Args:
            index: Index of the favorite to play
        """
        response = await self.admin_cgi(
            "favorites",
            extra_params={
                "n": "../favorites.html",
                "a": "p",
                "i": str(index),
            },
        )
        response.raise_for_status()

    async def get_now_playing(self) -> str:
        """Get currently playing track information.

        Returns:
            String with now playing information
        """
        response = await self.admin_cgi(
            "now_playing_frame",
            extra_params={"n": "../now_playing_frame.html"},
        )
        response.raise_for_status()

        soup = bs4.BeautifulSoup(response.content, "lxml")
        content = soup.find(class_="content_content")
        if content:
            return " ".join(content.stripped_strings)
        return ""

    async def get_uptime(self) -> timedelta:
        """Get device uptime.

        Returns:
            Uptime as timedelta
        """
        response = await self.admin_cgi(
            "uptime",
            extra_params={"n": "../empty.html"},
            method="POST",
        )
        response.raise_for_status()

        soup = bs4.BeautifulSoup(response.content, "lxml")
        text = (soup.string if soup.string else "").strip()
        if text:
            parts = text.split()
            if len(parts) >= 2:
                seconds = float(parts[1])
                return timedelta(seconds=seconds)
        return timedelta()

    async def reboot(self) -> None:
        """Reboot the device."""
        response = await self.debug_cgi("reboot")
        response.raise_for_status()

    async def restart_nashville(self) -> None:
        """Restart the Nashville service."""
        response = await self.debug_cgi("restart")
        response.raise_for_status()
