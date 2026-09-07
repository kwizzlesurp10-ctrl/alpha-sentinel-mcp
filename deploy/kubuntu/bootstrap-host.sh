#!/usr/bin/env bash
# Kubuntu host: KVM/libvirt + default NAT network. Run with sudo.
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "run as root: sudo $0" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  qemu-kvm \
  qemu-utils \
  libvirt-daemon-system \
  libvirt-clients \
  virtinst \
  virt-manager \
  cloud-image-utils \
  cpu-checker \
  bridge-utils \
  dnsmasq-base \
  ovmf

systemctl enable --now libvirtd

if ! kvm-ok >/dev/null 2>&1; then
  echo "warning: kvm-ok failed — enable VT-x/AMD-V in firmware if VMs are slow" >&2
fi

usermod -aG kvm,libvirt "${SUDO_USER:-$USER}" || true
virsh net-start default >/dev/null 2>&1 || true
virsh net-autostart default >/dev/null 2>&1 || true

echo "Kubuntu KVM host ready. Log out/in so libvirt group membership applies."
echo "Next: deploy/kubuntu/create-vm.sh"
