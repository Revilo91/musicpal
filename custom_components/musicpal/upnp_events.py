"""UPnP event subscription helpers for MusicPal."""

from __future__ import annotations

import logging
from urllib.parse import urljoin
from xml.etree import ElementTree

import httpx

_LOGGER = logging.getLogger(__name__)

# UPnP service type identifiers (DLNA DMR)
AVT_SERVICE_TYPE = "urn:schemas-upnp-org:service:AVTransport:1"
RC_SERVICE_TYPE = "urn:schemas-upnp-org:service:RenderingControl:1"

# Subscription timeout in seconds (30 minutes)
UPNP_SUBSCRIPTION_TIMEOUT = 1800

# Candidate (port, path) pairs to probe for device description.
# Nashville firmware on the Freecom MusicPal typically exposes UPnP
# on port 1400; fall back to common DLNA / HTTP ports as well.
UPNP_DESCRIPTION_CANDIDATES = [
    (1400, "/description.xml"),
    (49152, "/description.xml"),
    (80, "/description.xml"),
]


def parse_upnp_notify_body(body: bytes) -> dict[str, str]:
    """Parse a UPnP NOTIFY body and return its state variables.

    The body is a ``<e:propertyset>`` XML document.  Each child
    ``<e:property>`` contains one or more variable name/value elements.

    Args:
        body: Raw XML bytes from the NOTIFY request body.

    Returns:
        Mapping of UPnP variable name to its string value.
    """
    result: dict[str, str] = {}
    try:
        root = ElementTree.fromstring(body)
        ns = {"e": "urn:schemas-upnp-org:event-1-0"}
        for prop in root.findall("e:property", ns):
            for var in prop:
                tag = var.tag
                # Strip XML namespace URI if present.
                if "}" in tag:
                    tag = tag.split("}", 1)[1]
                if var.text is not None:
                    result[tag] = var.text
    except ElementTree.ParseError as err:
        _LOGGER.debug("Failed to parse UPnP NOTIFY body: %s", err)
    return result


def parse_upnp_description(xml_content: bytes, base_url: str) -> dict[str, str]:
    """Parse a UPnP device description XML document.

    Args:
        xml_content: Raw XML bytes of the device description.
        base_url: Base URL (scheme + host + port) used to resolve
            relative ``eventSubURL`` paths, e.g.
            ``"http://192.168.1.10:1400"``.

    Returns:
        Mapping of UPnP service type URN to absolute event sub URL.
    """
    services: dict[str, str] = {}
    try:
        root = ElementTree.fromstring(xml_content)
        upnp_ns = "urn:schemas-upnp-org:device-1-0"
        for svc in root.iter(f"{{{upnp_ns}}}service"):
            stype_el = svc.find(f"{{{upnp_ns}}}serviceType")
            event_url_el = svc.find(f"{{{upnp_ns}}}eventSubURL")
            if stype_el is None or event_url_el is None:
                continue
            stype = (stype_el.text or "").strip()
            event_url = (event_url_el.text or "").strip()
            if stype and event_url:
                services[stype] = urljoin(
                    base_url.rstrip("/") + "/",
                    event_url.lstrip("/"),
                )
    except ElementTree.ParseError as err:
        _LOGGER.debug("Failed to parse UPnP description: %s", err)
    return services


async def discover_upnp_services(
    hostname: str,
    http_timeout: float = 5.0,
) -> dict[str, str] | None:
    """Probe a MusicPal device for its UPnP service event URLs.

    Tries each candidate (port, path) pair from
    :data:`UPNP_DESCRIPTION_CANDIDATES` in order and returns the first
    successfully parsed service map.

    Args:
        hostname: IP address or hostname of the MusicPal device.
        http_timeout: Per-request HTTP timeout in seconds.

    Returns:
        Mapping of UPnP service type URN to absolute event sub URL,
        or ``None`` if no description was found.
    """
    async with httpx.AsyncClient(timeout=http_timeout) as client:
        for port, path in UPNP_DESCRIPTION_CANDIDATES:
            url = f"http://{hostname}:{port}{path}"
            try:
                response = await client.get(url)
                if response.status_code == 200 and response.content:
                    base_url = f"http://{hostname}:{port}"
                    services = parse_upnp_description(
                        response.content, base_url
                    )
                    if services:
                        _LOGGER.debug(
                            "Found UPnP description at %s, services: %s",
                            url,
                            list(services.keys()),
                        )
                        return services
            except httpx.HTTPError:
                continue
    _LOGGER.debug("No UPnP description found for %s", hostname)
    return None


async def upnp_subscribe(
    event_sub_url: str,
    callback_url: str,
    sid: str | None = None,
    timeout_seconds: int = UPNP_SUBSCRIPTION_TIMEOUT,
) -> str | None:
    """Subscribe or renew a UPnP event subscription.

    Sends a ``SUBSCRIBE`` request to *event_sub_url*.  When *sid* is
    ``None`` a new subscription is created; otherwise the existing
    subscription identified by *sid* is renewed.

    Args:
        event_sub_url: Device-side event subscription endpoint URL.
        callback_url: Local URL the device should send NOTIFY requests
            to (used for new subscriptions only).
        sid: Existing subscription ID to renew, or ``None``.
        timeout_seconds: Requested subscription lifetime.

    Returns:
        Subscription SID string on success, or ``None`` on failure.
    """
    headers: dict[str, str] = {
        "TIMEOUT": f"Second-{timeout_seconds}",
    }
    if sid:
        headers["SID"] = sid
    else:
        headers["NT"] = "upnp:event"
        headers["CALLBACK"] = f"<{callback_url}>"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.request(
                method="SUBSCRIBE",
                url=event_sub_url,
                headers=headers,
            )
            if response.status_code == 200:
                new_sid = response.headers.get("SID", "")
                _LOGGER.debug(
                    "UPnP subscribed to %s: SID=%s",
                    event_sub_url,
                    new_sid,
                )
                return new_sid or None
    except httpx.HTTPError as err:
        _LOGGER.debug("UPnP SUBSCRIBE to %s failed: %s", event_sub_url, err)
    return None


async def upnp_unsubscribe(event_sub_url: str, sid: str) -> None:
    """Cancel a UPnP event subscription.

    Args:
        event_sub_url: Device-side event subscription endpoint URL.
        sid: Subscription ID to cancel.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.request(
                method="UNSUBSCRIBE",
                url=event_sub_url,
                headers={"SID": sid},
            )
        _LOGGER.debug("UPnP unsubscribed from %s (SID: %s)", event_sub_url, sid)
    except httpx.HTTPError as err:
        _LOGGER.debug("UPnP UNSUBSCRIBE from %s failed: %s", event_sub_url, err)
