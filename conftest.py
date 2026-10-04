"""Test-session isolation. Loaded by pytest before any test module is imported.

Why this exists
---------------
`app.config.Settings` reads `.env` from the working directory. Without isolation:
  * a developer's real hosted-Supabase URL, service-role key and provider keys are loaded into every
    test process, so a test that forgets an override can reach a real project; and
  * five API tests only passed when a Supabase environment existed, because the service constructors
    answer 503 without one - so a clean checkout (CI) failed.

Deterministic test rails (not an OS-level network sandbox)
  1. Settings dotenv loading is disabled; known Supabase/provider credentials are isolated.
     This does not prohibit arbitrary code from directly reading files or inherited secrets.
  2. Supabase is "enabled" with a loopback port-9 sentinel so constructors can be tested.
     The port is not reserved: an unrelated local service could be listening there.
  3. Python socket connect/connect_ex, DNS resolution and UDP sendto reject non-loopback
     Internet hosts. Unix sockets and loopback remain usable. Subprocesses, native libraries,
     and other transports (including sendmsg) are not covered by these Python wrappers.

Global network-guard opt-out, intended only for OPTIONAL live model evaluation:
MIRROR_LIVE_EVAL=1 disables these wrappers for the entire process (see tests/ai_eval/README.md).
Deterministic CI pins MIRROR_LIVE_EVAL=0.
"""

from __future__ import annotations

import ipaddress
import os
import socket

_LIVE = os.environ.get("MIRROR_LIVE_EVAL") == "1"

# --- 1 + 2: settings isolation -------------------------------------------------------------------
_SENTINELS = {
    "NEXT_PUBLIC_SUPABASE_URL": "http://127.0.0.1:9",  # loopback discard-port sentinel, not reserved
    "NEXT_PUBLIC_SUPABASE_ANON_KEY": "test-anon-key-not-a-secret",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key-not-a-secret",
}
_PROVIDER_SECRETS = ("DEEPGRAM_API_KEY", "SARVAM_API_KEY")

for _key, _value in _SENTINELS.items():
    os.environ[_key] = _value  # force: a real value in the developer's shell must not leak in
if not _LIVE:
    for _key in _PROVIDER_SECRETS:
        os.environ.pop(_key, None)

from app.config import Settings, get_settings  # noqa: E402  (after env is prepared)

Settings.model_config["env_file"] = None  # never read .env / .env.local during tests
get_settings.cache_clear()


# --- 3: network guard -----------------------------------------------------------------------------
class NetworkBlocked(OSError):
    """Raised when a deterministic test tries to reach a non-loopback host."""


def _is_loopback(host: object) -> bool:
    if isinstance(host, bytes):
        try:
            host = host.decode("ascii")
        except UnicodeDecodeError:
            return False
    if not isinstance(host, str):
        return False
    if host in ("", "localhost", "localhost.localdomain"):
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


if not _LIVE:
    _real_connect = socket.socket.connect
    _real_connect_ex = socket.socket.connect_ex
    _real_getaddrinfo = socket.getaddrinfo
    _real_sendto = socket.socket.sendto

    def _guard_address(sock: socket.socket, address: object) -> None:
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            if not isinstance(address, tuple) or not address or not _is_loopback(address[0]):
                raise NetworkBlocked("blocked non-loopback or invalid network address in tests")

    def _connect(self: socket.socket, address: object) -> None:
        _guard_address(self, address)
        return _real_connect(self, address)

    def _connect_ex(self: socket.socket, address: object) -> int:
        _guard_address(self, address)
        return _real_connect_ex(self, address)

    def _getaddrinfo(host, *args, **kwargs):  # type: ignore[no-untyped-def]
        # None is the documented wildcard/passive resolver input, not a remote host.
        if host is not None and not _is_loopback(host):
            raise NetworkBlocked("blocked non-loopback or invalid DNS lookup in tests")
        return _real_getaddrinfo(host, *args, **kwargs)

    def _sendto(self: socket.socket, data, *args):
        # Both documented signatures: sendto(data, address), sendto(data, flags, address).
        if len(args) in (1, 2):
            _guard_address(self, args[-1])
        return _real_sendto(self, data, *args)

    socket.socket.sendto = _sendto  # type: ignore[method-assign]
    socket.socket.connect = _connect  # type: ignore[method-assign]
    socket.socket.connect_ex = _connect_ex  # type: ignore[method-assign]
    socket.getaddrinfo = _getaddrinfo  # type: ignore[assignment]
