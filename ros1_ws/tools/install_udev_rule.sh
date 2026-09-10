#!/usr/bin/env bash
set -euo pipefail

workspace_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_rule="${workspace_dir}/src/wildebeest_bringup/config/udev/99-wildebeest.rules"
target_rule="/etc/udev/rules.d/99-wildebeest.rules"

if [[ ! -f "${source_rule}" ]]; then
  echo "Missing source rule: ${source_rule}" >&2
  exit 2
fi

sudo install -m 0644 "${source_rule}" "${target_rule}"
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=tty
echo "Installed ${target_rule}. Reconnect devices and verify symlinks before launch."
