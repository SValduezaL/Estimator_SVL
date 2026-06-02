"""TLS certificate bundle for HTTP clients (tiktoken / OpenAI on Windows)."""

from __future__ import annotations

import os
import sys

_TIKTOKEN_HTTP_PATCHED = False
_SSL_CONFIGURED = False


def configure_ssl_certificates() -> None:
    """Use OS trust store (Windows) + certifi; patch tiktoken HTTPS downloads."""
    global _SSL_CONFIGURED
    if _SSL_CONFIGURED:
        return

    # Windows corporate proxies: system store often works when certifi alone fails.
    if sys.platform == "win32":
        try:
            import truststore

            truststore.inject_into_ssl()
        except ImportError:
            pass

    import certifi

    bundle = certifi.where()
    os.environ.setdefault("SSL_CERT_FILE", bundle)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", bundle)
    _patch_tiktoken_read_file(bundle)
    _SSL_CONFIGURED = True


def _patch_tiktoken_read_file(ca_bundle: str) -> None:
    """tiktoken uses requests.get without verify= for HTTPS; fix when not using local BPE."""
    global _TIKTOKEN_HTTP_PATCHED
    if _TIKTOKEN_HTTP_PATCHED:
        return

    import requests
    import tiktoken.load as tiktoken_load

    original_read_file = tiktoken_load.read_file

    def read_file(blobpath: str) -> bytes:
        if "://" not in blobpath:
            return original_read_file(blobpath)
        if blobpath.startswith(("http://", "https://")):
            response = requests.get(blobpath, verify=ca_bundle)
            response.raise_for_status()
            return response.content
        return original_read_file(blobpath)

    tiktoken_load.read_file = read_file  # type: ignore[method-assign]
    _TIKTOKEN_HTTP_PATCHED = True


def create_openai_http_client(*, timeout_seconds: float = 60.0) -> object:
    """httpx client for OpenAI SDK (SSL configured via configure_ssl_certificates)."""
    import httpx

    configure_ssl_certificates()
    return httpx.Client(timeout=timeout_seconds)
