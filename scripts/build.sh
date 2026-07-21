#!/usr/bin/env bash
set -euo pipefail

repository_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
venv_dir="$repository_dir/.venv"
python_command="${PYTHON:-python3}"

if ! command -v "$python_command" >/dev/null 2>&1; then
    echo "error: Python 3 is required but '$python_command' was not found" >&2
    exit 1
fi

if [[ ! -x "$venv_dir/bin/python" ]]; then
    if ! "$python_command" -m venv "$venv_dir"; then
        echo "warning: ensurepip is unavailable; creating a venv without pip" >&2
        "$python_command" -m venv --without-pip --clear "$venv_dir"
    fi
fi

if ! "$venv_dir/bin/python" -m pip --version >/dev/null 2>&1; then
    echo "Bootstrapping pip from verified PyPI wheel metadata..."
    "$python_command" - "$venv_dir" <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

venv = Path(sys.argv[1])
with urllib.request.urlopen("https://pypi.org/pypi/pip/json", timeout=30) as response:
    metadata = json.load(response)
wheel = next(item for item in metadata["urls"] if item["filename"].endswith("py3-none-any.whl"))
with tempfile.TemporaryDirectory(prefix="pixel-art-pip-") as temporary:
    wheel_path = Path(temporary) / wheel["filename"]
    with urllib.request.urlopen(wheel["url"], timeout=60) as response:
        payload = response.read()
    actual = hashlib.sha256(payload).hexdigest()
    expected = wheel["digests"]["sha256"]
    if actual != expected:
        raise SystemExit(f"error: pip wheel SHA-256 mismatch: expected {expected}, got {actual}")
    wheel_path.write_bytes(payload)
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(wheel_path)
    subprocess.run(
        [str(venv / "bin" / "python"), "-m", "pip", "install", "--no-index", str(wheel_path)],
        check=True,
        env=environment,
    )
PY
fi

"$venv_dir/bin/python" -m pip install \
    --require-virtualenv \
    --disable-pip-version-check \
    --requirement "$repository_dir/requirements.lock"
"$venv_dir/bin/python" -m pip install \
    --require-virtualenv \
    --disable-pip-version-check \
    --no-deps \
    --editable "$repository_dir"
"$repository_dir/scripts/install_pixelorama.sh"

echo "Installation complete: $repository_dir"
