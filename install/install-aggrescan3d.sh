#!/bin/sh
set -eu
project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tool_root="$project_root/.tools"
cargo install --locked --path "$project_root/tools/aggrescan3d-rs" --root "$tool_root"
sh "$project_root/tools/aggrescan3d-rs/tools/build-freesasa.sh" "$tool_root/aggrescan3d-source"
cp "$tool_root/aggrescan3d-source/upstream/aggrescan/data/freesasa-2.0.1/src/freesasa" "$tool_root/bin/freesasa"
printf '%s\n' 'Aggrescan3D and pinned FreeSASA installed in .tools/bin.'
printf '%s\n' 'Add .tools/bin to PATH and set AGGRESCAN3D_ENABLED=1 before starting NOVA.'
