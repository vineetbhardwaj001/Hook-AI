"""
URL Security & SSRF Prevention Service
"""
from __future__ import annotations
import ipaddress
import socket
import re
from urllib.parse import urlparse
from app.core.constants import ALLOWED_URL_HOSTS
from app.core.exceptions import InvalidURLError, UnsupportedURLError


BLOCKED_SCHEMES = {"file", "ftp", "gopher", "data", "ldap", "dict", "smb", "netbios", "javascript"}
ALLOWED_SCHEMES = {"http", "https"}

PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def is_private_ip(hostname: str) -> bool:
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(hostname))
        return any(ip in net for net in PRIVATE_NETWORKS)
    except (socket.gaierror, ValueError):
        return False


def validate_url(url: str) -> str:
    """
    Validate that the URL is safe, allowed, and return the normalized URL.
    Raises InvalidURLError or UnsupportedURLError on failure.
    """
    url = url.strip()
    if not url:
        raise InvalidURLError("URL cannot be empty.")

    try:
        parsed = urlparse(url)
    except Exception:
        raise InvalidURLError("Could not parse the URL.")

    # Scheme check
    scheme = (parsed.scheme or "").lower()
    if scheme in BLOCKED_SCHEMES:
        raise InvalidURLError(f"URL scheme '{scheme}' is not allowed.")
    if scheme not in ALLOWED_SCHEMES:
        raise InvalidURLError(f"URL must use http or https.")

    # Hostname check
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise InvalidURLError("URL has no hostname.")

    # Block localhost / internal hostnames
    localhost_patterns = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"}
    if hostname in localhost_patterns:
        raise InvalidURLError("Requests to localhost or internal addresses are not allowed.")

    # Block private IP ranges
    if is_private_ip(hostname):
        raise InvalidURLError("Requests to private network addresses are not allowed.")

    # Provider allowlist
    base_host = hostname.removeprefix("www.").removeprefix("m.")
    if not any(hostname == h or hostname.endswith("." + h) for h in ALLOWED_URL_HOSTS):
        raise UnsupportedURLError()

    return url


def is_youtube_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower().removeprefix("www.").removeprefix("m.")
        return hostname in {"youtube.com", "youtu.be", "music.youtube.com"}
    except Exception:
        return False
