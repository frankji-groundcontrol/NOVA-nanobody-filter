#!/bin/sh
# Pin external MIT FreeSASA source bundled in Aggrescan3D; see ../README.md.
set -eu
source_root=${1:?Usage: sh build-freesasa.sh SOURCE_ARTIFACT_DIR}
revision=afd8a9da1f44f7b702aceb5a80abe67dde74ca00
mkdir -p "$source_root"
if [ ! -d "$source_root/upstream/.git" ]; then
  git clone https://bitbucket.org/lcbio/aggrescan3d.git "$source_root/upstream"
  git -C "$source_root/upstream" checkout --detach "$revision"
fi
if [ "$(git -C "$source_root/upstream" rev-parse HEAD)" != "$revision" ]; then
  printf '%s\n' 'Source checkout is not the required pinned revision' >&2
  exit 2
fi
cd "$source_root/upstream/aggrescan/data/freesasa-2.0.1"
# Git does not preserve timestamps, so Make treats the release's generated
# Autotools files as stale and tries to rebuild them with aclocal-1.15.
touch aclocal.m4 configure config.h.in Makefile.in src/Makefile.in \
  tests/Makefile.in share/Makefile.in doc/Makefile.in bindings/Makefile.in
./configure --disable-json --disable-xml --disable-threads --disable-check
make -j4
./src/freesasa --version
