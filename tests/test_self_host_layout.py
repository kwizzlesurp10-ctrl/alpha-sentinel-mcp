"""Layout checks for Kubuntu VM / Compose / systemd self-hosting."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_compose_binds_loopback_api_and_all_interfaces_http() -> None:
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "HOST: \"0.0.0.0\"" in text
    assert "PORT: \"8403\"" in text
    assert "127.0.0.1}:8403:8403" in text
    assert "0.0.0.0}:80:80" in text
    assert "EVM_PRIVATE_KEY" not in text
    assert "scripts/healthcheck.py" in text
    assert "no-new-privileges:true" in text
    assert ".env.defaults" in text


def test_dockerfile_uses_entrypoint_and_port_env() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "ENTRYPOINT [\"/app/scripts/entrypoint.sh\"]" in text
    assert "HOST=0.0.0.0" in text
    assert "PORT=8403" in text
    assert "USER appuser" in text
    assert "scripts/healthcheck.py" in text


def test_entrypoint_refuses_spend_key() -> None:
    text = (ROOT / "scripts" / "entrypoint.sh").read_text(encoding="utf-8")
    assert "assert_seller_safe" in text
    assert "--host" in text
    assert "--port" in text
    assert "app.application:app" in text


def test_systemd_unit_is_hardened() -> None:
    text = (ROOT / "deploy" / "systemd" / "alpha-sentinel-mcp.service").read_text(
        encoding="utf-8"
    )
    assert "User=sentinel" in text
    assert "NoNewPrivileges=true" in text
    assert "assert_seller_safe" in text
    assert "EnvironmentFile=-/etc/alpha-sentinel-mcp.env" in text
    assert "EVM_PRIVATE_KEY" not in text


def test_cloud_init_installs_docker_and_firewall() -> None:
    text = (ROOT / "deploy" / "cloud-init" / "user-data.yaml").read_text(encoding="utf-8")
    assert "docker.io" in text
    assert "docker-compose-v2" in text
    assert "ufw allow 80/tcp" in text
    assert "qemu-guest-agent" in text
    assert "EVM_PRIVATE_KEY" not in text


def test_kubuntu_scripts_are_present() -> None:
    assert (ROOT / "deploy" / "kubuntu" / "bootstrap-host.sh").is_file()
    assert (ROOT / "deploy" / "kubuntu" / "create-vm.sh").is_file()
    assert (ROOT / "docs" / "KUBUNTU-VM.md").is_file()
