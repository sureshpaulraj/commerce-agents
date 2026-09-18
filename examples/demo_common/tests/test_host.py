# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

import asyncio
import base64
import os

import pytest
from fastapi.testclient import TestClient

from demo_common import host as host_module
from demo_common import host_approval_default, load_demo_env, spawn_background
from demo_common.host import _background_tasks, build_app


def _gated(monkeypatch, credentials: str | None) -> TestClient:
    if credentials is None:
        monkeypatch.delenv("DEMO_BASIC_AUTH", raising=False)
    else:
        monkeypatch.setenv("DEMO_BASIC_AUTH", credentials)
    app = build_app("test")

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    return TestClient(app, base_url="http://localhost")


def test_no_credentials_configured_leaves_every_route_open(monkeypatch):
    # What a loopback demo wants: the gate exists but is not in the way.
    assert _gated(monkeypatch, None).get("/api/health").status_code == 200
    assert _gated(monkeypatch, "   ").get("/api/health").status_code == 200


def test_configured_credentials_are_demanded_of_every_route(monkeypatch):
    client = _gated(monkeypatch, "grower:harvest")
    unauthorized = client.get("/api/health")
    assert unauthorized.status_code == 401
    # Without the challenge a browser has nothing to prompt with.
    assert unauthorized.headers["WWW-Authenticate"].startswith("Basic realm=")
    assert client.get("/api/health", auth=("grower", "harvest")).status_code == 200
    assert client.get("/api/health", auth=("grower", "wrong")).status_code == 401
    assert client.get("/api/health", auth=("someone", "harvest")).status_code == 401


def test_a_preflight_is_answered_before_the_gate(monkeypatch):
    # A browser attaches no credentials to a preflight, so demanding them there would
    # fail the request the browser makes before the one that does carry them.
    client = _gated(monkeypatch, "grower:harvest")
    preflight = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_the_gate_compares_the_whole_header(monkeypatch):
    client = _gated(monkeypatch, "grower:harvest")
    encoded = base64.b64encode(b"grower:harvest").decode()
    assert (
        client.get("/api/health", headers={"Authorization": f"Basic {encoded}"}).status_code == 200
    )
    for wrong in (encoded, f"Bearer {encoded}", f"basic {encoded}", f"Basic  {encoded}"):
        assert client.get("/api/health", headers={"Authorization": wrong}).status_code == 401


@pytest.mark.parametrize(
    ("value", "expected"), [(None, True), ("0", False), ("1", True), ("", True), ("true", True)]
)
def test_only_an_explicit_zero_turns_host_approval_off(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("MERCHANT_REQUIRE_HOST_APPROVAL", raising=False)
    else:
        monkeypatch.setenv("MERCHANT_REQUIRE_HOST_APPROVAL", value)
    assert host_approval_default() is expected


@pytest.fixture
def env_dirs(tmp_path, monkeypatch):
    """A repo root and an example directory under ``tmp_path``, with the loader pointed at
    the former and no credential variables in the environment."""
    repo_root, example_root = tmp_path / "repo", tmp_path / "repo" / "examples" / "retail"
    example_root.mkdir(parents=True)
    monkeypatch.setattr(host_module, "REPO_ROOT", repo_root)
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "COMMERCE_DEMO_AUTH"):
        monkeypatch.delenv(name, raising=False)
    return repo_root, example_root


def test_a_key_in_the_environment_survives_a_blank_env_file(env_dirs, monkeypatch):
    repo_root, example_root = env_dirs
    (repo_root / ".env").write_text("ANTHROPIC_API_KEY=\n")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-the-shell")

    load_demo_env(example_root)

    assert os.environ["ANTHROPIC_API_KEY"] == "from-the-shell"


def test_the_example_env_file_fills_in_before_the_repo_root_one(env_dirs):
    repo_root, example_root = env_dirs
    (repo_root / ".env").write_text("ANTHROPIC_API_KEY=root-key\n")
    (example_root / ".env").write_text("ANTHROPIC_API_KEY=example-key\n")

    load_demo_env(example_root)

    assert os.environ["ANTHROPIC_API_KEY"] == "example-key"


def test_the_repo_root_env_file_is_read_when_the_example_has_none(env_dirs):
    repo_root, example_root = env_dirs
    (repo_root / ".env").write_text("ANTHROPIC_API_KEY=root-key\n")

    load_demo_env(example_root)

    assert os.environ["ANTHROPIC_API_KEY"] == "root-key"


def test_sdk_auth_clears_key_variables_and_reads_no_file(env_dirs, monkeypatch):
    repo_root, example_root = env_dirs
    (repo_root / ".env").write_text("ANTHROPIC_API_KEY=root-key\n")
    monkeypatch.setenv("COMMERCE_DEMO_AUTH", "sdk")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-the-shell")

    load_demo_env(example_root)

    assert "ANTHROPIC_API_KEY" not in os.environ


async def test_spawn_background_holds_the_task_until_it_finishes():
    started, release = asyncio.Event(), asyncio.Event()

    async def work() -> None:
        started.set()
        await release.wait()

    spawn_background(work())
    await asyncio.wait_for(started.wait(), 1)
    assert _background_tasks
    release.set()
    for _ in range(10):
        if not _background_tasks:
            break
        await asyncio.sleep(0)
    assert not _background_tasks
