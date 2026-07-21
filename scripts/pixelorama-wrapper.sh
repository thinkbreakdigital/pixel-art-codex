#!/usr/bin/env bash
set -euo pipefail

tool_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
candidate=""
while IFS= read -r path; do
    case "$(basename -- "$path")" in
        Pixelorama|Pixelorama.x86_64|pixelorama|pixelorama.x86_64)
            candidate="$path"
            break
            ;;
    esac
done < <(find "$tool_dir/app" -type f -perm -u+x -print)
if [[ -z "$candidate" ]]; then
    echo "error: Pixelorama executable was not found below $tool_dir/app" >&2
    exit 1
fi
exec "$candidate" "$@"

