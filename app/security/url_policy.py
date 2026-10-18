from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeResourceURL(ValueError):
    pass


def _is_public_address(value: str) -> bool:
    address = ipaddress.ip_address(value)
    return address.is_global


def validate_external_resource_url(
    url: str,
    *,
    allowed_ports: set[int] | None = None,
) -> str:
    """Reject URLs that could reach local/private infrastructure.

    This is the first application-level SSRF boundary for user-registered resources.
    A production deployment should additionally enforce outbound network policy at
    the hosting/network layer and revalidate every redirect target.
    """

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeResourceURL("Only http and https resource URLs are allowed.")
    if not parsed.hostname:
        raise UnsafeResourceURL("Resource URL must contain a hostname.")
    if parsed.username or parsed.password:
        raise UnsafeResourceURL("Credentials in resource URLs are not allowed.")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise UnsafeResourceURL("Localhost resource URLs are not allowed.")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if allowed_ports is not None and port not in allowed_ports:
        raise UnsafeResourceURL(f"Resource URL port {port} is not allowed.")

    try:
        direct_ip = ipaddress.ip_address(hostname)
    except ValueError:
        direct_ip = None

    if direct_ip is not None:
        if not direct_ip.is_global:
            raise UnsafeResourceURL("Private or non-public IP addresses are not allowed.")
        return url

    try:
        addresses = {
            result[4][0]
            for result in socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        }
    except socket.gaierror as exc:
        raise UnsafeResourceURL("Resource hostname could not be resolved.") from exc

    if not addresses:
        raise UnsafeResourceURL("Resource hostname resolved to no addresses.")
    if any(not _is_public_address(address) for address in addresses):
        raise UnsafeResourceURL(
            "Resource hostname resolves to a private or non-public address."
        )
    return url
