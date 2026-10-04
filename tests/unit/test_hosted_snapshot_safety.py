"""Synthetic snapshot safety checks: no dotenv reads or network requests."""
import importlib.util
import io
from pathlib import Path
import urllib.error
import urllib.request
from email.message import Message
from urllib.response import addinfourl

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "scripts/ops/hosted_readonly_snapshot.py"


def snapshot_functions():
    spec = importlib.util.spec_from_file_location("snapshot_safety", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.__dict__.update(URL="https://project.invalid", KEY="synthetic-not-a-secret")
    return module


@pytest.mark.parametrize("target", ["https://other.invalid/stolen", "https://project.invalid/elsewhere", "http://project.invalid/downgrade"])
@pytest.mark.parametrize("redirect_status", [301, 302, 303, 307, 308])
@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_snapshot_rejects_every_redirect_without_forwarding_credentials(monkeypatch, target, redirect_status, method):
    module = snapshot_functions()
    seen = []

    class SyntheticHTTP(urllib.request.BaseHandler):
        handler_order = 50  # Intercept before proxy/default handlers; never open a socket.

        def https_open(self, request):
            seen.append(request)
            headers = Message()
            status = redirect_status if len(seen) == 1 else 200
            if status == redirect_status:
                headers["Location"] = target
            response = addinfourl(io.BytesIO(b"synthetic"), headers, request.full_url, status)
            response.msg = "synthetic response"
            return response

        http_open = https_open

    real_build = urllib.request.build_opener
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: real_build(SyntheticHTTP(), *handlers))
    monkeypatch.setattr(urllib.request, "urlopen", real_build(SyntheticHTTP()).open)
    status, _, _ = module.get("/rest/v1/", method=method)
    assert status == redirect_status, "redirect must be returned, never followed"
    assert len(seen) == 1, "credentials must never be sent to a redirected target"


@pytest.mark.parametrize("url", [
    "http://project.invalid", "https://user:password@project.invalid",
    "https://project.invalid/rest/v1", "https://project.invalid?query=1",
    "https://project.invalid#fragment", "https://", "https://project.invalid:bad",
    "https://project.invalid/", "https://project.invalid?", "https://project.invalid#",
    "https://project.invalid\\other", "https://project.invalid\n",
])
def test_invalid_project_base_is_rejected_before_transport(monkeypatch, url):
    module = snapshot_functions()
    module.URL = url
    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: pytest.fail("transport constructed"))
    with pytest.raises(ValueError, match="project URL"):
        module.get("/rest/v1/")


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT", "get", ""])
def test_other_methods_are_explicitly_rejected(monkeypatch, method):
    module = snapshot_functions()
    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: pytest.fail("transport constructed"))
    with pytest.raises(ValueError, match="read-only"):
        module.get("/rest/v1/", method=method)


def test_import_does_not_load_credentials_or_create_output(monkeypatch):
    spec = importlib.util.spec_from_file_location("snapshot_import_test", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setattr(Path, "read_text", lambda *args, **kwargs: pytest.fail("credential file read on import"))
    monkeypatch.setattr(Path, "mkdir", lambda *args, **kwargs: pytest.fail("output created on import"))
    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: pytest.fail("transport created on import"))
    spec.loader.exec_module(module)


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_readonly_methods_send_one_authenticated_request(monkeypatch, method):
    module = snapshot_functions()
    seen = []

    class SyntheticHTTP(urllib.request.BaseHandler):
        handler_order = 50

        def https_open(self, request):
            seen.append(request)
            response = addinfourl(io.BytesIO(b"synthetic"), Message(), request.full_url, 200)
            response.msg = "synthetic response"
            return response

    real_build = urllib.request.build_opener
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: real_build(SyntheticHTTP(), *handlers))
    assert module.get("/rest/v1/", method=method)[0] == 200
    assert len(seen) == 1
    assert seen[0].get_method() == method
    assert seen[0].get_header("Authorization") == "Bearer synthetic-not-a-secret"
    assert seen[0].get_header("Apikey") == "synthetic-not-a-secret"


def test_default_urllib_redirect_would_copy_service_headers():
    # Reproduces the underlying disclosure without sending any request.
    request = urllib.request.Request("https://project.invalid/rest/v1/", headers={
        "Authorization": "Bearer synthetic-not-a-secret", "apikey": "synthetic-not-a-secret",
    })
    redirected = urllib.request.HTTPRedirectHandler().redirect_request(
        request, None, 302, "synthetic", Message(), "https://other.invalid/stolen",
    )
    assert redirected is not None
    assert redirected.get_header("Authorization") == request.get_header("Authorization")
    assert redirected.get_header("Apikey") == request.get_header("Apikey")


@pytest.mark.parametrize("path", ["@other.invalid/stolen", "https://other.invalid/stolen", "//other.invalid/stolen", "/rest/v1/#fragment", "/rest/v1/\n", "/\\other.invalid"])
def test_request_paths_cannot_change_or_obscure_the_origin(monkeypatch, path):
    module = snapshot_functions()
    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: pytest.fail("transport constructed"))
    with pytest.raises(ValueError, match="path"):
        module.get(path)


def test_transport_errors_do_not_expose_credentials(monkeypatch):
    module = snapshot_functions()

    class BrokenTransport:
        def open(self, *args, **kwargs):
            raise RuntimeError("synthetic-not-a-secret")

    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: BrokenTransport())
    status, headers, body = module.get("/rest/v1/")
    assert status == -1
    assert headers == {}
    assert b"synthetic-not-a-secret" not in body

