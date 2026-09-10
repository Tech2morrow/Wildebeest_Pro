#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v pio >/dev/null || { echo "PlatformIO Core is required" >&2; exit 127; }
cat <<'WARNING'
Before upload:
  1. Disconnect or disable motor power.
  2. Raise and secure the drive wheels.
  3. Keep the physical E-stop within reach.
Press Enter to continue, or Ctrl-C to abort.
WARNING
read -r
pio run -d "$ROOT_DIR/firmware/wildebeest_base" -t upload
