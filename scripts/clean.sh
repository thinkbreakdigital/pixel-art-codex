#!/usr/bin/env bash
set -euo pipefail

repository_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python="$repository_dir/.venv/bin/python"
if [[ ! -x "$python" ]]; then
    echo "error: virtual environment is missing; run make install" >&2
    exit 1
fi
"$python" -m pixel_art_pipeline.cli clean

