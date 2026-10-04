"""Proves the test-session isolation in the root conftest.py actually holds (and stays held)."""

from __future__ import annotations

import socket
import threading
from urllib.parse import urlparse

import pytest

from app.config import Settings, get_settings


@pytest.fixture
def guard(pytestconfig):
    """Use pytest's loaded root plugin, never the ambiguous conftest import."""
    from pathlib import Path

    root_file = Path(__file__).resolve().parents[2] / "conftest.py"
    matches = [
        plugin for plugin in pytestconfig.pluginmanager.get_plugins()
        if getattr(plugin, "__file__", None)
        and Path(plugin.__file__).resolve() == root_file
    ]
    assert len(matches) == 1, "Expected exactly one loaded root isolation plugin"
    return matches[0]


def test_settings_use_sentinels_not_real_credentials() -> None:
    settings = get_settings()
    assert urlparse(settings.next_public_supabase_url).hostname == "127.0.0.1"
    assert settings.supabase_service_role_key.startswith("test-")
    assert settings.next_public_supabase_anon_key.startswith("test-")


def test_dotenv_files_are_never_read_during_tests() -> None:
    assert Settings.model_config["env_file"] is None


@pytest.mark.parametrize("host", ["93.184.216.34", "8.8.8.8", "example.com", "project-ref.supabase.co"])
def test_non_loopback_connections_are_blocked(host: str) -> None:
    with pytest.raises(OSError, match="blocked"):
        socket.create_connection((host, 443), timeout=1)


def test_loopback_connections_still_work() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    accepted: list[bool] = []
    thread = threading.Thread(target=lambda: accepted.append(server.accept() is not None))
    thread.start()
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            pass
    finally:
        thread.join(timeout=2)
        server.close()
    assert accepted == [True]


@pytest.mark.parametrize("host", [b"203.0.113.1", b"example.com", b"\xff", None, 123, object()])
def test_internet_socket_hosts_fail_closed(host, guard):
    with socket.socket(socket.AF_INET) as sock:
        with pytest.raises(guard.NetworkBlocked):
            guard._guard_address(sock, (host, 443))


@pytest.mark.parametrize("host", [b"203.0.113.1", b"example.com", b"\xff", 123, object()])
def test_dns_hosts_fail_closed_without_resolver_calls(monkeypatch, host, guard):
    calls = []
    monkeypatch.setattr(guard, "_real_getaddrinfo", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(guard.NetworkBlocked):
        socket.getaddrinfo(host, 443)
    assert calls == []


@pytest.mark.parametrize("family", [socket.AF_INET, socket.AF_INET6])
@pytest.mark.parametrize("address", [(), "not-a-tuple", (None, 443)])
def test_malformed_internet_addresses_are_denied(family, address, guard):
    with socket.socket(family) as sock:
        with pytest.raises(guard.NetworkBlocked):
            guard._guard_address(sock, address)


@pytest.mark.parametrize("flags", [False, True])
@pytest.mark.parametrize("host", ["203.0.113.1", b"203.0.113.1"])
def test_udp_sendto_blocks_before_native_transport(monkeypatch, flags, host, guard):
    calls = []
    monkeypatch.setattr(guard, "_real_sendto", lambda *args: calls.append(args), raising=False)
    # Invalid port also makes an unguarded native call fail without emitting a datagram.
    address = (host, -1)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        with pytest.raises(guard.NetworkBlocked):
            if flags:
                sock.sendto(b"synthetic", 0, address)
            else:
                sock.sendto(b"synthetic", address)
    assert calls == []


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "[::1]", b"127.0.0.1", b"::1", "localhost"])
def test_valid_loopback_host_forms_are_preserved(host, guard):
    assert guard._is_loopback(host)


def test_unix_addresses_are_not_treated_as_internet_hosts(guard):
    from types import SimpleNamespace
    guard._guard_address(SimpleNamespace(family=getattr(socket, "AF_UNIX", -1)), b"/synthetic/socket")


@pytest.mark.parametrize("flags", [False, True])
def test_udp_loopback_is_forwarded_with_original_arguments(monkeypatch, flags, guard):
    calls = []
    monkeypatch.setattr(guard, "_real_sendto", lambda *args: calls.append(args) or 9)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        args = (b"synthetic", 0, ("127.0.0.1", 9000)) if flags else (b"synthetic", ("127.0.0.1", 9000))
        assert sock.sendto(*args) == 9
        assert calls == [(sock, *args)]


def test_deterministic_ci_pins_live_evaluation_off():
    from pathlib import Path
    workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/ci.yml").read_text()
    global_env = workflow.split("\nenv:\n", 1)[1].split("\njobs:", 1)[0]
    assert '  MIRROR_LIVE_EVAL: "0"' in global_env


def test_backend_ci_explicitly_installs_node_for_wrapper_tests():
    from pathlib import Path
    workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/ci.yml").read_text()
    backend = workflow.split("  backend:\n", 1)[1].split("  frontend:\n", 1)[0]
    setup = backend.index("uses: actions/setup-node@v4")
    assert setup < backend.index("node --test scripts/exit-code.test.js")
    assert 'node-version: "24"' in backend[setup:]



