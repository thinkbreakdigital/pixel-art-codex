#!/usr/bin/env bash
set -euo pipefail

repository_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
wrapper="$repository_dir/.tools/pixelorama/pixelorama"

usage() {
    echo "Usage: $0 PATH.{pxo,png,gif,apng}" >&2
}

if [[ $# -ne 1 ]]; then
    usage
    exit 2
fi
asset_path="$(realpath -e -- "$1" 2>/dev/null)" || {
    echo "error: asset does not exist: $1" >&2
    exit 1
}
if [[ ! -f "$asset_path" ]]; then
    echo "error: asset is not a regular file: $asset_path" >&2
    exit 1
fi
case "${asset_path,,}" in
    *.pxo|*.png|*.gif|*.apng) ;;
    *) echo "error: unsupported file type; expected .pxo, .png, .gif, or .apng" >&2; exit 2 ;;
esac
if [[ ! -x "$wrapper" ]]; then
    echo "error: Pixelorama is not installed; run make install" >&2
    exit 1
fi

exec "$wrapper" -- "$asset_path"
