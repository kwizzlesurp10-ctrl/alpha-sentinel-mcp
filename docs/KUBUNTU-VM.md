# Self-host Alpha Sentinel MCP as a server on Kubuntu (KVM guest or host Compose)

This runbook turns [alpha-sentinel-mcp](https://github.com/kwizzlesurp10-ctrl/alpha-sentinel-mcp) into a long-running HTTP MCP seller on a Kubuntu PC. The public process binds `0.0.0.0:$PORT`, holds **no** `EVM_PRIVATE_KEY`, and sits behind Caddy or systemd.

## Topology

```
Kubuntu PC
  ├─ Option A: Docker Compose on the host (fastest professional path)
  │     Caddy :80/:443 → uvicorn 127.0.0.1:8403
  └─ Option B: KVM/libvirt Ubuntu 24.04 guest (isolation)
        Guest Compose or systemd → host NAT/port-forward
```

Do not put a buyer spend key on this box. Set `X402_PAY_TO_ADDRESS` (cold receive) only.

## Option A — Compose on Kubuntu (recommended)

```bash
sudo apt-get update
sudo apt-get install -y git docker.io docker-compose-v2
sudo usermod -aG docker "$USER"
# log out and back in

git clone https://github.com/kwizzlesurp10-ctrl/alpha-sentinel-mcp.git
cd alpha-sentinel-mcp
cp .env.example .env
# edit .env: X402_PAY_TO_ADDRESS, PUBLIC_BASE_URL, optional PUBLIC_HOST

make compose-up
curl -fsS http://127.0.0.1:8403/health
curl -fsS http://127.0.0.1:8403/.well-known/mcp
```

API is published on loopback `:8403`. Caddy publishes LAN/WAN `:80`. For TLS, copy `deploy/Caddyfile.tls` over `deploy/Caddyfile`, set `PUBLIC_HOST` and `ACME_EMAIL` in `.env`, then `docker compose up -d`.

Default `HOST_BIND=127.0.0.1` keeps uvicorn off the LAN. Caddy is the only public socket.

## Option B — KVM guest on Kubuntu

```bash
sudo deploy/kubuntu/bootstrap-host.sh
# new login so libvirt/kvm groups apply
SSH_PUBKEY=~/.ssh/id_ed25519.pub deploy/kubuntu/create-vm.sh
virsh domifaddr alpha-sentinel-mcp
ssh sentinel@<guest-ip>
```

Cloud-init clones this repo into `/opt/alpha-sentinel-mcp`, enables UFW (22/80/443), Docker, qemu-guest-agent, and starts Compose.

Publish the guest from the host (replace `GUEST_IP`):

```bash
sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j DNAT --to-destination GUEST_IP:80
sudo iptables -t nat -A PREROUTING -p tcp --dport 443 -j DNAT --to-destination GUEST_IP:443
```

Persist NAT with `iptables-persistent` or a libvirt network hook.

## Option C — systemd on the guest (no Docker)

```bash
sudo useradd --system --home /opt/alpha-sentinel-mcp --shell /usr/sbin/nologin sentinel
sudo mkdir -p /opt/alpha-sentinel-mcp
sudo git clone https://github.com/kwizzlesurp10-ctrl/alpha-sentinel-mcp.git /opt/alpha-sentinel-mcp
cd /opt/alpha-sentinel-mcp
sudo python3 -m venv .venv
sudo .venv/bin/pip install -r requirements.txt
sudo install -m 0640 deploy/systemd/alpha-sentinel-mcp.env.example /etc/alpha-sentinel-mcp.env
sudo install -m 0644 deploy/systemd/alpha-sentinel-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now alpha-sentinel-mcp
curl -fsS http://127.0.0.1:8403/health
```

The unit runs `assert_seller_safe` before uvicorn. Boot fails if `EVM_PRIVATE_KEY` is present.

## Cursor MCP client (remote HTTP)

```json
{
  "mcpServers": {
    "alpha-sentinel": {
      "url": "http://<kubuntu-host-or-vm>:80/mcp"
    }
  }
}
```

Local stdio (not the VM server):

```json
{
  "mcpServers": {
    "alpha-sentinel-local": {
      "command": "python",
      "args": ["run_stdio.py"],
      "cwd": "/opt/alpha-sentinel-mcp"
    }
  }
}
```

## Firewall on the Kubuntu host

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

Leave `:8403` closed on the WAN if Caddy is in front.

## Checks

| Check | Command |
| --- | --- |
| Health | `curl -fsS http://127.0.0.1:8403/health` |
| MCP initialize | `curl -fsS -X POST http://127.0.0.1:8403/mcp -H 'content-type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"ops","version":"0"}}}'` |
| Doctor | `curl -fsS http://127.0.0.1:8403/doctor` |
| Logs (Compose) | `docker compose logs -f api` |
| Logs (systemd) | `journalctl -u alpha-sentinel-mcp -f` |
