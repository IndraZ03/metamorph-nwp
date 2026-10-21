"""Verified HTTPS using Windows' certificate store on native Windows."""
from __future__ import annotations

import os
import ssl


def ssl_context():
    if os.name == "nt":
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    return ssl.create_default_context()


def configure_tls():
    """Configure third-party HTTP clients before importing their transports."""
    if os.name == "nt":
        import truststore
        truststore.inject_into_ssl()
