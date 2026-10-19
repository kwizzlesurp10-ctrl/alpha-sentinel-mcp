#!/usr/bin/env bash
# Create the Alpha Sentinel MCP Ubuntu guest on a Kubuntu KVM host.
set -euo pipefail

VM_NAME="${VM_NAME:-alpha-sentinel-mcp}"
RAM_MIB="${RAM_MIB:-4096}"
VCPUS="${VCPUS:-2}"
DISK_GB="${DISK_GB:-20}"
SSH_PUBKEY="${SSH_PUBKEY:-${HOME}/.ssh/id_ed25519.pub}"
IMAGE_DIR="${IMAGE_DIR:-${HOME}/.local/share/libvirt/images}"
CLOUD_IMAGE_URL="${CLOUD_IMAGE_URL:-https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img}"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

if ! command -v virt-install >/dev/null; then
  echo "virt-install missing. Run sudo deploy/kubuntu/bootstrap-host.sh first." >&2
  exit 1
fi

if [[ ! -f "${SSH_PUBKEY}" ]]; then
  echo "SSH public key not found at ${SSH_PUBKEY}. Set SSH_PUBKEY=..." >&2
  exit 1
fi

mkdir -p "${IMAGE_DIR}"
BASE_IMG="${IMAGE_DIR}/noble-server-cloudimg-amd64.img"
DISK="${IMAGE_DIR}/${VM_NAME}.qcow2"
SEED="${IMAGE_DIR}/${VM_NAME}-seed.iso"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "${WORKDIR}"' EXIT

if [[ ! -f "${BASE_IMG}" ]]; then
  curl -L --fail -o "${BASE_IMG}" "${CLOUD_IMAGE_URL}"
fi

if [[ ! -f "${DISK}" ]]; then
  qemu-img create -f qcow2 -F qcow2 -b "${BASE_IMG}" "${DISK}" "${DISK_GB}G"
fi

PUB="$(cat "${SSH_PUBKEY}")"
USER_DATA="${WORKDIR}/user-data"
cp "${REPO_ROOT}/deploy/cloud-init/user-data.yaml" "${USER_DATA}"
python3 - "${USER_DATA}" "${PUB}" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
key = sys.argv[2]
text = path.read_text(encoding="utf-8")
old = "    ssh_authorized_keys: []"
new = "    ssh_authorized_keys:\n      - " + key
if old not in text:
    raise SystemExit("cloud-init template missing ssh_authorized_keys placeholder")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
cp "${REPO_ROOT}/deploy/cloud-init/meta-data" "${WORKDIR}/meta-data"
cloud-localds "${SEED}" "${USER_DATA}" "${WORKDIR}/meta-data"

if virsh dominfo "${VM_NAME}" >/dev/null 2>&1; then
  echo "domain ${VM_NAME} already exists. Use virsh start ${VM_NAME} or destroy it first." >&2
  exit 1
fi

virt-install \
  --name "${VM_NAME}" \
  --memory "${RAM_MIB}" \
  --vcpus "${VCPUS}" \
  --cpu host-passthrough \
  --import \
  --disk "path=${DISK},format=qcow2,bus=virtio" \
  --disk "path=${SEED},device=cdrom" \
  --os-variant ubuntu24.04 \
  --network network=default,model=virtio \
  --graphics none \
  --console pty,target_type=serial \
  --noautoconsole \
  --autostart

echo "Guest ${VM_NAME} defined. Wait for cloud-init, then:"
echo "  virsh domifaddr ${VM_NAME}"
echo "  ssh sentinel@<guest-ip>"
echo "Host port publish (example, replace GUEST_IP):"
echo "  sudo iptables -t nat -A PREROUTING -p tcp --dport 8403 -j DNAT --to-destination <GUEST_IP>:8403"
echo "Or run Docker Compose on the Kubuntu host instead: make compose-up"
