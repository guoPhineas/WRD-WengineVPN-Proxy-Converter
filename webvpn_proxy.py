#!/usr/bin/env python3
"""A small HTTP/HTTPS proxy which sends requests through a WebVPN gateway."""

from __future__ import annotations

import argparse
import asyncio
from urllib.parse import urlsplit, urlunsplit

from mitmproxy import http, options
from mitmproxy.tools.dump import DumpMaster
from wengine_decryptor import decrypt_webvpn_url, encrypt_webvpn_url


# ---- Replace these two values before use. WEBVPN_URL may use HTTP or HTTPS. ----
WEBVPN_URL = "http://vpn.xxx.edu.cn"
WEBVPN_COOKIE_NAME = "wengine_vpn_ticketvpn_xxx_edu_cn"
WEBVPN_COOKIE_VALUE = "xxxxx"
WENGINE_KEY = "wrdvpnisthebest!"
WENGINE_IV = "wrdvpnisthebest!"

# Only these domains (including their subdomains) are sent through WebVPN.
PROXY_DOMAIN_WHITELIST = {
    "baidu.com",
    "github.com",
    # "example.com",
}

# Requests under these directories are left completely unchanged.
DIRECT_PATH_PREFIXES = {
    "/wengine-vpn/",
}


def is_whitelisted(host: str) -> bool:
    """Return whether host exactly matches, or is a subdomain of, an entry."""
    normalized_host = host.lower().rstrip(".")
    for entry in PROXY_DOMAIN_WHITELIST:
        normalized_entry = entry.lower().strip().lstrip("*.").rstrip(".")
        if normalized_entry and (
            normalized_host == normalized_entry
            or normalized_host.endswith(f".{normalized_entry}")
        ):
            return True
    return False


def is_direct_path(path: str) -> bool:
    """Return whether path belongs to a directory that must bypass rewriting."""
    for entry in DIRECT_PATH_PREFIXES:
        normalized_entry = "/" + entry.strip("/")
        if path == normalized_entry or path.startswith(f"{normalized_entry}/"):
            return True
    return False


def decrypt_authority(encrypted_authority: str) -> str | None:
    """Decrypt and validate an authority stored in a WebVPN path."""
    try:
        authority = decrypt_webvpn_url(
            encrypted_authority,
            WENGINE_KEY,
            WENGINE_IV,
        )
    except (UnicodeDecodeError, ValueError):
        return None

    if not authority or any(char in authority for char in "/?#\r\n"):
        return None
    return authority


def parse_webvpn_encoded_path(path: str) -> tuple[str, str, str] | None:
    """Parse /http(s)/<encrypted-host>/path into its original URL parts."""
    gateway_path = urlsplit(WEBVPN_URL).path.rstrip("/")
    prefix = f"{gateway_path}/"
    if not path.startswith(prefix):
        return None

    remainder = path[len(prefix) :]
    scheme, separator, target = remainder.partition("/")
    if not separator or scheme not in {"http", "https"}:
        return None

    encrypted_authority, separator, target_path = target.partition("/")
    authority = decrypt_authority(encrypted_authority)
    if not authority:
        return None

    target_path = f"/{target_path}" if separator else "/"
    return scheme, authority, target_path


def is_webvpn_encoded_path(path: str) -> bool:
    return parse_webvpn_encoded_path(path) is not None


def gateway_url_for_encoded_path(request_url: str) -> str:
    """Move an already encoded path back onto the configured WebVPN host."""
    request = urlsplit(request_url)
    gateway = urlsplit(WEBVPN_URL.rstrip("/"))
    return urlunsplit(
        (gateway.scheme, gateway.netloc, request.path, request.query, "")
    )


def webvpn_url(original_url: str) -> str:
    """Put the encrypted target authority into a WebVPN URL."""
    original = urlsplit(original_url)
    gateway = urlsplit(WEBVPN_URL.rstrip("/"))
    encrypted_authority = encrypt_webvpn_url(
        original.netloc,
        WENGINE_KEY,
        WENGINE_IV,
    )
    path = original.path or "/"
    gateway_path = (
        f"{gateway.path.rstrip('/')}/{original.scheme}/{encrypted_authority}{path}"
    )
    return urlunsplit((gateway.scheme, gateway.netloc, gateway_path, original.query, ""))


def original_url(location: str) -> str | None:
    """Undo a WebVPN URL in a redirect Location header, when possible."""
    gateway = urlsplit(WEBVPN_URL.rstrip("/"))
    parsed = urlsplit(location)

    if parsed.netloc and parsed.netloc.lower() != gateway.netloc.lower():
        return None

    path = parsed.path
    prefix = gateway.path.rstrip("/") + "/"
    if not path.startswith(prefix):
        return None

    decoded = parse_webvpn_encoded_path(path)
    if not decoded:
        return None

    scheme, authority, target_path = decoded
    return urlunsplit((scheme, authority, target_path, parsed.query, parsed.fragment))


class WebVPNProxy:
    def request(self, flow: http.HTTPFlow) -> None:
        request = flow.request
        gateway = urlsplit(WEBVPN_URL)
        gateway_host = (gateway.hostname or "").lower().rstrip(".")
        request_host = request.host.lower().rstrip(".")
        parsed_request = urlsplit(request.pretty_url)
        encoded_target = parse_webvpn_encoded_path(parsed_request.path)

        # WebVPN's own static files, such as /wengine-vpn/main.js, bypass all
        # URL and header changes.
        if is_direct_path(parsed_request.path):
            return

        # Absolute links already pointing at WebVPN need no URL conversion.
        if request_host == gateway_host:
            request.headers["Cookie"] = (
                f"{WEBVPN_COOKIE_NAME}={WEBVPN_COOKIE_VALUE}"
            )
            request.headers.pop("Proxy-Authorization", None)
            return

        # WebVPN may inject a root-relative /http/<encrypted-host>/... link.
        # The browser resolves it against the visible original host, so move the
        # existing encoded path back to WebVPN without encrypting it again.
        if encoded_target:
            target_scheme, target_authority, target_path = encoded_target
            target_host = urlsplit(
                f"{target_scheme}://{target_authority}"
            ).hostname

            if target_host and is_whitelisted(target_host):
                flow.metadata["webvpn_original_url"] = request.pretty_url
                flow.metadata["webvpn_rewritten"] = True
                request.url = gateway_url_for_encoded_path(request.pretty_url)
                request.headers["Cookie"] = (
                    f"{WEBVPN_COOKIE_NAME}={WEBVPN_COOKIE_VALUE}"
                )
            else:
                # Respect the whitelist by restoring non-whitelisted targets
                # and connecting to them directly.
                request.url = urlunsplit(
                    (
                        target_scheme,
                        target_authority,
                        target_path,
                        parsed_request.query,
                        "",
                    )
                )
            request.headers.pop("Proxy-Authorization", None)
            return

        if not is_whitelisted(request_host):
            return

        flow.metadata["webvpn_original_url"] = request.pretty_url
        flow.metadata["webvpn_rewritten"] = True
        request.url = webvpn_url(request.pretty_url)
        request.headers["Cookie"] = f"{WEBVPN_COOKIE_NAME}={WEBVPN_COOKIE_VALUE}"
        request.headers.pop("Proxy-Authorization", None)

    def response(self, flow: http.HTTPFlow) -> None:
        # Keep redirects transparent when the gateway returns its encoded URL.
        if not flow.metadata.get("webvpn_rewritten"):
            return

        location = flow.response.headers.get("Location")
        if location:
            decoded = original_url(location)
            if decoded:
                flow.response.headers["Location"] = decoded


addons = [WebVPNProxy()]


async def run(host: str, port: int) -> None:
    opts = options.Options(listen_host=host, listen_port=port)
    master = DumpMaster(opts, with_termlog=True, with_dumper=False)
    master.addons.add(WebVPNProxy())
    try:
        await master.run()
    finally:
        master.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="listen address")
    parser.add_argument("--port", type=int, default=8080, help="listen port")
    args = parser.parse_args()

    gateway = urlsplit(WEBVPN_URL)
    if gateway.scheme not in {"http", "https"} or not gateway.netloc:
        parser.error("WEBVPN_URL must be like http://vpn.a.com or https://vpn.a.com")
    if len(WENGINE_KEY.encode()) not in {16, 24, 32}:
        parser.error("WENGINE_KEY must be 16, 24, or 32 bytes")
    if len(WENGINE_IV.encode()) != 16:
        parser.error("WENGINE_IV must be 16 bytes")
    if not WEBVPN_COOKIE_NAME or any(
        char in WEBVPN_COOKIE_NAME for char in "=; \t\r\n"
    ):
        parser.error("WEBVPN_COOKIE_NAME is not a valid cookie name")
    if WEBVPN_COOKIE_VALUE.startswith("replace-"):
        parser.error("please replace WEBVPN_COOKIE_VALUE at the top of this file")
    asyncio.run(run(args.host, args.port))


if __name__ == "__main__":
    main()
