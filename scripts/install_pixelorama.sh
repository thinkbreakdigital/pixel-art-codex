#!/usr/bin/env bash
set -euo pipefail

repository_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
tool_dir="$repository_dir/.tools/pixelorama"
api_url="https://api.github.com/repos/Orama-Interactive/Pixelorama/releases/latest"

for dependency in curl python3 sha256sum tar find; do
    if ! command -v "$dependency" >/dev/null 2>&1; then
        echo "error: required dependency is missing: $dependency" >&2
        exit 1
    fi
done

case "$(uname -m)" in
    x86_64|amd64) asset_name="Pixelorama-Linux-64bit.tar.gz" ;;
    i386|i486|i586|i686) asset_name="Pixelorama-Linux-32bit.tar.gz" ;;
    aarch64|arm64) asset_name="Pixelorama-Linux-ARM64.tar.gz" ;;
    armv7l|armv6l) asset_name="Pixelorama-Linux-ARM32.tar.gz" ;;
    *) echo "error: no official portable Pixelorama asset for architecture $(uname -m)" >&2; exit 1 ;;
esac

temporary_dir="$(mktemp -d -t pixelorama-install-XXXXXXXX)"
cleanup() {
    rm -rf -- "$temporary_dir"
}
trap cleanup EXIT

release_json="$temporary_dir/release.json"
curl --fail --silent --show-error --location \
    --header 'Accept: application/vnd.github+json' \
    --header 'X-GitHub-Api-Version: 2022-11-28' \
    "$api_url" --output "$release_json"

mapfile -t release_data < <(python3 - "$release_json" "$asset_name" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if payload.get("draft") or payload.get("prerelease"):
    raise SystemExit("error: GitHub latest release is not stable")
asset = next((item for item in payload.get("assets", []) if item.get("name") == sys.argv[2]), None)
if asset is None:
    raise SystemExit(f"error: release {payload.get('tag_name')} lacks {sys.argv[2]}")
digest = asset.get("digest", "")
if not digest.startswith("sha256:"):
    raise SystemExit("error: official release metadata has no SHA-256 digest")
print(payload["tag_name"])
print(asset["browser_download_url"])
print(digest.removeprefix("sha256:"))
PY
)

version="${release_data[0]}"
download_url="${release_data[1]}"
expected_sha256="${release_data[2]}"

if [[ -x "$tool_dir/pixelorama" && -f "$tool_dir/VERSION" ]] \
    && [[ "$(<"$tool_dir/VERSION")" == "$version" ]]; then
    install -m 0755 "$repository_dir/scripts/pixelorama-wrapper.sh" "$tool_dir/pixelorama"
    echo "Pixelorama $version is already installed."
    exit 0
fi

archive="$temporary_dir/$asset_name"
curl --fail --show-error --location "$download_url" --output "$archive"
printf '%s  %s\n' "$expected_sha256" "$archive" | sha256sum --check

python3 - "$archive" <<'PY'
import sys
import tarfile
from pathlib import PurePosixPath

with tarfile.open(sys.argv[1], "r:gz") as archive:
    for member in archive.getmembers():
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts or member.isdev():
            raise SystemExit(f"error: unsafe archive member: {member.name}")
        if member.issym() or member.islnk():
            link = PurePosixPath(member.linkname)
            if link.is_absolute() or ".." in link.parts:
                raise SystemExit(f"error: unsafe archive link: {member.name}")
PY

staging_dir="$temporary_dir/staging"
mkdir -p "$staging_dir/app"
tar -xzf "$archive" -C "$staging_dir/app" --no-same-owner --no-same-permissions

pixelorama_binary=""
while IFS= read -r candidate; do
    case "$(basename -- "$candidate")" in
        Pixelorama|Pixelorama.x86_64|pixelorama|pixelorama.x86_64)
            pixelorama_binary="$candidate"
            break
            ;;
    esac
done < <(find "$staging_dir/app" -type f -perm -u+x -print)

if [[ -z "$pixelorama_binary" ]]; then
    echo "error: verified archive contains no recognizable Pixelorama executable" >&2
    exit 1
fi
if [[ "$(head -c 4 "$pixelorama_binary" | od -An -tx1 | tr -d ' \n')" != "7f454c46" ]]; then
    echo "error: Pixelorama candidate is not an ELF executable" >&2
    exit 1
fi

mkdir -p "$tool_dir"
find "$tool_dir" -mindepth 1 -maxdepth 1 ! -name '.gitkeep' -exec rm -rf -- {} +
mv "$staging_dir/app" "$tool_dir/app"
printf '%s\n' "$version" > "$tool_dir/VERSION"
printf '%s\n' "$expected_sha256" > "$tool_dir/ARCHIVE.sha256"

install -m 0755 "$repository_dir/scripts/pixelorama-wrapper.sh" "$tool_dir/pixelorama"

echo "Installed Pixelorama $version at $tool_dir"
