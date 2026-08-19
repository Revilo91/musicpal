"""UPnP event subscription helpers for MusicPal.

Only the small subset of UPnP eventing that this integration needs is
implemented here: discovering the device description, SUBSCRIBE/UNSUBSCRIBE
and decoding NOTIFY bodies.
"""

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

# Candidate (port, path) pairs to probe for the device description.
# Nashville firmware on the Freecom MusicPal typically exposes UPnP on port
# 1400; fall back to common DLNA / HTTP ports as well.
UPNP_DESCRIPTION_CANDIDATES = [
    (1400, "/description.xml"),
    (49152, "/description.xml"),
    (80, "/description.xml"),
]

# Channel reported by RenderingControl events that we care about.
_MASTER_CHANNEL = "Master"


def _localname(tag: str) -> str:
    """Strip the XML namespace URI from *tag*."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def parse_didl_title(didl: str) -> str | None:
    """Return the ``dc:title`` of a DIDL-Lite metadata document."""
    try:
        root = ElementTree.fromstring(didl)
    except ElementTree.ParseError:
        return None
    for element in root.iter():
        if _localname(element.tag) == "title" and element.text:
            return element.text.strip() or None
    return None


def parse_last_change(xml_text: str) -> dict[str, str]:
    """Flatten a UPnP ``LastChange`` document into ``name -> value``.

    ``LastChange`` wraps the actual state variables as ``val`` attributes
    inside an ``<InstanceID>`` element::

        <Event xmlns="...AVT/">
          <InstanceID val="0">
            <TransportState val="PLAYING"/>
          </InstanceID>
        </Event>

    Only instance ``0`` and the ``Master`` channel are considered.
    """
    result: dict[str, str] = {}
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as err:
        _LOGGER.debug("Failed to parse UPnP LastChange document: %s", err)
        return result

    for instance in root:
        if _localname(instance.tag) != "InstanceID":
            continue
        if (instance.get("val") or "0") != "0":
            continue
        for var in instance:
            value = var.get("val")
            if value is None:
                continue
            channel = var.get("channel")
            if channel is not None and channel != _MASTER_CHANNEL:
                continue
            result[_localname(var.tag)] = value
    return result


def parse_upnp_notify_body(body: bytes) -> dict[str, str]:
    """Parse a UPnP NOTIFY body and return its state variables.

    The body is an ``<e:propertyset>`` document.  AVTransport and
    RenderingControl wrap everything in a single ``LastChange`` property,
    which is unwrapped here so callers see the individual state variables.

    Args:
        body: Raw XML bytes from the NOTIFY request body.

    Returns:
        Mapping of UPnP variable name to its string value.
    """
    result: dict[str, str] = {}
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as err:
        _LOGGER.debug("Failed to parse UPnP NOTIFY body: %s", err)
        return result

    ns = {"e": "urn:schemas-upnp-org:event-1-0"}
    properties = root.findall("e:property", ns) or list(root)
    for prop in properties:
        for var in prop:
            if var.text is None:
                continue
            result[_localname(var.tag)] = var.text

    # Unwrap the nested LastChange document, if present.  Without this step
    # the only variable ever reported would be "LastChange" itself.
    if last_change := result.pop("LastChange", None):
        result.update(parse_last_change(last_change))

    if (metadata := result.get("CurrentTrackMetaData")) and (
        title := parse_didl_title(metadata)
    ):
        result["CurrentTrackTitle"] = title

    return result


def parse_upnp_description(xml_content: bytes, base_url: str) -> dict[str, str]:
    """Parse a UPnP device description XML document.

    Args:
        xml_content: Raw XML bytes of the device description.
        base_url: Base URL (scheme + host + port) used to resolve relative
            ``eventSubURL`` paths, e.g. ``"http://192.168.1.10:1400"``.

    Returns:
        Mapping of UPnP service type URN to absolute event sub URL.
    """
    services: dict[str, str] = {}
    try:
        root = ElementTree.fromstring(xml_content)
    except ElementTree.ParseError as err:
        _LOGGER.debug("Failed to parse UPnP description: %s", err)
        return services

    for svc in root.iter():
        if _localname(svc.tag) != "service":
            continue
        stype = ""
        event_url = ""
        for child in svc:
            name = _localname(child.tag)
            if name == "serviceType":
                stype = (child.text or "").strip()
            elif name == "eventSubURL":
                event_url = (child.text or "").strip()
        if stype and event_url:
            services[stype] = urljoin(
                base_url.rstrip("/") + "/",
                event_url.lstrip("/"),
            )
    return services


async def discover_upnp_services(
    client: httpx.AsyncClient,
    hostname: str,
    http_timeout: float = 5.0,
) -> dict[str, str] | None:
    """Probe a MusicPal device for its UPnP service event URLs.

    Tries each candidate (port, path) pair from
    :data:`UPNP_DESCRIPTION_CANDIDATES` in order and returns the first
    successfully parsed service map.

    Args:
        client: HTTP client to use for the probes.
        hostname: IP address or hostname of the MusicPal device.
        http_timeout: Per-request HTTP timeout in seconds.

    Returns:
        Mapping of UPnP service type URN to absolute event sub URL, or
        ``None`` if no description was found.
    """
    for port, path in UPNP_DESCRIPTION_CANDIDATES:
        url = f"http://{hostname}:{port}{path}"
        try:
            response = await client.get(url, timeout=http_timeout)
        except httpx.HTTPError:
            continue
        if response.status_code != 200 or not response.content:
            continue
        services = parse_upnp_description(
            response.content, f"http://{hostname}:{port}"
        )
        if services:
            _LOGGER.debug(
                "Found UPnP description at %s, services: %s",
                url,
                list(services),
            )
            return services

    _LOGGER.debug("No UPnP description found for %s", hostname)
    return None


async def upnp_subscribe(
    client: httpx.AsyncClient,
    event_sub_url: str,
    callback_url: str,
    sid: str | None = None,
    timeout_seconds: int = UPNP_SUBSCRIPTION_TIMEOUT,
) -> str | None:
    """Subscribe to, or renew, a UPnP event subscription.

    When *sid* is ``None`` a new subscription is created; otherwise the
    existing subscription identified by *sid* is renewed.

    Returns:
        The subscription SID on success, ``None`` on failure.
    """
    headers: dict[str, str] = {"TIMEOUT": f"Second-{timeout_seconds}"}
    if sid:
        headers["SID"] = sid
    else:
        headers["NT"] = "upnp:event"
        headers["CALLBACK"] = f"<{callback_url}>"

    try:
        response = await client.request(
            method="SUBSCRIBE",
            url=event_sub_url,
            headers=headers,
            timeout=10.0,
        )
    except httpx.HTTPError as err:
        _LOGGER.debug("UPnP SUBSCRIBE to %s failed: %s", event_sub_url, err)
        return None

    if response.status_code != 200:
        _LOGGER.debug(
            "UPnP SUBSCRIBE to %s returned HTTP %s",
            event_sub_url,
            response.status_code,
        )
        return None

    # On renewal the device is allowed to answer without repeating the SID.
    new_sid = response.headers.get("SID") or sid
    _LOGGER.debug("UPnP subscribed to %s: SID=%s", event_sub_url, new_sid)
    return new_sid or None


async def upnp_unsubscribe(
    client: httpx.AsyncClient,
    event_sub_url: str,
    sid: str,
) -> None:
    """Cancel a UPnP event subscription."""
    try:
        await client.request(
            method="UNSUBSCRIBE",
            url=event_sub_url,
            headers={"SID": sid},
            timeout=10.0,
        )
    except httpx.HTTPError as err:
        _LOGGER.debug("UPnP UNSUBSCRIBE from %s failed: %s", event_sub_url, err)
        return
    _LOGGER.debug("UPnP unsubscribed from %s (SID: %s)", event_sub_url, sid)
